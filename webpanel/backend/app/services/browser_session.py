"""In-process orchestration of headed Chromium for interactive logins.

The panel keeps **at most one** active session at a time so multiple
concurrent panel users can't see each other's screens through the
shared X display in the ``browser`` docker service. Subsequent
callers receive a 409 from the auth router until the running session
finishes (success / cancel / timeout).

A session is created with :func:`start_session`, polled with
:func:`get_session`, and finalised with :func:`harvest_storage_state`
or :func:`cancel_session`. Each session carries its own Playwright
:class:`BrowserContext` so cookies / localStorage are isolated from
any leftover profile data — but they all share the same Chromium
window the user sees over noVNC.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Literal

from app.config import Settings

if TYPE_CHECKING:  # pragma: no cover - typing only
    from playwright.async_api import Browser, BrowserContext, Page, Playwright
else:
    Browser = BrowserContext = Page = Playwright = object


logger = logging.getLogger(__name__)


# Time after which a session is auto-cancelled if the user never
# completes the login. 10 minutes is generous for a multi-step Google
# login including 2FA.
SESSION_TIMEOUT_SECONDS = 10 * 60

# If a session has not been polled / interacted with for this many
# seconds we consider it abandoned (the user closed the tab, lost
# their network, etc.) and let *another* user take over the slot
# without waiting for the full ``SESSION_TIMEOUT_SECONDS`` budget.
# The SPA polls every 2 seconds, so 30 seconds is comfortably above
# any normal poll cadence yet keeps the unblocking latency for a
# second user low.
SESSION_IDLE_TAKEOVER_SECONDS = 30

SessionStatus = Literal["pending", "loading", "ready", "completed", "cancelled", "error"]


@dataclass
class BrowserSession:
    """State for one interactive browser-login session."""

    id: str
    user_id: int
    purpose: str  # currently always "notebooklm"
    target_url: str
    success_url_substring: str
    status: SessionStatus = "pending"
    error: str | None = None
    started_at: float = field(default_factory=time.time)
    last_polled_at: float = field(default_factory=time.time)
    finished_at: float | None = None
    # Playwright handles. Kept private so callers don't have to deal
    # with the async lifecycle directly.
    _playwright: Playwright | None = None
    _browser: Browser | None = None
    _context: BrowserContext | None = None
    _page: Page | None = None

    @property
    def is_active(self) -> bool:
        return self.status in ("pending", "loading", "ready")

    @property
    def expired(self) -> bool:
        return time.time() - self.started_at > SESSION_TIMEOUT_SECONDS

    @property
    def idle_seconds(self) -> float:
        return time.time() - self.last_polled_at

    @property
    def can_be_taken_over(self) -> bool:
        """True when another user is allowed to preempt this session.

        Either the session has gone past its hard timeout (no progress
        in 10 minutes) or it has been silent for more than
        ``SESSION_IDLE_TAKEOVER_SECONDS`` (the SPA stopped polling —
        usually because the tab was closed or the user navigated away).
        """
        return self.expired or self.idle_seconds > SESSION_IDLE_TAKEOVER_SECONDS

    def to_public_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "purpose": self.purpose,
            "status": self.status,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "target_url": self.target_url,
        }


class BrowserSessionManager:
    """Singleton-ish manager around the shared headed Chromium."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._lock = asyncio.Lock()
        self._session: BrowserSession | None = None

    @property
    def cdp_url(self) -> str:
        return self._settings.browser_cdp_url

    @property
    def public_url(self) -> str:
        return self._settings.browser_public_url

    async def start_session(
        self,
        *,
        user_id: int,
        purpose: str,
        target_url: str,
        success_url_substring: str,
    ) -> BrowserSession:
        """Open a Chromium tab pointing at ``target_url``.

        Raises:
            RuntimeError: if a different user already has an active
                session, or if the browser service is unreachable.
        """
        async with self._lock:
            existing = self._session
            if existing is not None and existing.is_active:
                if existing.user_id == user_id:
                    # Same user — return the existing one so the SPA can resume.
                    existing.last_polled_at = time.time()
                    return existing
                if not existing.can_be_taken_over:
                    raise RuntimeError(
                        "browser_busy: another user has an active session"
                    )
                # Other user's session is stale (expired or no recent
                # poll) — reclaim the slot so a fresh user isn't held
                # hostage by an abandoned tab.
                logger.info(
                    "Preempting idle browser session %s (user_id=%s, idle=%.1fs)",
                    existing.id,
                    existing.user_id,
                    existing.idle_seconds,
                )
                existing.error = "preempted"
                await self._teardown(existing, mark_status="cancelled")
            elif existing is not None:
                # Already-finalised session — clear it before starting a new one.
                await self._teardown(existing, mark_status="cancelled")

            session = BrowserSession(
                id=secrets.token_urlsafe(12),
                user_id=user_id,
                purpose=purpose,
                target_url=target_url,
                success_url_substring=success_url_substring,
                status="loading",
            )
            self._session = session

        try:
            await self._open_page(session)
        except Exception as exc:  # noqa: BLE001 — surface to caller
            session.status = "error"
            session.error = str(exc)
            session.finished_at = time.time()
            logger.exception("Browser session %s failed to start", session.id)
            raise
        return session

    async def get_session(self, session_id: str) -> BrowserSession | None:
        session = self._session
        if session is None or session.id != session_id:
            return None
        # Bump the heartbeat *before* any teardown so a single missed
        # poll doesn't immediately race the takeover threshold.
        session.last_polled_at = time.time()
        if session.is_active and session.expired:
            await self._teardown(session, mark_status="cancelled")
            session.error = "timeout"
        elif session.is_active and session._page is not None:
            try:
                current = session._page.url
            except Exception:  # noqa: BLE001 — page may have closed
                current = ""
            # Use a prefix check rather than substring so that Google's
            # accounts.google.com login redirect (which embeds NotebookLM
            # under continue=https://notebooklm.google.com/...) does NOT
            # falsely flip status to "ready" before the user has actually
            # signed in.
            if current and current.startswith(session.success_url_substring):
                session.status = "ready"
        return session

    async def harvest_storage_state(self, session_id: str) -> dict[str, object] | None:
        """Extract Playwright ``storage_state`` from the current context.

        Returns ``None`` if the session id doesn't match or is no
        longer active. The caller is responsible for serialising the
        returned dict to disk and then calling :func:`cancel_session`
        (or relying on this method which also tears the session
        down).
        """
        session = self._session
        if session is None or session.id != session_id:
            return None
        if session._context is None:
            return None
        try:
            state = await session._context.storage_state()
        except Exception as exc:  # noqa: BLE001 — bubble error
            logger.exception("Failed to capture storage state for %s", session.id)
            session.status = "error"
            session.error = str(exc)
            await self._teardown(session, mark_status=session.status)
            raise
        await self._teardown(session, mark_status="completed")
        # Roundtrip through json so the result is plain dict/list/str
        # and easy to write with json.dumps().
        return json.loads(json.dumps(state))

    async def cancel_session(self, session_id: str) -> bool:
        session = self._session
        if session is None or session.id != session_id:
            return False
        await self._teardown(session, mark_status="cancelled")
        return True

    async def cancel_sessions_for_user(self, user_id: int) -> bool:
        """Cancel any active session owned by ``user_id``.

        Called from the user-delete endpoint so deleting an admin
        mid-login doesn't leave their orphaned session pinning the
        shared Chromium for the full ``SESSION_TIMEOUT_SECONDS``
        window.
        """
        session = self._session
        if session is None or session.user_id != user_id:
            return False
        if not session.is_active:
            return False
        logger.info(
            "Cancelling browser session %s because user %s was deleted",
            session.id,
            user_id,
        )
        session.error = "user_deleted"
        await self._teardown(session, mark_status="cancelled")
        return True

    async def shutdown(self) -> None:
        if self._session is not None:
            await self._teardown(self._session, mark_status="cancelled")

    async def _open_page(self, session: BrowserSession) -> None:
        from playwright.async_api import async_playwright

        playwright = await async_playwright().start()
        try:
            browser = await playwright.chromium.connect_over_cdp(self.cdp_url)
        except Exception:
            await playwright.stop()
            raise

        # Anything below can fail (network blip on goto, ctx.close races,
        # CDP target loss). Until we've stashed the handles on the session
        # object, ``_teardown`` won't see them — so we clean up locally on
        # any failure to avoid leaking the WebSocket / browser process.
        try:
            # ``connect_over_cdp`` yields the existing Chromium instance.
            # Close leftover contexts so the visible window is always the
            # brand-new login tab.
            for ctx in list(browser.contexts):
                try:
                    await ctx.close()
                except Exception:  # noqa: BLE001 — best-effort cleanup
                    pass

            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(session.target_url, wait_until="domcontentloaded")
        except Exception:
            for handle, closer in (
                (locals().get("page"), lambda h: h.close()),
                (locals().get("context"), lambda h: h.close()),
                (browser, lambda h: h.close()),
                (playwright, lambda h: h.stop()),
            ):
                if handle is None:
                    continue
                try:
                    await closer(handle)
                except Exception:  # noqa: BLE001 — best-effort
                    logger.debug(
                        "Cleanup error while unwinding failed _open_page",
                        exc_info=True,
                    )
            raise

        session._playwright = playwright
        session._browser = browser
        session._context = context
        session._page = page
        session.status = "pending"

    async def _teardown(
        self,
        session: BrowserSession,
        *,
        mark_status: SessionStatus,
    ) -> None:
        for handle, closer in (
            (session._page, lambda h: h.close()),
            (session._context, lambda h: h.close()),
            (session._browser, lambda h: h.close()),
            (session._playwright, lambda h: h.stop()),
        ):
            if handle is None:
                continue
            try:
                await closer(handle)
            except Exception:  # noqa: BLE001 — best-effort
                logger.debug("Error tearing down browser session %s", session.id, exc_info=True)
        session._page = None
        session._context = None
        session._browser = None
        session._playwright = None
        if session.is_active:
            session.status = mark_status
        if session.finished_at is None:
            session.finished_at = time.time()


_manager: BrowserSessionManager | None = None


def get_manager(settings: Settings) -> BrowserSessionManager:
    """Return the lazy-initialised singleton."""
    global _manager
    if _manager is None:
        _manager = BrowserSessionManager(settings)
    return _manager


def reset_manager_for_tests() -> None:
    """Drop the cached manager between tests."""
    global _manager
    _manager = None
