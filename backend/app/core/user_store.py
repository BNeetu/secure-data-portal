"""
Lightweight user store backed by a JSON file (no database, per requirements).

users.json structure:
{
  "users": [
    {
      "username": "admin",
      "password_hash": "<bcrypt hash>",
      "role": "admin",          # admin | manager | viewer
      "totp_secret": "<base32>",
      "mfa_enabled": true,
      "failed_attempts": 0,
      "locked_until": null,     # ISO timestamp or null
      "last_login": null,
      "created_at": "..."
    }
  ]
}

File writes are guarded by a process-wide lock since this is a simple
single-instance deployment (no DB transactions available).
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import settings

_lock = threading.Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_file():
    path = Path(settings.USERS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(json.dumps({"users": []}, indent=2))


def _read() -> dict:
    _ensure_file()
    with open(settings.USERS_FILE, "r") as f:
        return json.load(f)


def _write(data: dict):
    with open(settings.USERS_FILE, "w") as f:
        json.dump(data, f, indent=2)


def get_user(username: str) -> Optional[dict]:
    data = _read()
    for u in data["users"]:
        if u["username"].lower() == username.lower():
            return u
    return None


def list_users() -> list:
    return _read()["users"]


def create_user(username: str, password_hash: str, role: str, totp_secret: str) -> dict:
    with _lock:
        data = _read()
        if any(u["username"].lower() == username.lower() for u in data["users"]):
            raise ValueError(f"User '{username}' already exists")
        user = {
            "username": username,
            "password_hash": password_hash,
            "role": role,
            "totp_secret": totp_secret,
            "mfa_enabled": True,
            "mfa_verified": False,  # becomes True once user confirms first TOTP code
            "failed_attempts": 0,
            "locked_until": None,
            "last_login": None,
            "created_at": _now_iso(),
        }
        data["users"].append(user)
        _write(data)
        return user


def update_user(username: str, **fields):
    with _lock:
        data = _read()
        for u in data["users"]:
            if u["username"].lower() == username.lower():
                u.update(fields)
                _write(data)
                return u
        raise ValueError(f"User '{username}' not found")


def record_failed_attempt(username: str) -> int:
    """Increments failed_attempts; locks account if threshold reached. Returns new count."""
    with _lock:
        data = _read()
        for u in data["users"]:
            if u["username"].lower() == username.lower():
                u["failed_attempts"] = u.get("failed_attempts", 0) + 1
                if u["failed_attempts"] >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
                    from datetime import timedelta
                    lock_until = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCOUNT_LOCKOUT_MINUTES)
                    u["locked_until"] = lock_until.isoformat()
                _write(data)
                return u["failed_attempts"]
        return 0


def reset_failed_attempts(username: str):
    update_user(username, failed_attempts=0, locked_until=None, last_login=_now_iso())


def is_locked(user: dict) -> bool:
    locked_until = user.get("locked_until")
    if not locked_until:
        return False
    try:
        until = datetime.fromisoformat(locked_until)
        return datetime.now(timezone.utc) < until
    except Exception:
        return False
