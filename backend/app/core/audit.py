"""
Audit log — append-only JSONL file recording security-relevant events:
logins (success/fail), MFA attempts, lockouts, IP blocks, uploads, role
changes, logouts. Each line is one JSON event, newest last.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.core.config import settings

_lock = threading.Lock()


def _ensure_file():
    path = Path(settings.AUDIT_LOG_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.touch()


def log_event(
    event_type: str,
    username: Optional[str] = None,
    ip: Optional[str] = None,
    detail: str = "",
    success: Optional[bool] = None,
):
    _ensure_file()
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,   # login_success | login_failed | mfa_failed | account_locked |
                                     # ip_blocked | logout | upload | role_change | suspicious_activity
        "username": username,
        "ip": ip,
        "detail": detail,
        "success": success,
    }
    with _lock:
        with open(settings.AUDIT_LOG_FILE, "a") as f:
            f.write(json.dumps(entry) + "\n")


def read_events(limit: int = 200) -> list:
    """Returns the most recent `limit` audit events, newest first."""
    _ensure_file()
    with open(settings.AUDIT_LOG_FILE, "r") as f:
        lines = f.readlines()
    events = [json.loads(line) for line in lines[-limit:] if line.strip()]
    return list(reversed(events))


def count_recent_failed_logins(username: str, minutes: int = 15) -> int:
    """Used for suspicious-activity detection — counts failed logins in the last N minutes."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    count = 0
    for e in read_events(limit=1000):
        if e["event_type"] == "login_failed" and e.get("username") == username:
            try:
                ts = datetime.fromisoformat(e["timestamp"])
                if ts >= cutoff:
                    count += 1
            except Exception:
                continue
    return count
