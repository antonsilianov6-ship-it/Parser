"""Async subprocess runner for panel-launched parser jobs.

A :class:`Job` row is created in *pending* state, then :func:`launch` spawns
``python main.py --mode <mode> [--channel X] [--format F]`` with the per-slot
``PARSER_SESSION_PATH`` / ``TELEGRAM_API_ID`` / ``TELEGRAM_API_HASH`` env
overrides. Stdout/stderr are merged into a per-job log file under
``logs/jobs/<id>.log``; when the process exits the row is updated with
``status``, ``exit_code`` and ``ended_at``.

The runner deliberately avoids holding ``Job`` ORM objects across awaits — it
only persists ids and short metadata, then opens a fresh DB session inside
:func:`_finalize_in_background` to write the result.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
from datetime import UTC, datetime
from pathlib import Path

from sqlmodel import Session

from app.db import get_engine
from app.models.job import Job, JobMode, JobStatus
from app.models.telegram_account import TelegramAccount

logger = logging.getLogger(__name__)


_running: dict[int, asyncio.subprocess.Process] = {}


def project_root() -> Path:
    """Path to the parser repo root (where ``main.py`` lives)."""
    return Path(__file__).resolve().parents[4]


def log_path_for(job_id: int) -> Path:
    """Return the on-disk log file path for a job (idempotent ``mkdir``)."""
    log_dir = project_root() / "logs" / "jobs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{job_id}.log"


def _build_command(job: Job) -> list[str]:
    cmd = [sys.executable, "-u", "main.py", "--mode", job.mode.value]
    if job.mode == JobMode.parse and job.channel:
        cmd.extend(["--channel", job.channel])
    if job.mode == JobMode.export and job.export_format:
        cmd.extend(["--format", job.export_format])
    return cmd


def _build_env(account: TelegramAccount) -> dict[str, str]:
    """Return a child env with per-slot Telegram credentials patched in."""
    env = os.environ.copy()
    if account.api_id is not None:
        env["TELEGRAM_API_ID"] = str(account.api_id)
    if account.api_hash:
        env["TELEGRAM_API_HASH"] = account.api_hash
    session_full = project_root() / account.session_path
    env["PARSER_SESSION_PATH"] = str(session_full)
    env["PYTHONIOENCODING"] = "utf-8"
    return env


async def launch(job_id: int) -> None:
    """Spawn the parser subprocess for ``job_id`` and arrange for finalisation."""
    with Session(get_engine()) as db:
        job = db.get(Job, job_id)
        if job is None:
            logger.error("launch(%s): job not found", job_id)
            return
        account = db.get(TelegramAccount, job.telegram_account_id)
        if account is None:
            job.status = JobStatus.failed
            job.ended_at = datetime.now(tz=UTC)
            db.add(job)
            db.commit()
            return
        if not account.is_authorized:
            _write_log(
                Path(job.log_path),
                "ERROR: Telegram account is not authorised; cancel and re-auth first.\n",
            )
            job.status = JobStatus.failed
            job.ended_at = datetime.now(tz=UTC)
            db.add(job)
            db.commit()
            return
        cmd = _build_command(job)
        env = _build_env(account)
        log_path = Path(job.log_path)

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_file = log_path.open("ab", buffering=0)
    log_file.write(
        (
            f"$ {' '.join(cmd)}\n"
            f"# session: {env.get('PARSER_SESSION_PATH', '?')}\n"
            f"# started: {datetime.now(tz=UTC).isoformat()}\n"
            f"---\n"
        ).encode()
    )

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(project_root()),
            env=env,
            stdout=log_file,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
    except FileNotFoundError as err:
        log_file.write(f"ERROR: cannot launch parser: {err}\n".encode())
        log_file.close()
        with Session(get_engine()) as db:
            job = db.get(Job, job_id)
            if job is not None:
                job.status = JobStatus.failed
                job.ended_at = datetime.now(tz=UTC)
                db.add(job)
                db.commit()
        return

    _running[job_id] = proc
    with Session(get_engine()) as db:
        job = db.get(Job, job_id)
        if job is not None:
            job.status = JobStatus.running
            job.pid = proc.pid
            job.started_at = datetime.now(tz=UTC)
            db.add(job)
            db.commit()

    asyncio.create_task(_finalize_in_background(job_id, proc, log_file))


async def _finalize_in_background(
    job_id: int,
    proc: asyncio.subprocess.Process,
    log_file: object,  # actual type is BufferedWriter; kept loose for cross-platform
) -> None:
    try:
        exit_code = await proc.wait()
    finally:
        try:
            log_file.close()  # type: ignore[attr-defined]
        except Exception:  # pragma: no cover
            pass
        _running.pop(job_id, None)

    with Session(get_engine()) as db:
        job = db.get(Job, job_id)
        if job is None:
            return
        if job.status == JobStatus.cancelled:
            pass  # leave as cancelled even if exit_code is non-zero
        elif exit_code == 0:
            job.status = JobStatus.succeeded
        else:
            job.status = JobStatus.failed
        job.exit_code = exit_code
        job.ended_at = datetime.now(tz=UTC)
        db.add(job)
        db.commit()


async def cancel(job_id: int) -> bool:
    """Send SIGINT to the running subprocess, if any."""
    proc = _running.get(job_id)
    if proc is None or proc.returncode is not None:
        return False
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGINT)
    except (ProcessLookupError, PermissionError):
        return False
    with Session(get_engine()) as db:
        job = db.get(Job, job_id)
        if job is not None and job.status == JobStatus.running:
            job.status = JobStatus.cancelled
            db.add(job)
            db.commit()
    return True


def is_running(job_id: int) -> bool:
    proc = _running.get(job_id)
    return proc is not None and proc.returncode is None


async def tail_log_iter(
    log_path: Path,
    *,
    job_id: int,
    poll_interval: float = 0.5,
    idle_timeout: float = 5.0,
):
    """Async generator: replay the existing log then poll for new bytes.

    Stops when (a) the job is no longer running and (b) no new bytes have been
    written for ``idle_timeout`` seconds (so a finished job's tail still
    flushes).
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)
    with log_path.open("rb") as fh:
        # Replay existing bytes line-by-line.
        while True:
            chunk = fh.readline()
            if not chunk:
                break
            yield chunk

        last_data = asyncio.get_event_loop().time()
        while True:
            chunk = fh.readline()
            if chunk:
                last_data = asyncio.get_event_loop().time()
                yield chunk
                continue
            if not is_running(job_id):
                if asyncio.get_event_loop().time() - last_data > idle_timeout:
                    return
            await asyncio.sleep(poll_interval)


def _write_log(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as fh:
        fh.write(text.encode("utf-8"))
