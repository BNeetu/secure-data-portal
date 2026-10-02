"""
Background watcher: if a previously-uploaded Excel file is edited and
re-saved directly on disk (e.g. a manager has it open in Excel and presses
Ctrl+S), this detects the change, reprocesses just that one file, and
broadcasts a lightweight "slot changed" signal so connected clients refetch
the merged dashboard — no manual re-upload needed for that workflow.

Iterates every populated slot and every file within it, since a slot can
now hold multiple files.

Also sweeps /data/uploads and deletes files older than UPLOAD_RETENTION_HOURS,
since per requirements we don't retain historical uploads indefinitely.
"""
import asyncio
import os
import time
from pathlib import Path

import pandas as pd

from app.core.config import settings
from app.core.data_store import broadcast_slot_update, get_slot_files, list_populated_slots, update_file_data
from app.utils.excel_engine import process_excel

POLL_INTERVAL_SECONDS = 2

# Tracks last-seen mtime per individual file id so we only react to genuine changes
_last_mtimes: dict = {}


async def watch_for_direct_edits():
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)

        for slot_info in list_populated_slots():
            department = slot_info["department"]
            subdepartment = slot_info["subdepartment"]
            data_type = slot_info["data_type"]
            files = get_slot_files(department, subdepartment, data_type)

            changed = False
            for f in files:
                path = f.get("file_path")
                if not path or not os.path.exists(path):
                    continue

                try:
                    mtime = os.path.getmtime(path)
                except FileNotFoundError:
                    continue

                tracking_key = f["id"]
                last_mtime = _last_mtimes.get(tracking_key)

                if last_mtime is None:
                    _last_mtimes[tracking_key] = mtime
                    continue

                if mtime != last_mtime:
                    _last_mtimes[tracking_key] = mtime
                    await asyncio.sleep(0.5)  # let the editor finish writing
                    try:
                        df = pd.read_excel(path)
                        processed = process_excel(df)
                        processed["selected_data_type"] = data_type
                        update_file_data(department, subdepartment, data_type, f["id"], processed)
                        changed = True
                        print(f"[live-reload] Detected direct edit of {path} ({department}/{subdepartment}/{data_type}).")
                    except Exception as e:
                        print(f"[live-reload] Failed to reprocess {path}: {e}")

            if changed:
                await broadcast_slot_update(department, subdepartment, data_type)


async def sweep_old_uploads():
    """Deletes uploaded files older than the retention window. Runs forever."""
    while True:
        await asyncio.sleep(60 * 30)  # every 30 minutes
        retention_seconds = settings.UPLOAD_RETENTION_HOURS * 3600
        upload_dir = Path(settings.UPLOAD_DIR)
        if not upload_dir.exists():
            continue
        now = time.time()
        for f in upload_dir.iterdir():
            if f.is_file() and (now - f.stat().st_mtime) > retention_seconds:
                try:
                    f.unlink()
                    print(f"[cleanup] Deleted expired upload: {f.name}")
                except Exception:
                    pass
