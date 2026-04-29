"""Jobs router — launch / list / cancel parser subprocesses, stream logs via SSE."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlmodel import or_, select

from app.deps import CurrentUser, SessionDep
from app.models.job import Job, JobStatus
from app.models.telegram_account import TelegramAccount
from app.schemas.job import JobCreate, JobRead
from app.services import jobs_runner

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


def _to_read(job: Job) -> JobRead:
    assert job.id is not None
    return JobRead(
        id=job.id,
        owner_id=job.owner_id,
        telegram_account_id=job.telegram_account_id,
        mode=job.mode,
        channel=job.channel,
        export_format=job.export_format,
        status=job.status,
        pid=job.pid,
        exit_code=job.exit_code,
        created_at=job.created_at,
        started_at=job.started_at,
        ended_at=job.ended_at,
    )


def _account_visible_to(account: TelegramAccount, user_id: int | None) -> bool:
    return account.owner_id == user_id or account.is_shared


@router.post(
    "",
    response_model=JobRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_job(
    payload: JobCreate,
    session: SessionDep,
    current_user: CurrentUser,
) -> JobRead:
    """Spawn a parser subprocess for the caller, using the chosen TG slot."""
    assert current_user.id is not None
    account = session.get(TelegramAccount, payload.telegram_account_id)
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

    job = Job(
        owner_id=current_user.id,
        telegram_account_id=payload.telegram_account_id,
        mode=payload.mode,
        channel=payload.channel,
        export_format=payload.export_format,
        status=JobStatus.pending,
        log_path="",
    )
    session.add(job)
    session.commit()
    session.refresh(job)
    assert job.id is not None
    job.log_path = str(jobs_runner.log_path_for(job.id))
    session.add(job)
    session.commit()
    session.refresh(job)

    asyncio.create_task(jobs_runner.launch(job.id))
    return _to_read(job)


@router.get("", response_model=list[JobRead])
def list_jobs(
    session: SessionDep,
    current_user: CurrentUser,
    limit: int = 50,
) -> list[JobRead]:
    """Return jobs the caller owns plus jobs that ran on shared TG accounts."""
    assert current_user.id is not None
    statement = (
        select(Job)
        .join(
            TelegramAccount,
            TelegramAccount.id == Job.telegram_account_id,
        )
        .where(
            or_(
                Job.owner_id == current_user.id,
                TelegramAccount.is_shared.is_(True),  # type: ignore[attr-defined]
            )
        )
        .order_by(Job.id.desc())  # type: ignore[union-attr]
        .limit(max(1, min(limit, 200)))
    )
    return [_to_read(j) for j in session.exec(statement)]


@router.get("/{job_id}", response_model=JobRead)
def get_job(
    job_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> JobRead:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.owner_id != current_user.id:
        account = session.get(TelegramAccount, job.telegram_account_id)
        if account is None or not _account_visible_to(account, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed"
            )
    return _to_read(job)


@router.post("/{job_id}/cancel", response_model=JobRead)
async def cancel_job(
    job_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> JobRead:
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the owner may cancel a job",
        )
    await jobs_runner.cancel(job_id)
    session.refresh(job)
    return _to_read(job)


@router.get("/{job_id}/logs")
async def stream_logs(
    job_id: int,
    session: SessionDep,
    current_user: CurrentUser,
) -> StreamingResponse:
    """Server-Sent-Events endpoint that replays then tails the job log."""
    job = session.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if job.owner_id != current_user.id:
        account = session.get(TelegramAccount, job.telegram_account_id)
        if account is None or not _account_visible_to(account, current_user.id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed"
            )

    log_path = Path(job.log_path)

    async def event_stream():
        try:
            async for chunk in jobs_runner.tail_log_iter(log_path, job_id=job_id):
                text = chunk.decode("utf-8", errors="replace")
                for line in text.splitlines() or [""]:
                    yield f"data: {line}\n\n".encode()
            yield b"event: end\ndata: \n\n"
        except asyncio.CancelledError:  # pragma: no cover — client disconnect
            return

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
