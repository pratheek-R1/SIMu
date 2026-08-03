"""Supabase Storage upload for generated investment reports.

Degrades gracefully: when Supabase is not configured the report HTML is still
persisted in Postgres and served from the API, so a dev run is fully functional
without object storage.
"""

from __future__ import annotations

import httpx

from .config import settings


async def upload_report(session_id: str, html: str) -> tuple[str | None, str | None]:
    """Return (storage_path, public_url). Both None when storage is unconfigured."""
    if not settings.supabase_url or not settings.supabase_service_key:
        return None, None

    path = f"{session_id}/investment-report.html"
    base = settings.supabase_url.rstrip("/")
    url = f"{base}/storage/v1/object/{settings.supabase_report_bucket}/{path}"

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            url,
            content=html.encode("utf-8"),
            headers={
                "Authorization": f"Bearer {settings.supabase_service_key}",
                "Content-Type": "text/html; charset=utf-8",
                "x-upsert": "true",
            },
        )
        if resp.status_code >= 400:
            # A failed upload must not lose the student's report -- the caller
            # has already persisted the HTML.
            return None, None

    public_url = (
        f"{base}/storage/v1/object/public/{settings.supabase_report_bucket}/{path}"
    )
    return path, public_url
