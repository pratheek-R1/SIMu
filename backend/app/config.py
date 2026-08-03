from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Survivors' Illusion API"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # Supabase PostgreSQL. Use the session-pooler connection string in
    # production; asyncpg does not speak the transaction pooler's protocol for
    # prepared statements.
    database_url: str = "sqlite+aiosqlite:///./survivors.db"

    # Upstash Redis (rediss://). Optional: the API degrades to an in-process
    # cache when unset, which is correct for a single-worker dev run and wrong
    # for a multi-replica deployment.
    redis_url: str | None = None
    cache_ttl_seconds: int = 3600

    # Supabase Storage
    supabase_url: str | None = None
    supabase_service_key: str | None = None
    supabase_report_bucket: str = "reports"

    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 12

    cors_origins: str = "http://localhost:3000"

    # Currency. The prototype hardcoded 83 inside profile.js; it is config here
    # so a deployment can change it without a code change.
    inr_rate: float = 83.0

    # Every cohort gets its own seed. Reusing a seed across semesters means the
    # reveal is common knowledge before the second cohort starts.
    default_cohort_seed: int = 20260729

    # Deliberation gate between the committee and the archive.
    deliberation_seconds: int = 15

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
