"""
Data endpoints — scoped by Department → Sub-department → Data Type, with
support for multiple uploaded files per slot (merged together for charting).

  GET    /data/departments
      → hierarchy + the 6 data types, for building the picker UI

  GET    /data/slots
      → every (department, subdepartment, data_type) slot that has files

  POST   /data/{department}/{subdepartment}/{data_type}/upload   (admin/manager)
      → adds a new file to the slot (does NOT replace existing files)

  GET    /data/{department}/{subdepartment}/{data_type}/files
      → lists files currently in this slot (id, filename, uploader, time)

  DELETE /data/{department}/{subdepartment}/{data_type}/files/{file_id}  (admin/manager)
      → removes one specific file from the slot

  DELETE /data/{department}/{subdepartment}/{data_type}/clear   (admin/manager)
      → removes ALL files from the slot

  GET    /data/{department}/{subdepartment}/{data_type}/dashboard
      → merged chart-ready dataset combining every file currently in the slot

  WS     /data/ws/live?department=X&subdepartment=Y&data_type=Z&token=T
      → live updates whenever a file is added/removed from this slot
"""
import io
import os
import time
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect, status
from fastapi.responses import FileResponse
from jose import JWTError

from app.core.audit import log_event
from app.core.config import settings
from app.core.data_store import (
    add_file_to_slot,
    broadcast_slot_update,
    clear_slot,
    get_slot_files,
    has_data,
    list_populated_slots,
    register_client,
    remove_file_from_slot,
    slot_client_count,
    unregister_client,
)
from app.core.departments import DATA_TYPES, DEPARTMENTS, DATA_TYPE_KEYS, department_list, is_valid_data_type, is_valid_department, is_valid_subdepartment, subdepartments_for
from app.core.deps import get_current_user, require_role
from app.core.security import decode_token
from app.core.user_store import get_user
from app.utils.excel_engine import process_excel, process_excel_bytes
from app.utils.hr_coil_chart_engine import generate_and_embed_charts, detect_tables
from app.utils.hr_coil_dashboard import build_hr_coil_dashboard
from app.utils.merge_engine import merge_slot_files
from app.utils.timeseries_engine import find_date_column

router = APIRouter(prefix="/data", tags=["data"])

ALLOWED_EXTENSIONS = {".xlsx", ".xls"}
MAX_FILES_PER_SLOT = 50  # sane safety ceiling so one slot can't grow unbounded forever


def _client_ip(request: Request) -> str:
    return getattr(request.state, "client_ip", request.client.host if request.client else "unknown")


def _validate_path(department: str, subdepartment: str, data_type: str):
    if not is_valid_department(department):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown department '{department}'. Valid departments: {', '.join(d['name'] for d in DEPARTMENTS)}",
        )
    if not is_valid_subdepartment(department, subdepartment):
        valid_subs = subdepartments_for(department)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown sub-department '{subdepartment}' under '{department}'. Valid options: {', '.join(valid_subs)}",
        )
    if not is_valid_data_type(data_type):
        valid_keys = [d["key"] for d in DATA_TYPES]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown data type '{data_type}'. Valid types: {', '.join(valid_keys)}",
        )


def _check_data_type_match(data_type: str, df) -> list:
    """
    Non-blocking sanity check: warns (but does not prevent) the user if the
    uploaded file's actual shape doesn't match the data type they selected.
    """
    warnings = []
    numeric_cols = df.select_dtypes(include="number").columns.tolist()

    if not numeric_cols:
        warnings.append("No numeric columns were found in this file — charts may be empty.")

    time_types = {"daily","cumulative_to_date","monthly","month_wise","cumulative_months","yearly"}
    if data_type in time_types:
        date_info = find_date_column(df)
        if date_info is None:
            warnings.append(
                f"You selected '{data_type.replace('_', ' ').title()}', but no usable date column "
                f"was found in this file. Charts will still be shown but without time-axis grouping."
            )
    else:
        date_info = None
    if date_info is not None:
        granularity = date_info["source_granularity"]
        if data_type in ("daily", "cumulative_to_date") and granularity != "day":
            warnings.append(
                f"You selected '{data_type.replace('_', ' ').title()}', but the date column "
                f"\"{date_info['column']}\" only has {granularity}-level data, not day-by-day records. "
                f"Consider selecting '{'Monthly' if granularity == 'month' else 'Yearly'}' instead."
            )
        elif data_type in ("monthly", "cumulative_months") and granularity == "year":
            warnings.append(
                f"You selected '{data_type.replace('_', ' ').title()}', but the date column "
                f"\"{date_info['column']}\" only has year-level data, not monthly records. "
                f"Consider selecting 'Yearly' instead."
            )
        elif data_type == "month_wise":
            distinct_years = date_info["parsed"].dropna().dt.year.nunique()
            if distinct_years < 2:
                warnings.append(
                    "Month-wise comparison works best with 2+ years of data in the file — "
                    "this file only spans a single year, so the year-over-year comparison will be limited."
                )
        elif data_type == "yearly":
            distinct_years = date_info["parsed"].dropna().dt.year.nunique()
            if distinct_years < 2:
                warnings.append("You selected 'Yearly', but this file only contains a single year of data.")

    return warnings


@router.get("/departments")
async def get_departments(user: dict = Depends(get_current_user)):
    """Returns the Department → Sub-department hierarchy + the 6 data-type options."""
    return {"departments": department_list(), "data_types": DATA_TYPES}


@router.get("/slots")
async def get_populated_slots(user: dict = Depends(get_current_user)):
    """Lists every department/subdepartment/data-type combination that currently has files."""
    return {"slots": list_populated_slots()}


@router.post("/{department}/{subdepartment}/{data_type}/upload", dependencies=[Depends(require_role("admin", "manager"))])
async def upload_excel(
    department: str,
    subdepartment: str,
    data_type: str,
    request: Request,
    file: UploadFile = File(...),
    uploader: dict = Depends(get_current_user),
):
    _validate_path(department, subdepartment, data_type)

    existing_files = get_slot_files(department, subdepartment, data_type)
    if len(existing_files) >= MAX_FILES_PER_SLOT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This section already has {MAX_FILES_PER_SLOT} files, the maximum allowed. Remove an old file before adding a new one.",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only .xlsx and .xls files are accepted")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds the {settings.MAX_UPLOAD_SIZE_MB}MB limit",
        )

    try:
        df = pd.read_excel(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Could not read Excel file: {e}")

    warnings = _check_data_type_match(data_type, df)

    # Use smart engine: auto-detects best sheet+header, handles merged cells, varied structures
    processed = process_excel_bytes(contents, data_type)
    if not processed["meta"]["row_count"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail=processed.get("error", "No usable data found in the uploaded file."))
    processed["selected_data_type"] = data_type
    processed["_filename"] = file.filename

    # ── HR Coil specialized dashboard ───────────────────────────────────────
    # Triggered when filename starts with "HR COIL MONTH WISE QUALITY BREAK UP"
    import re as _re
    _fname_upper = file.filename.upper().replace("_", " ").replace("-", " ")
    _is_hr_coil  = bool(_re.search(r"HR.COIL.MONTH.WISE.QUALITY.BREAK.UP", _fname_upper))
    if _is_hr_coil:
        try:
            hr_dash = build_hr_coil_dashboard(contents)
            # sections is a LIST in the new engine (not a dict)
            _sections = hr_dash.get("sections", [])
            _iter = _sections if isinstance(_sections, list) else _sections.values()
            _has_data = any(
                len(sec.get("data", [])) > 0
                for sec in _iter
                if isinstance(sec.get("data"), list)
            )
            if hr_dash and _has_data:
                processed["hr_coil_dashboard"] = hr_dash
                processed["render_mode"] = "hr_coil"
            else:
                processed["render_mode"] = "generic"
        except Exception as _e:
            import sys
            print(f"[hr_coil] dashboard build failed: {_e}", file=sys.stderr)
            processed["render_mode"] = "generic"
    else:
        processed["render_mode"] = "generic"

    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    safe_name = f"{int(time.time())}_{department}_{subdepartment}_{data_type}_{Path(file.filename).name}".replace(" ", "_").replace("/", "-")
    save_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    with open(save_path, "wb") as f:
        f.write(contents)

    file_id = add_file_to_slot(department, subdepartment, data_type, processed, file.filename, uploader["username"], save_path)

    log_event(
        "upload",
        uploader["username"],
        _client_ip(request),
        f"Uploaded '{file.filename}' to {department} / {subdepartment} / {data_type} "
        f"({processed['meta']['row_count']} rows, {processed['meta']['column_count']} cols, file {len(existing_files)+1} of slot)"
        + (f" — {len(warnings)} warning(s)" if warnings else ""),
        success=True,
    )

    await broadcast_slot_update(department, subdepartment, data_type)

    return {
        "message": f"File added. This section now has {len(existing_files) + 1} file(s).",
        "file_id": file_id,
        "department": department, "subdepartment": subdepartment, "data_type": data_type,
        "filename": file.filename,
        "rows": processed["meta"]["row_count"],
        "columns": processed["meta"]["columns"],
        "warnings": warnings,
        "total_files_in_slot": len(existing_files) + 1,
        "broadcast_to_clients": slot_client_count(department, subdepartment, data_type),
    }


@router.get("/{department}/{subdepartment}/{data_type}/files")
async def list_files(department: str, subdepartment: str, data_type: str, user: dict = Depends(get_current_user)):
    _validate_path(department, subdepartment, data_type)
    files = get_slot_files(department, subdepartment, data_type)
    return {
        "files": [
            {"id": f["id"], "filename": f["filename"], "uploaded_by": f["uploaded_by"], "uploaded_at": f["uploaded_at"],
             "rows": f["data"]["meta"]["row_count"] if f.get("data") else None}
            for f in files
        ]
    }


@router.delete("/{department}/{subdepartment}/{data_type}/files/{file_id}", dependencies=[Depends(require_role("admin", "manager"))])
async def delete_file(department: str, subdepartment: str, data_type: str, file_id: str, request: Request, user: dict = Depends(get_current_user)):
    _validate_path(department, subdepartment, data_type)
    removed = remove_file_from_slot(department, subdepartment, data_type, file_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in this section")
    log_event("file_removed", user["username"], _client_ip(request), f"Removed a file from {department} / {subdepartment} / {data_type}", success=True)
    await broadcast_slot_update(department, subdepartment, data_type)
    return {"message": "File removed"}


@router.get("/{department}/{subdepartment}/{data_type}/dashboard")
async def get_dashboard(department: str, subdepartment: str, data_type: str, user: dict = Depends(get_current_user)):
    _validate_path(department, subdepartment, data_type)
    files = get_slot_files(department, subdepartment, data_type)
    if not files:
        return {
            "has_data": False, "data": None, "file_count": 0,
            "department": department, "subdepartment": subdepartment, "data_type": data_type,
        }

    if len(files) == 1:
        merged = dict(files[0]["data"])
        merged["_merge_info"] = {"files_merged": 1, "files_skipped": [], "total_files_in_slot": 1}
    else:
        merged = merge_slot_files(files)
        if merged is None:
            # All files' source paths expired/missing — fall back to the most recent file's
            # already-processed data so the dashboard doesn't go blank.
            merged = dict(files[-1]["data"])
            merged["_merge_info"] = {"files_merged": 1, "files_skipped": [f["filename"] for f in files[:-1]], "total_files_in_slot": len(files)}

    return {
        "has_data": True,
        "data": merged,
        "file_count": len(files),
        "department": department, "subdepartment": subdepartment, "data_type": data_type,
    }



@router.get("/{department}/{subdepartment}/{data_type}/dashboard/{file_id}")
async def get_file_dashboard(department: str, subdepartment: str, data_type: str, file_id: str, user: dict = Depends(get_current_user)):
    """Returns the processed dashboard data for ONE specific uploaded file by its ID."""
    _validate_path(department, subdepartment, data_type)
    files = get_slot_files(department, subdepartment, data_type)
    match = next((f for f in files if f["id"] == file_id), None)
    if not match:
        raise HTTPException(status_code=404, detail=f"File '{file_id}' not found in this slot.")
    return {
        "has_data": True,
        "data": match["data"],
        "file_id": file_id,
        "filename": match["filename"],
        "uploaded_by": match["uploaded_by"],
        "uploaded_at": match["uploaded_at"],
        "file_count": len(files),
        "department": department,
        "subdepartment": subdepartment,
        "data_type": data_type,
    }


@router.delete("/{department}/{subdepartment}/{data_type}/clear", dependencies=[Depends(require_role("admin", "manager"))])
async def clear_dataset(department: str, subdepartment: str, data_type: str, request: Request, user: dict = Depends(get_current_user)):
    _validate_path(department, subdepartment, data_type)
    clear_slot(department, subdepartment, data_type)
    log_event("data_cleared", user["username"], _client_ip(request), f"Cleared all files from {department} / {subdepartment} / {data_type}", success=True)
    await broadcast_slot_update(department, subdepartment, data_type)
    return {"message": f"All files cleared for {department} / {subdepartment} / {data_type}"}



@router.get("/{department}/{subdepartment}/{data_type}/files/{file_id}/download-charts")
async def download_chart_excel(
    department: str, subdepartment: str, data_type: str, file_id: str,
    user: dict = Depends(get_current_user),
):
    """Download the chart-enhanced Excel file for a specific uploaded file."""
    _validate_path(department, subdepartment, data_type)
    from app.core.data_store import get_slot_files
    files = get_slot_files(department, subdepartment, data_type)
    match = next((f for f in files if f["id"] == file_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="File not found.")
    chart_path = match.get("chart_path")
    if not chart_path or not os.path.exists(chart_path):
        raise HTTPException(status_code=404,
            detail="Chart-enhanced file not available. Re-upload the file to generate charts.")
    dl_name = Path(match["filename"]).stem + "_with_charts.xlsx"
    return FileResponse(chart_path, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        filename=dl_name)


# ── WebSocket for live dashboard updates, scoped to one slot ──
@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket, department: str = "", subdepartment: str = "", data_type: str = "", token: str = ""):
    if not is_valid_department(department) or not is_valid_subdepartment(department, subdepartment) or not is_valid_data_type(data_type):
        await websocket.close(code=4400)
        return

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.close(code=4401)
            return
        username = payload.get("sub")
        user = get_user(username)
        if not user:
            await websocket.close(code=4401)
            return
    except JWTError:
        await websocket.close(code=4401)
        return

    await websocket.accept()
    register_client(websocket, department, subdepartment, data_type)

    try:
        files = get_slot_files(department, subdepartment, data_type)
        import json
        await websocket.send_text(json.dumps({
            "type": "slot_updated", "department": department, "subdepartment": subdepartment,
            "data_type": data_type, "file_count": len(files),
        }))
    except Exception:
        pass

    try:
        while True:
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        unregister_client(websocket, department, subdepartment, data_type)
    except Exception:
        unregister_client(websocket, department, subdepartment, data_type)
