"""Cookie-backed authentication for the protected VoiceAgent Demo workspace."""

from __future__ import annotations

import secrets
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from urllib.parse import quote

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse, Response
from starlette.types import ASGIApp

AUTH_COOKIE = "voiceagent_demo_session"


@dataclass
class AuthSession:
    """Server-side website login state."""

    created_at: float
    last_seen_at: float


class AuthSessionStore:
    """Maintain revocable website sessions with idle and absolute expiry."""

    def __init__(self, *, idle_seconds: int = 43_200, absolute_seconds: int = 604_800) -> None:
        """Initialize login expiry windows.

        Args:
            idle_seconds: Maximum inactivity before reauthentication.
            absolute_seconds: Maximum lifetime even while active.
        """
        self.idle_seconds = idle_seconds
        self.absolute_seconds = absolute_seconds
        self._sessions: dict[str, AuthSession] = {}

    def create(self) -> tuple[str, float, float]:
        """Create one opaque browser session and return its expiry metadata."""
        now = time.time()
        self._sessions = {
            token: session
            for token, session in self._sessions.items()
            if now < session.created_at + self.absolute_seconds
            and now - session.last_seen_at < self.idle_seconds
        }
        token = secrets.token_urlsafe(32)
        self._sessions[token] = AuthSession(created_at=now, last_seen_at=now)
        return token, now + self.idle_seconds, now + self.absolute_seconds

    def validate(self, token: str, *, touch: bool = True) -> tuple[float, float] | None:
        """Validate and optionally extend a session's inactivity window."""
        session = self._sessions.get(token)
        if session is None:
            return None
        now = time.time()
        absolute_expires_at = session.created_at + self.absolute_seconds
        if now >= absolute_expires_at or now - session.last_seen_at >= self.idle_seconds:
            self._sessions.pop(token, None)
            return None
        if touch:
            session.last_seen_at = now
        idle_expires_at = min(session.last_seen_at + self.idle_seconds, absolute_expires_at)
        return idle_expires_at, absolute_expires_at

    def revoke(self, token: str) -> None:
        """Invalidate one website session immediately."""
        self._sessions.pop(token, None)


class LoginAttemptLimiter:
    """Bound repeated login failures without retaining submitted credentials."""

    def __init__(self, *, max_failures: int = 5, window_seconds: int = 60) -> None:
        """Configure the per-client failure window."""
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._failures: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, client: str) -> bool:
        """Return whether another login attempt is currently allowed."""
        now = time.monotonic()
        failures = self._failures[client]
        while failures and now - failures[0] >= self.window_seconds:
            failures.popleft()
        return len(failures) < self.max_failures

    def fail(self, client: str) -> None:
        """Record one failed login without storing its submitted values."""
        self._failures[client].append(time.monotonic())

    def clear(self, client: str) -> None:
        """Clear failures after a successful login."""
        self._failures.pop(client, None)


class ProductAuthMiddleware(BaseHTTPMiddleware):
    """Protect website routes with a Cookie while preserving call Bearer tokens."""

    def __init__(self, app: ASGIApp, *, sessions: AuthSessionStore) -> None:
        """Initialize route protection with the shared website session store."""
        super().__init__(app)
        self._sessions = sessions

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Authorize a page Cookie or return product-owned login behavior."""
        path = request.url.path
        if self._is_public(path) or self._uses_call_bearer(path):
            return await call_next(request)

        token = request.cookies.get(AUTH_COOKIE, "")
        expiry = self._sessions.validate(token)
        if expiry is None:
            if path.startswith("/api/"):
                return JSONResponse({"detail": "Website login required"}, status_code=401)
            target = path
            if request.url.query:
                target += f"?{request.url.query}"
            return RedirectResponse(
                f"/login?expired=1&next={quote(target, safe='')}", status_code=303
            )

        request.state.auth_idle_expires_at = expiry[0]
        request.state.auth_absolute_expires_at = expiry[1]
        response = await call_next(request)
        if path != "/api/auth/logout":
            self.set_cookie(response, token, expiry[0])
        return response

    @staticmethod
    def _is_public(path: str) -> bool:
        """Return whether a route is intentionally available before login."""
        return path.startswith("/assets/") or path in {
            "/health",
            "/login",
            "/login.html",
            "/api/auth/login",
        }

    @staticmethod
    def _uses_call_bearer(path: str) -> bool:
        """Keep per-call telemetry independent from the website login Cookie."""
        parts = path.rstrip("/").split("/")
        return (
            len(parts) == 5
            and parts[1:3] == ["api", "sessions"]
            and parts[4]
            in {
                "events",
                "metrics",
            }
        )

    def set_cookie(self, response: Response, token: str, expires_at: float) -> None:
        """Attach an unreadable, HTTPS-only website session Cookie."""
        max_age = max(0, int(expires_at - time.time()))
        response.set_cookie(
            AUTH_COOKIE,
            token,
            max_age=max_age,
            httponly=True,
            secure=True,
            samesite="strict",
            path="/",
        )


def safe_return_path(value: str | None) -> str:
    """Accept only a local absolute path as a post-login destination."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/"
    return value
