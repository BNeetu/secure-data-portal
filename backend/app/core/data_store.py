"""
Supabase-backed cloud dataset store with an in-memory local fallback.

Keyed by (department, sub_department, data_type). Each slot can now hold
MULTIPLE uploaded files (not just the latest one) — every successful upload
APPENDS a new file entry to that slot's list, rather than replacing it.
This lets users build up a fuller picture over time (e.g. uploading several
months of "Daily" reports one at a time) and still see all of them charted
together.

Each file entry stores its own processed dataset. The frontend can view
files individually or the slot can expose a "merged" view that combines
every file's records into one dashboard (see merge_slot_files below).
"""
import threading
import time
import uuid
from typing import Optional, Set

from fastapi import WebSocket

from app.core.config import settings
from app.core.departments import slot_key
from app.core.supabase_client import delete_objects, get_supabase, supabase_enabled

_lock = threading.Lock()

# slot_key -> { "files": [ {id, data, filename, uploaded_by, uploaded_at, file_path}, ... ] }
_slots: dict = {}

# slot_key -> set of WebSocket connections currently watching that slot
_subscribers: dict = {}


def _empty_slot() -> dict:
    return {"files": []}


def _purge_expired_supabase_files():
    client = get_supabase()
    cutoff = time.time() - settings.UPLOAD_RETENTION_HOURS * 3600
    result = client.table("portal_files").select("id,file_path").lt("uploaded_at", cutoff).execute()
    if not result.data:
        return
    delete_objects([row["file_path"] for row in result.data if row.get("file_path")])
    client.table("portal_files").delete().in_("id", [row["id"] for row in result.data]).execute()


def add_file_to_slot(department: str, subdepartment: str, data_type: str,
                      data: dict, filename: str, uploaded_by: str, file_path: Optional[str] = None) -> str:
    """Appends a new file to the slot. Returns the new file's unique id."""
    if supabase_enabled():
        file_id = uuid.uuid4().hex[:12]
        get_supabase().table("portal_files").insert({
            "id": file_id,
            "department": department,
            "subdepartment": subdepartment,
            "data_type": data_type,
            "data": data,
            "filename": filename,
            "uploaded_by": uploaded_by,
            "uploaded_at": time.time(),
            "file_path": file_path or "",
        }).execute()
        return file_id

    with _lock:
        key = slot_key(department, subdepartment, data_type)
        if key not in _slots:
            _slots[key] = _empty_slot()
        file_id = uuid.uuid4().hex[:12]
        _slots[key]["files"].append({
            "id": file_id,
            "data": data,
            "filename": filename,
            "uploaded_by": uploaded_by,
            "uploaded_at": time.time(),
            "file_path": file_path,
        })
        return file_id


def get_slot_files(department: str, subdepartment: str, data_type: str) -> list:
    if supabase_enabled():
        _purge_expired_supabase_files()
        return (
            get_supabase().table("portal_files").select("*")
            .eq("department", department).eq("subdepartment", subdepartment)
            .eq("data_type", data_type).order("uploaded_at").execute().data
        )

    with _lock:
        key = slot_key(department, subdepartment, data_type)
        return list(_slots.get(key, _empty_slot())["files"])


def remove_file_from_slot(department: str, subdepartment: str, data_type: str, file_id: str) -> bool:
    """Removes one specific file from a slot. Returns True if it was found and removed."""
    if supabase_enabled():
        client = get_supabase()
        result = (
            client.table("portal_files").select("file_path").eq("department", department)
            .eq("subdepartment", subdepartment).eq("data_type", data_type)
            .eq("id", file_id).limit(1).execute()
        )
        if not result.data:
            return False
        delete_objects([result.data[0]["file_path"]])
        client.table("portal_files").delete().eq("id", file_id).execute()
        return True

    with _lock:
        key = slot_key(department, subdepartment, data_type)
        slot = _slots.get(key)
        if not slot:
            return False
        before = len(slot["files"])
        slot["files"] = [f for f in slot["files"] if f["id"] != file_id]
        return len(slot["files"]) < before


def clear_slot(department: str, subdepartment: str, data_type: str):
    if supabase_enabled():
        client = get_supabase()
        result = (
            client.table("portal_files").select("id,file_path")
            .eq("department", department).eq("subdepartment", subdepartment)
            .eq("data_type", data_type).execute()
        )
        delete_objects([row["file_path"] for row in result.data if row.get("file_path")])
        client.table("portal_files").delete().eq("department", department).eq(
            "subdepartment", subdepartment
        ).eq("data_type", data_type).execute()
        return

    with _lock:
        key = slot_key(department, subdepartment, data_type)
        _slots[key] = _empty_slot()


def has_data(department: str, subdepartment: str, data_type: str) -> bool:
    if supabase_enabled():
        result = (
            get_supabase().table("portal_files").select("id")
            .eq("department", department).eq("subdepartment", subdepartment)
            .eq("data_type", data_type).limit(1).execute()
        )
        return bool(result.data)

    with _lock:
        key = slot_key(department, subdepartment, data_type)
        slot = _slots.get(key)
        return slot is not None and len(slot["files"]) > 0


def list_populated_slots() -> list:
    """Returns [{department, subdepartment, data_type, file_count}, ...] for every slot with data."""
    if supabase_enabled():
        _purge_expired_supabase_files()
        rows = get_supabase().table("portal_files").select(
            "department,subdepartment,data_type,uploaded_at"
        ).execute().data
        grouped = {}
        for row in rows:
            key = (row["department"], row["subdepartment"], row["data_type"])
            slot = grouped.setdefault(key, {"file_count": 0, "latest_upload": 0})
            slot["file_count"] += 1
            slot["latest_upload"] = max(slot["latest_upload"], row["uploaded_at"])
        return [
            {
                "department": department,
                "subdepartment": subdepartment,
                "data_type": data_type,
                **values,
            }
            for (department, subdepartment, data_type), values in grouped.items()
        ]

    with _lock:
        out = []
        for key, slot in _slots.items():
            if slot["files"]:
                department, subdepartment, data_type = key.split("::", 2)
                out.append({
                    "department": department,
                    "subdepartment": subdepartment,
                    "data_type": data_type,
                    "file_count": len(slot["files"]),
                    "latest_upload": max(f["uploaded_at"] for f in slot["files"]),
                })
        return out


def get_file_for_watcher(department: str, subdepartment: str, data_type: str, file_id: str) -> Optional[dict]:
    if supabase_enabled():
        result = (
            get_supabase().table("portal_files").select("*").eq("department", department)
            .eq("subdepartment", subdepartment).eq("data_type", data_type)
            .eq("id", file_id).limit(1).execute()
        )
        return result.data[0] if result.data else None

    with _lock:
        key = slot_key(department, subdepartment, data_type)
        slot = _slots.get(key)
        if not slot:
            return None
        for f in slot["files"]:
            if f["id"] == file_id:
                return dict(f)
        return None


def update_file_data(department: str, subdepartment: str, data_type: str, file_id: str, new_data: dict):
    """Used by the file watcher when a file is edited+resaved on disk."""
    if supabase_enabled():
        get_supabase().table("portal_files").update({
            "data": new_data,
            "uploaded_at": time.time(),
        }).eq("department", department).eq("subdepartment", subdepartment).eq(
            "data_type", data_type
        ).eq("id", file_id).execute()
        return

    with _lock:
        key = slot_key(department, subdepartment, data_type)
        slot = _slots.get(key)
        if not slot:
            return
        for f in slot["files"]:
            if f["id"] == file_id:
                f["data"] = new_data
                f["uploaded_at"] = time.time()
                return


# ── WebSocket subscription (per-slot, so broadcasts stay small and targeted) ──
def register_client(ws: WebSocket, department: str, subdepartment: str, data_type: str):
    key = slot_key(department, subdepartment, data_type)
    _subscribers.setdefault(key, set()).add(ws)


def unregister_client(ws: WebSocket, department: str, subdepartment: str, data_type: str):
    key = slot_key(department, subdepartment, data_type)
    if key in _subscribers:
        _subscribers[key].discard(ws)


def _slot_summary(department: str, subdepartment: str, data_type: str) -> dict:
    files = get_slot_files(department, subdepartment, data_type)
    return {
        "files": [
            {"id": f["id"], "filename": f["filename"], "uploaded_by": f["uploaded_by"], "uploaded_at": f["uploaded_at"]}
            for f in files
        ],
    }


async def broadcast_slot_update(department: str, subdepartment: str, data_type: str):
    import json
    key = slot_key(department, subdepartment, data_type)
    clients = _subscribers.get(key)
    if not clients:
        return
    summary = _slot_summary(department, subdepartment, data_type)
    message = json.dumps({
        "type": "slot_updated",
        "department": department, "subdepartment": subdepartment, "data_type": data_type,
        "file_count": len(summary["files"]),
    })
    dead = set()
    for ws in list(clients):
        try:
            await ws.send_text(message)
        except Exception:
            dead.add(ws)
    clients.difference_update(dead)


def slot_client_count(department: str, subdepartment: str, data_type: str) -> int:
    key = slot_key(department, subdepartment, data_type)
    return len(_subscribers.get(key, set()))
