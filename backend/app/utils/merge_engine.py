"""
Merges multiple uploaded Excel files within the same (department,
sub-department, data_type) slot into a single combined dataset for charting.

Re-reads each file's raw bytes from disk and concatenates the actual rows,
then runs the combined dataframe through the normal process_excel pipeline
— this is the only correct way to merge: re-summing combined raw rows
produces correct totals, whereas trying to add together two already-computed
KPI dictionaries would silently double-count or misalign categories.

If files have different/incompatible column structures, columns are merged
on their union (pandas concat default) and missing values become NaN —
process_excel already handles NaN safely throughout.
"""
import pandas as pd

from app.utils.excel_engine import process_excel


def merge_slot_files(files: list) -> dict:
    """
    files: list of {id, filename, file_path, ...} dicts from data_store.
    Returns the merged process_excel() output, or None if no files have a
    readable file_path (e.g. all expired past the retention window).
    """
    frames = []
    skipped = []
    for f in files:
        path = f.get("file_path")
        if not path:
            skipped.append(f["filename"])
            continue
        try:
            df = pd.read_excel(path)
            df["__source_file__"] = f["filename"]  # provenance, dropped before charting below
            frames.append(df)
        except Exception:
            skipped.append(f["filename"])
            continue

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True, sort=False)
    source_col = combined.pop("__source_file__")  # keep available for provenance, not used in main charts yet

    result = process_excel(combined)
    result["_merge_info"] = {
        "files_merged": len(frames),
        "files_skipped": skipped,
        "total_files_in_slot": len(files),
    }
    return result
