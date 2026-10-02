"""Lazy, server-only Supabase client and private upload helpers."""
from functools import lru_cache
from typing import Optional

from app.core.config import settings


def supabase_enabled() -> bool:
    return bool(settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY)


@lru_cache(maxsize=1)
def get_supabase():
    if not supabase_enabled():
        raise RuntimeError(
            "Supabase is not configured. Set SUPABASE_URL and "
            "SUPABASE_SERVICE_ROLE_KEY in the backend environment."
        )

    from supabase import create_client

    return create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)


def upload_object(path: str, contents: bytes, content_type: str) -> None:
    get_supabase().storage.from_(settings.SUPABASE_STORAGE_BUCKET).upload(
        path,
        contents,
        file_options={
            "content-type": content_type,
            "upsert": "false",
        },
    )


def download_object(path: str) -> bytes:
    result = get_supabase().storage.from_(settings.SUPABASE_STORAGE_BUCKET).download(path)
    return result if isinstance(result, bytes) else bytes(result)


def delete_objects(paths: Optional[list[str]]) -> None:
    if paths:
        get_supabase().storage.from_(settings.SUPABASE_STORAGE_BUCKET).remove(paths)
