"""Publishing kill switch. Publishing is allowed only when BOTH the env flag and the DB flag are on.

Default is OFF. The emergency stop flips the DB flag off immediately and records who/why.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.db import utcnow
from app.models import Setting

KEY = "publishing"
CONFIRM_PHRASE = "ENABLE PUBLISHING"


@dataclass(frozen=True)
class PublishingState:
    env_enabled: bool
    db_enabled: bool
    reason: str | None
    changed_at: str | None

    @property
    def can_publish(self) -> bool:
        return self.env_enabled and self.db_enabled


def get_state(session: Session, env_enabled: bool) -> PublishingState:
    row = session.get(Setting, KEY)
    value = row.value if row else {}
    return PublishingState(
        env_enabled=env_enabled,
        db_enabled=bool(value.get("enabled", False)),
        reason=value.get("reason"),
        changed_at=value.get("changed_at"),
    )


def _set(session: Session, enabled: bool, reason: str) -> None:
    value = {"enabled": enabled, "reason": reason, "changed_at": utcnow().isoformat()}
    row = session.get(Setting, KEY)
    if row:
        row.value = value
    else:
        session.add(Setting(key=KEY, value=value))
    session.flush()


def emergency_stop(session: Session, reason: str) -> None:
    _set(session, False, f"EMERGENCY STOP: {reason}")


def enable_publishing(session: Session, confirm: str, reason: str) -> None:
    if confirm != CONFIRM_PHRASE:
        raise PermissionError(f"Type the exact phrase {CONFIRM_PHRASE!r} to enable publishing")
    _set(session, True, reason)


class PublishingDisabled(RuntimeError):
    pass


def assert_can_publish(session: Session, env_enabled: bool) -> None:
    """Call immediately before any publishing API call."""
    state = get_state(session, env_enabled)
    if not state.can_publish:
        raise PublishingDisabled(
            f"Publishing blocked (env={state.env_enabled}, db={state.db_enabled}, reason={state.reason})"
        )
