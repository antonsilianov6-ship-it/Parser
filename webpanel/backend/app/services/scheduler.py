"""APScheduler integration for cron-based parse jobs.

A single ``AsyncIOScheduler`` runs inside the FastAPI process. It
holds one APScheduler job per active :class:`~app.models.schedule.Schedule`
row and on tick spawns a regular :class:`~app.models.job.Job` exactly
the way the ``POST /api/jobs`` route does — so users see the run on
the existing `/jobs` page with full SSE log streaming.

The mapping between APScheduler job ids and Schedule ids is one-to-one:
``apscheduler_id = f"schedule:{schedule.id}"``. ``init_scheduler()``
loads all active schedules at startup; ``upsert_schedule()`` /
``remove_schedule()`` keep APScheduler in sync with CRUD operations.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlmodel import Session, select

from app.db import get_engine
from app.models.job import Job, JobMode, JobStatus
from app.models.schedule import Schedule
from app.services import jobs_runner

logger = logging.getLogger(__name__)


_scheduler: AsyncIOScheduler | None = None


def _job_id(schedule_id: int) -> str:
    return f"schedule:{schedule_id}"


def get_scheduler() -> AsyncIOScheduler | None:
    return _scheduler


async def init_scheduler() -> None:
    """Start the AsyncIOScheduler and (re)load every active schedule."""
    global _scheduler
    if _scheduler is not None:
        return
    _scheduler = AsyncIOScheduler(timezone="UTC")
    _scheduler.start()
    with Session(get_engine()) as session:
        rows = session.exec(select(Schedule).where(Schedule.is_active.is_(True))).all()  # type: ignore[attr-defined]
        for schedule in rows:
            _add_or_replace_job(schedule)
            session.add(schedule)
        session.commit()
    logger.info("Scheduler started with %d active schedules", len(rows))


async def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None


def upsert_schedule(schedule: Schedule) -> None:
    """Mirror a Schedule row into the running APScheduler instance."""
    if _scheduler is None:
        # Tests may exercise CRUD without starting the scheduler.
        logger.debug("Scheduler not running; skipping upsert for %s", schedule.id)
        return
    if schedule.id is None:
        return
    if schedule.is_active:
        _add_or_replace_job(schedule)
    else:
        _scheduler.remove_job(_job_id(schedule.id), jobstore=None) if _has_job(
            schedule.id
        ) else None


def remove_schedule(schedule_id: int) -> None:
    if _scheduler is None or not _has_job(schedule_id):
        return
    _scheduler.remove_job(_job_id(schedule_id))


def _has_job(schedule_id: int) -> bool:
    if _scheduler is None:
        return False
    return _scheduler.get_job(_job_id(schedule_id)) is not None


def _add_or_replace_job(schedule: Schedule) -> None:
    assert _scheduler is not None
    assert schedule.id is not None
    trigger = CronTrigger.from_crontab(schedule.cron_expression, timezone="UTC")
    _scheduler.add_job(
        _fire_schedule,
        trigger=trigger,
        id=_job_id(schedule.id),
        kwargs={"schedule_id": schedule.id},
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,
        max_instances=1,
    )
    schedule.next_run_at = _scheduler.get_job(_job_id(schedule.id)).next_run_time


async def _fire_schedule(schedule_id: int) -> None:
    """Tick handler — create a Job row and hand it to the runner."""
    with Session(get_engine()) as session:
        schedule = session.get(Schedule, schedule_id)
        if schedule is None or not schedule.is_active:
            logger.info("Schedule %s vanished or disabled, skipping tick", schedule_id)
            return

        job = Job(
            owner_id=schedule.owner_id,
            telegram_account_id=schedule.telegram_account_id,
            mode=JobMode.parse,
            channel=schedule.channel,
            export_format=None,
            export_to_docs=schedule.export_to_docs,
            export_to_notebooklm=schedule.export_to_notebooklm,
            status=JobStatus.pending,
            log_path="",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        assert job.id is not None
        job.log_path = str(jobs_runner.log_path_for(job.id))
        session.add(job)

        schedule.last_run_at = datetime.now(tz=UTC)
        if _scheduler is not None:
            ap_job = _scheduler.get_job(_job_id(schedule_id))
            if ap_job is not None:
                schedule.next_run_at = ap_job.next_run_time
        schedule.updated_at = datetime.now(tz=UTC)
        session.add(schedule)
        session.commit()

        job_id = job.id

    asyncio.create_task(jobs_runner.launch(job_id))
