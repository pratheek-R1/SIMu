from __future__ import annotations

from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

# Managed Postgres providers hand out libpq URLs:
# a `postgresql://` scheme plus query parameters asyncpg does not understand.
# Rewriting them here means DATABASE_URL can be pasted in verbatim.
_LIBPQ_ONLY_PARAMS = {"sslmode", "channel_binding", "target_session_attrs", "gssencmode"}


def _split_pg_url(url: str) -> tuple[str, bool]:
    """Return (SQLAlchemy/asyncpg URL, whether the provider asked for TLS)."""
    if not url.startswith(("postgres://", "postgresql://", "postgresql+asyncpg://")):
        return url, False

    parts = urlsplit(url)
    scheme = "postgresql+asyncpg"
    params = parse_qsl(parts.query, keep_blank_values=True)
    ssl_required = any(
        k == "sslmode" and v not in ("disable", "allow") for k, v in params
    )
    kept = [(k, v) for k, v in params if k not in _LIBPQ_ONLY_PARAMS]
    return urlunsplit(
        (scheme, parts.netloc, parts.path, urlencode(kept), parts.fragment)
    ), ssl_required


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "Survivors' Illusion API"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    # Postgres. On Render this is the blueprint-injected connection string. Any
    # provider's URL is accepted verbatim: `sqlalchemy_database_url` normalises
    # the driver and strips libpq-only query parameters.
    database_url: str = "sqlite+aiosqlite:///./survivors.db"

    # Render Key Value / Redis. Optional: the API degrades to an in-process
    # cache when unset, which is correct for a single-worker dev run and wrong
    # for a multi-replica deployment.
    redis_url: str | None = None
    cache_ttl_seconds: int = 3600

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
        """Origins allowed to call the API.

        Bare hostnames are accepted and assumed HTTPS so that a platform can
        inject a service host (`survivors-web.onrender.com`) directly, and
        localhost is always allowed outside production so a developer can point
        a local client at a deployed API.
        """
        origins: list[str] = []
        for raw in self.cors_origins.split(","):
            origin = raw.strip().rstrip("/")
            if not origin:
                continue
            if "://" not in origin:
                origin = f"https://{origin}"
            if origin not in origins:
                origins.append(origin)
        if not self.is_production:
            for dev in ("http://localhost:3000", "http://127.0.0.1:3000"):
                if dev not in origins:
                    origins.append(dev)
        return origins

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def sqlalchemy_database_url(self) -> str:
        return _split_pg_url(self.database_url)[0]

    @property
    def db_ssl_required(self) -> bool:
        """True when the URL carried `sslmode`, as external Postgres URLs do.

        Render's internal URL omits it and the connection stays inside the
        private network, so this is off for the common deployment.
        """
        return _split_pg_url(self.database_url)[1]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in ("production", "prod")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
