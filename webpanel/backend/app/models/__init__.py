"""SQLModel model registry — importing this module registers tables on metadata."""

from app.models.job import Job, JobMode, JobStatus
from app.models.telegram_account import TelegramAccount
from app.models.user import User

__all__ = ["Job", "JobMode", "JobStatus", "TelegramAccount", "User"]
