"""Schedules CRUD — cron-driven parse-job triggers."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status
from sqlmodel import or_, select

from app.deps import CurrentUser, SessionDep
from app.models.schedule import Schedule
from app.models.telegram_account import TelegramAccount
from app.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate
from app.services import parser_files, scheduler

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


def _to_read(schedule: Schedule) -> ScheduleRead:
    assert schedule.id is not None
    return ScheduleRead(
        id=schedule.id,
        owner_id=schedule.owner_id,
        telegram_account_id=schedule.telegram_account_id,
        name=schedule.name,
        cron_expression=schedule.cron_expression,
        channel=schedule.channel,
        export_to_docs=schedule.export_to_docs,
        export_to_notebooklm=schedule.export_to_notebooklm,
        is_active=schedule.is_active,
        last_run_at=schedule.last_run_at,
        next_run_at=schedule.next_run_at,
        created_at=schedule.created_at,
        updated_at=schedule.updated_at,
    )


def _account_visible_to(account: TelegramAccount, user_id: int) -> bool:
    return account.owner_id == user_id or account.is_shared


def _check_account_and_creds(
    session: SessionDep,
    current_user: User,
    *,
    telegram_account_id: int,
    export_to_docs: bool,
    export_to_notebooklm: bool,
) -> None:
    """Mirror the pre-flight checks the jobs router does at POST time."""
    assert current_user.id is not None
    account = session.get(TelegramAccount, telegram_account_id)
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Telegram account not found",
        )
    if not _account_visible_to(account, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot use this Telegram account",
        )
    if not account.is_authorized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram account is not authorised yet",
        )
    if export_to_docs:
        if not parser_files.has_google_credentials(current_user.id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Для экспорта в Google Docs сначала загрузите Service "
                    "Account JSON в Настройки → Google"
                ),
            )
        owner = session.get(User, current_user.id)
        if owner is None or not owner.google_doc_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите Google Doc ID в Настройки → Google",
            )
    if export_to_notebooklm and not parser_files.has_notebooklm_storage(
        current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Для NotebookLM сначала загрузите storage_state.json в "
                "Настройки → Google"
            ),
        )


@router.post(
    "",
    response_model=ScheduleRead,
    status_code=status.HTTP_201_CREATED,
)
def create_schedule(
    payload: ScheduleCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ScheduleRead:
    assert current_user.id is not None
    _check_account_and_creds(
        session,
        current_user,
        telegram_account_id=payload.telegram_account_id,
        export_to_docs=payload.export_to_docs,
        export_to_notebooklm=payload.export_to_notebooklm,
    )
    schedule = Schedule(
        owner_id=current_user.id,
        telegram_account_id=payload.telegram_account_id,
        name=payload.name,
        cron_expression=payload.cron_expression,
        channel=payload.channel,
        export_to_docs=payload.export_to_docs,
        export_to_notebooklm=payload.export_to_notebooklm,
        is_active=payload.is_active,
    )
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    scheduler.upsert_schedule(schedule)
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return _to_read(schedule)


@router.get("", response_model=list[ScheduleRead])
def list_schedules(
    session: SessionDep,
    current_user: CurrentUser,
) -> list[ScheduleRead]:
    assert current_user.id is not None
    statement = (
        select(Schedule)
        .join(
            TelegramAccount,
            TelegramAccount.id == Schedule.telegram_account_id,
        )
        .where(
            or_(
                Schedule.owner_id == current_user.id,
                TelegramAccount.is_shared.is_(True),  # type: ignore[attr-defined]
            )
        )
        .order_by(Schedule.id.desc())  # type: ignore[union-attr]
    )
    return [_to_read(s) for s in session.exec(statement)]


def _load_owned(
    session: SessionDep, current_user: CurrentUser, schedule_id: int
) -> Schedule:
    schedule = session.get(Schedule, schedule_id)
    if schedule is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Schedule not found"
        )
    if schedule.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner may manage this schedule",
        )
    return schedule


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    session: SessionDep,
    current_user: CurrentUser,
) -> ScheduleRead:
    schedule = _load_owned(session, current_user, schedule_id)

    # Compute the post-update flags so we can validate creds before mutating.
    new_account_id = (
        payload.telegram_account_id
        if payload.telegram_account_id is not None
        else schedule.telegram_account_id
    )
    new_docs = (
        payload.export_to_docs
        if payload.export_to_docs is not None
        else schedule.export_to_docs
    )
    new_nlm = (
        payload.export_to_notebooklm
        if payload.export_to_notebooklm is not None
        else schedule.export_to_notebooklm
    )
    new_is_active = (
        payload.is_active if payload.is_active is not None else schedule.is_active
    )

    # Validate creds only when the post-update schedule is going to actually
    # fire — otherwise the user can't pause or rename a stale schedule
    # whose creds were removed (e.g. after rotating the Service Account JSON).
    # Same for the at-least-one-export check: a deactivated schedule with
    # neither flag is harmless because no Job will be spawned.
    if new_is_active:
        if not (new_docs or new_nlm):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Для расписания нужно выбрать хотя бы один вариант "
                    "выгрузки: Google Docs или NotebookLM"
                ),
            )
        _check_account_and_creds(
            session,
            current_user,
            telegram_account_id=new_account_id,
            export_to_docs=new_docs,
            export_to_notebooklm=new_nlm,
        )

    if payload.name is not None:
        schedule.name = payload.name
    if payload.telegram_account_id is not None:
        schedule.telegram_account_id = payload.telegram_account_id
    if payload.cron_expression is not None:
        schedule.cron_expression = payload.cron_expression
    # ``channel`` is the only field where ``None`` is a meaningful value
    # (= "parse all channels from channels.txt"), so we have to look at
    # ``model_fields_set`` to tell "field omitted" from "explicitly cleared".
    if "channel" in payload.model_fields_set:
        schedule.channel = payload.channel
    if payload.export_to_docs is not None:
        schedule.export_to_docs = payload.export_to_docs
    if payload.export_to_notebooklm is not None:
        schedule.export_to_notebooklm = payload.export_to_notebooklm
    if payload.is_active is not None:
        schedule.is_active = payload.is_active
    schedule.updated_at = datetime.now(tz=UTC)

    session.add(schedule)
    session.commit()
    session.refresh(schedule)

    scheduler.upsert_schedule(schedule)
    session.add(schedule)
    session.commit()
    session.refresh(schedule)
    return _to_read(schedule)


@router.delete(
    "/{schedule_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_schedule(
    schedule_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> None:
    schedule = _load_owned(session, current_user, schedule_id)
    scheduler.remove_schedule(schedule_id)
    session.delete(schedule)
    session.commit()
