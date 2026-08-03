"""Session state machine, stage guards and telemetry recording.

The narrative is linear and the gating is enforced here, on the server. In the
prototype the thesis lock was "a JS boolean with no UI path to reverse it",
which is not a lock -- it is an inconvenience. A student who can edit their
thesis after seeing the archive has not taken the test the simulation
administers.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .models import Session as RunSession, TelemetryEvent

SCREEN_ORDER = (
    "brief",
    "dashboard",
    "research",
    "thesis",
    "committee",
    "deliberation",
    "inbox",
    "evidence",
    "model",
    "dealflow",
    "results",
    "debrief",
    "scorecard",
    "report",
)

SCREEN_LABELS = {
    "brief": "Brief",
    "dashboard": "Dashboard",
    "research": "Research",
    "thesis": "Thesis",
    "committee": "Committee",
    "deliberation": "Deliberation",
    "inbox": "Inbox",
    "evidence": "Evidence",
    "model": "Model",
    "dealflow": "Deal flow",
    "results": "Performance",
    "debrief": "Debrief",
    "scorecard": "Scorecard",
    "report": "Report",
}


def screen_index(screen: str) -> int:
    try:
        return SCREEN_ORDER.index(screen)
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown screen '{screen}'")


def now() -> datetime:
    return datetime.now(timezone.utc)


async def record_event(
    db: AsyncSession,
    run: RunSession,
    kind: str,
    *,
    subject: str | int | None = None,
    payload: dict | None = None,
) -> None:
    """Append a behavioural event.

    Called from inside the endpoints that the behaviour actually requires, so
    the log reflects what happened rather than what the client claims happened.
    """
    db.add(
        TelemetryEvent(
            session_id=run.id,
            kind=kind,
            subject=str(subject) if subject is not None else None,
            payload=payload,
            screen=run.current_screen,
        )
    )


def deliberation_remaining(run: RunSession) -> int:
    if run.deliberation_started_at is None:
        return settings.deliberation_seconds
    started = run.deliberation_started_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    elapsed = (now() - started).total_seconds()
    return max(0, int(round(settings.deliberation_seconds - elapsed)))


def _deny(message: str) -> None:
    raise HTTPException(status.HTTP_409_CONFLICT, message)


def assert_can_enter(run: RunSession, screen: str, n_partners: int) -> None:
    """Guard every forward transition. Backward navigation is always allowed --
    a student may re-read the research screen, they simply cannot un-lock a
    thesis or un-see the archive."""
    target = screen_index(screen)

    if target <= screen_index(run.furthest_screen):
        return  # revisiting somewhere already reached

    if target > screen_index(run.furthest_screen) + 1:
        _deny("Screens must be reached in order")

    if screen == "committee" and not run.thesis_locked:
        _deny("Lock your thesis before presenting to the committee")

    if screen == "deliberation":
        answered = len(run.committee_answers or [])
        if answered < n_partners:
            _deny(f"Answer all {n_partners} partners before the committee deliberates")

    if screen == "inbox" and deliberation_remaining(run) > 0:
        _deny("The committee is still deliberating")

    if screen == "evidence" and not run.archive_unlocked:
        _deny("Open the archive first")

    if screen == "dealflow" and not run.model_weights:
        _deny("Build your scoring model before reviewing deal flow")

    if screen == "results" and not run.deployed:
        _deny("Deploy the fund before reviewing performance")

    if screen in ("debrief", "scorecard", "report") and not run.deployed:
        _deny("Deploy the fund first")


def set_screen(run: RunSession, screen: str) -> None:
    run.current_screen = screen
    if screen_index(screen) > screen_index(run.furthest_screen):
        run.furthest_screen = screen
    run.updated_at = now()


def rail(run: RunSession) -> list[dict]:
    reached = screen_index(run.furthest_screen)
    current = screen_index(run.current_screen)
    return [
        {
            "key": s,
            "label": SCREEN_LABELS[s],
            "state": (
                "current" if i == current else "done" if i < reached or (i <= reached and i != current) else "pending"
            ),
        }
        for i, s in enumerate(SCREEN_ORDER)
    ]
