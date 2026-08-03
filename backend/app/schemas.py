from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default="Analyst", max_length=160)
    cohort_code: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: str
    email: str
    name: str
    role: str
    photo_url: str | None = None
    cohort_id: str | None = None


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=160)
    photo_url: str | None = None


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------
class SessionOut(BaseModel):
    id: str
    seed: int
    dataset_fingerprint: str
    status: str
    current_screen: str
    furthest_screen: str
    thesis_locked: bool
    thesis_variables: list[str] | None = None
    thesis_confidence: dict[str, int] | None = None
    falsification: str | None = None
    archive_unlocked: bool
    committee_answers: list[dict[str, Any]] | None = None
    model_weights: dict[str, float] | None = None
    picks: list[int] | None = None
    deployed: bool
    created_at: datetime
    completed_at: datetime | None = None


class SessionSummary(BaseModel):
    id: str
    status: str
    current_screen: str
    total_score: float | None = None
    band: str | None = None
    hits: int | None = None
    created_at: datetime


class ScreenRequest(BaseModel):
    screen: str


# --------------------------------------------------------------------------
# Research
# --------------------------------------------------------------------------
class SearchRequest(BaseModel):
    query: str = Field(max_length=200)


class SearchResponse(BaseModel):
    matches: list[dict[str, Any]]
    total: int
    # Set when the query tripped a provenance or ghost detector. The message is
    # the in-fiction toast the client shows.
    notice: dict[str, str] | None = None


class CompareRequest(BaseModel):
    company_ids: list[int] = Field(min_length=2, max_length=3)


class ChartViewRequest(BaseModel):
    chart_id: str = Field(max_length=64)


class ContradictionFlagRequest(BaseModel):
    company_id: int
    feature: str


class ContradictionFlagResponse(BaseModel):
    correct: bool
    message: str
    resolution: str | None = None


# --------------------------------------------------------------------------
# Thesis
# --------------------------------------------------------------------------
class ThesisRequest(BaseModel):
    variables: list[str] = Field(min_length=1, max_length=4)
    confidence: dict[str, int]
    falsification: str = Field(min_length=1, max_length=2000)

    @field_validator("confidence")
    @classmethod
    def _bounds(cls, v: dict[str, int]) -> dict[str, int]:
        for key, value in v.items():
            if not 10 <= value <= 99:
                raise ValueError(f"confidence for {key} must be between 10 and 99")
        return v


class CommitteeAnswerRequest(BaseModel):
    partner_index: int = Field(ge=0)
    answer: str = Field(min_length=1, max_length=4000)


# --------------------------------------------------------------------------
# Model
# --------------------------------------------------------------------------
class WeightsRequest(BaseModel):
    weights: dict[str, float]

    @field_validator("weights")
    @classmethod
    def _bounds(cls, v: dict[str, float]) -> dict[str, float]:
        for key, value in v.items():
            if not -3.0 <= value <= 3.0:
                raise ValueError(f"weight for {key} must be between -3 and 3")
        return v


class BacktestResponse(BaseModel):
    top_n: int
    success_rate: float
    baseline_rate: float
    sample_size: int


# --------------------------------------------------------------------------
# Deal flow
# --------------------------------------------------------------------------
class PicksRequest(BaseModel):
    picks: list[int] = Field(min_length=1, max_length=5)
