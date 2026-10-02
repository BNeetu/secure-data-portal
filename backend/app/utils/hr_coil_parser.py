"""
HR Coil Monthly Report Parser
==============================
Reads ANY HR Coil monthly Excel file and extracts every table into a
structured dict that the frontend dashboard can render directly.

Tables detected dynamically — no hardcoded cell references.
Works for any month's report regardless of row count or table position.
"""
import io, re, math, warnings
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import openpyxl

warnings.filterwarnings("ignore")

PCT_HEADERS  = {"%WRP", "% WRP", "%", "PERCENTAGE", "PCT", "% SHARE"}
SKIP_LABELS  = {"grand total", "total", "row labels"}
QTY_HEADERS  = {"sum of qty(mt)", "sum of qty", "nos coils", "count of batch", "qty(mt)"}

def _v(grid, r, c):
    return grid.get((r, c))

def _is_pct_hdr(v):
    return str(v).strip().upper() in PCT_HEADERS if v else False

def _is_skip(v):
    return str(v).strip().lower() in SKIP_LABELS if v else False

def _is_title(v):
    if v is None or isinstance(v, (int, float)): return False
    s = str(v).strip()
    return bool(s) and s.lower() not in SKIP_LABELS and not _is_pct_hdr(v) and str(s).upper() not in QTY_HEADERS

def _pct(v) -> Optional[float]:
    """Convert raw cell value to a 0-100 percentage."""
    if v is None: return None
    try:
        f = float(v)
        if f > 1.0: return None   # already >100% means it's a raw qty, skip
        return round(f * 100, 4)
    except (TypeError, ValueError):
        return None


def _extract_table(grid, hdr_row, label_col, pct_col, max_row) -> List[Dict]:
    """Extract data rows for one table block."""
    rows = []
    r = hdr_row + 1
    while r <= max_row:
        lv = _v(grid, r, label_col)
        pv = _v(grid, r, pct_col)
        if lv is None and pv is None:
            break
        if lv is not None and not _is_skip(lv):
            pct = _pct(pv)
            if pct is not None:
                rows.append({"label": str(lv).strip(), "pct": pct})
        elif lv is not None and _is_skip(lv):
            break
        r += 1
    return rows


def _find_title(grid, hdr_row, label_col, pct_col) -> str:
    """Find the nearest title above or at the header row."""
    # Check same row at label_col
    v = _v(grid, hdr_row, label_col)
    if _is_title(v): return str(v).strip()
    # Scan upward
    for tr in range(hdr_row - 1, max(0, hdr_row - 5), -1):
        for c in range(label_col, pct_col + 1):
            v = _v(grid, tr, c)
            if _is_title(v): return str(v).strip()
    return f"Table (row {hdr_row})"


def parse_summary_sheet(ws) -> Dict[str, Any]:
    """Parse the SUMMARY sheet and return all table data."""
    grid: Dict[Tuple, Any] = {}
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                grid[(cell.row, cell.column)] = cell.value

    max_row = ws.max_row
    pct_cells = sorted([(r, c) for (r, c), v in grid.items() if _is_pct_hdr(v)])

    tables = {}
    seen = set()

    for (hdr_row, pct_col) in pct_cells:
        if (hdr_row, pct_col) in seen: continue
        seen.add((hdr_row, pct_col))

        # Find label col: leftmost non-qty, non-pct col at header row
        label_col = None
        for c in range(pct_col - 1, 0, -1):
            v = _v(grid, hdr_row, c)
            if v is not None and not _is_pct_hdr(v) and str(v).upper() not in QTY_HEADERS:
                label_col = c
                break
        if label_col is None: continue

        title = _find_title(grid, hdr_row, label_col, pct_col)
        rows  = _extract_table(grid, hdr_row, label_col, pct_col, max_row)
        if not rows: continue

        # Normalize title to a key
        key = re.sub(r'\W+', '_', title.upper()).strip('_')
        tables[key] = {"title": title, "rows": rows}

    return tables


def parse_grade_diversion_sheet(ws) -> Dict[str, Any]:
    """Parse GRADE DIVERSION sheet — may contain monthwise trend data."""
    grid: Dict[Tuple, Any] = {}
    for row in ws.iter_rows():
        for cell in row:
            if cell.value is not None:
                grid[(cell.row, cell.column)] = cell.value

    if not grid: return {}

    max_row = ws.max_row
    max_col = ws.max_column

    # Detect headers in first few rows
    tables = {}

    # Look for monthwise CAT-I data: rows with month labels and % values
    month_pattern = re.compile(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)', re.I)
    monthwise = {}
    defect_trend = defaultdict(dict)

    for r in range(1, max_row + 1):
        row_vals = {c: grid.get((r, c)) for c in range(1, max_col + 1) if grid.get((r, c)) is not None}
        if not row_vals: continue

        first = str(list(row_vals.values())[0]).strip() if row_vals else ""

        # Detect month label rows in trend tables
        if month_pattern.search(first):
            for c, v in row_vals.items():
                if isinstance(v, (int, float)) and 0 <= float(v) <= 1:
                    hdr = grid.get((1, c)) or grid.get((2, c)) or f"Col{c}"
                    defect_trend[str(hdr)][first] = round(float(v) * 100, 4)

    if defect_trend:
        tables["DEFECT_TREND"] = {"title": "Major Defects Trend", "data": dict(defect_trend)}

    # Parse simple tables with %WRP columns
    pct_cells = sorted([(r, c) for (r, c), v in grid.items() if _is_pct_hdr(v)])
    seen = set()
    for (hdr_row, pct_col) in pct_cells:
        if (hdr_row, pct_col) in seen: continue
        seen.add((hdr_row, pct_col))
        label_col = None
        for c in range(pct_col - 1, 0, -1):
            v = grid.get((hdr_row, c))
            if v and not _is_pct_hdr(v) and str(v).upper() not in QTY_HEADERS:
                label_col = c; break
        if label_col is None: continue
        title = _find_title(grid, hdr_row, label_col, pct_col)
        rows  = _extract_table(grid, hdr_row, label_col, pct_col, max_row)
        if not rows: continue
        key = re.sub(r'\W+', '_', title.upper()).strip('_')
        tables[key] = {"title": title, "rows": rows}

    return tables


def parse_hr_coil_excel(raw_bytes: bytes) -> Dict[str, Any]:
    """
    Main entry point.
    Returns a dict with all parsed table data ready for the dashboard.
    """
    wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)

    result = {
        "sheets": wb.sheetnames,
        "summary": {},
        "grade_diversion": {},
        "month": None,
        "year": None,
    }

    # Detect month/year from sheet names or title cells
    for name in wb.sheetnames:
        m = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[\s\-]*(\d{2,4})', name, re.I)
        if m:
            result["month"] = m.group(1).capitalize()
            result["year"]  = m.group(2)

    if "SUMMARY" in wb.sheetnames:
        result["summary"] = parse_summary_sheet(wb["SUMMARY"])

    for name in wb.sheetnames:
        if "grade" in name.lower() or "diversion" in name.lower():
            result["grade_diversion"] = parse_grade_diversion_sheet(wb[name])
            break

    return result
