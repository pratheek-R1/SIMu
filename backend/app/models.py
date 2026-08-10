from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Cohort(Base):
    """A teaching cohort, bound to its own dataset seed.

    Open Issue 8 in the handoff: the prototype had a single hardcoded seed, so
    reusing it across semesters meant the reveal was common knowledge before the
    second cohort started. A cohort owns a seed; a new cohort gets a new dataset.
    """

    __tablename__ = "cohorts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    users: Mapped[list["User"]] = relationship(back_populates="cohort")


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(160), default="Analyst", nullable=False)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "student" or "facilitator". Facilitators can read cohort results.
    role: Mapped[str] = mapped_column(String(24), default="student", nullable=False)
    cohort_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cohorts.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    cohort: Mapped[Cohort | None] = relationship(back_populates="users")
    sessions: Mapped[list["Session"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Session(Base):
    """One analyst run. Everything the student does hangs off this row.

    Open Issue 6: the prototype kept all of this in browser memory, so closing
    the tab lost the scorecard and a facilitator had no way to review a cohort.
    """

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    cohort_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cohorts.id"), nullable=True
    )
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    dataset_fingerprint: Mapped[str] = mapped_column(String(32), nullable=False)

    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    current_screen: Mapped[str] = mapped_column(String(24), default="brief", nullable=False)
    furthest_screen: Mapped[str] = mapped_column(String(24), default="brief", nullable=False)

    # ---- Thesis (locked, immutable once set) ----------------------------
    thesis_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    thesis_variables: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    thesis_confidence: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)
    falsification: Mapped[str | None] = mapped_column(Text, nullable=True)
    thesis_locked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Committee ------------------------------------------------------
    committee_answers: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    deliberation_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Archive / evidence ---------------------------------------------
    archive_unlocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    archive_unlocked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ---- Model ----------------------------------------------------------
    # w1_snapshot is the thesis-seeded starting point, captured the first time
    # the model screen loads. Revision Quality is measured against it.
    w1_snapshot: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)
    model_weights: Mapped[dict[str, float] | None] = mapped_column(JSON, nullable=True)

    # ---- Deployment -----------------------------------------------------
    picks: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    # Cheque size per pick, in whole USD, keyed by deal id as a string because
    # JSON object keys cannot be integers. Null means the student never sized
    # them and the pool is split evenly -- which Capital Allocation reads as
    # "no conviction expressed" and scores neutrally rather than as a failure.
    cheque_sizes: Mapped[dict[str, int] | None] = mapped_column(JSON, nullable=True)
    deployed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fund_result: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped[User] = relationship(back_populates="sessions", lazy="selectin")
    events: Mapped[list["TelemetryEvent"]] = relationship(
        cascade="all, delete-orphan", lazy="noload"
    )
    scorecard: Mapped["Scorecard | None"] = relationship(
        back_populates="session", cascade="all, delete-orphan", uselist=False,
        lazy="noload",
    )


class TelemetryEvent(Base):
    """Append-only behavioural log.

    Every event here is produced by the server in response to an API call the
    student's actions actually required -- opening a profile IS a GET on the
    profile endpoint. The client cannot inflate a score by posting events it
    did not earn, which was structurally impossible to guarantee when telemetry
    lived in a browser-side `T` object.

    The one exception is `chart_viewed`, which needs a hover signal the server
    cannot observe. It is validated against a server-side allowlist of chart
    ids and deduplicated, so its maximum contribution is bounded.
    """

    __tablename__ = "telemetry_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(48), nullable=False, index=True)
    subject: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # Screen the student was on when the event fired -- lets a facilitator see
    # whether provenance questions came before or after the reveal.
    screen: Mapped[str | None] = mapped_column(String(24), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Scorecard(Base):
    __tablename__ = "scorecards"
    __table_args__ = (UniqueConstraint("session_id", name="uq_scorecard_session"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    total: Mapped[float] = mapped_column(Float, nullable=False)
    band: Mapped[str] = mapped_column(String(24), nullable=False)
    dimensions: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped[Session] = relationship(back_populates="scorecard")


class Report(Base):
    __tablename__ = "reports"
    # One report per session, like scorecards. Without this, a second POST to
    # /report inserts a duplicate and every subsequent read raises
    # MultipleResultsFound -- the student loses access to their own report.
    __table_args__ = (UniqueConstraint("session_id", name="uq_report_session"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("sessions.id", ondelete="CASCADE"), index=True
    )
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
