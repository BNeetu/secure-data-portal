"""
HR Coil Monthly Quality Breakup — Dashboard Engine
===================================================
Reads the uploaded Excel file (all sheets), extracts every KPI and
chart dataset needed to reproduce the Excel dashboard exactly, returns
a JSON-serializable dict consumed by the frontend HR Coil Dashboard.

Works for any future monthly report — no hardcoded cell values.
"""
from __future__ import annotations
import io, json, re, warnings
from typing import Any, Dict, List

import pandas as pd
import numpy as np

warnings.filterwarnings("ignore")

# ── defect keyword map ─────────────────────────────────────────────────────
DEFECT_MAP = {
    'LOOSE COILING':       ['LOOSE COILING', 'LOOSE COIL'],
    'ROLL WEAR SCALE':     ['ROLL WEAR SCALE'],
    'LONGITUDINAL CRACK':  ['LONGITUDINAL CRACK'],
    'ROLLED IN SCALE':     ['ROLLED IN SCALE', 'ROLL IN SCALE'],
    'MIX GRADE':           ['MIX GRADE', 'MIX WITH'],
    'UNDER WIDTH':         ['UNDER WIDTH', 'UNDERWIDTH'],
    'OD SHIFTED':          ['OD SHIFTED', 'BODY SHIFT', 'BODY SHIFTED'],
    'METAL ENTRAPMENT':    ['METAL ENTRAPMENT', 'ALUMINA STREAK', 'SLAG ENTRAP'],
    'SEGMENT SCRATCH MARK':['SCRATCH MARK'],
    'EDGE CUT':            ['EDGE CUT'],
    'MECHANICAL PROP FAIL':['MECHANICAL', 'PROP FAIL', 'LOW YS', 'GAUGE VARIATION'],
    'NO LAMINAR COOLING':  ['NO LAMINAR', 'LOW FT'],
}

def _classify_defect(obs: Any) -> str | None:
    if not obs or str(obs).strip().rstrip('.').upper() in ('OK', 'OK ', ''):
        return None
    obs_up = str(obs).upper()
    for defect, keywords in DEFECT_MAP.items():
        if any(kw in obs_up for kw in keywords):
            return defect
    return 'OTHER'

def _safe(v: Any) -> Any:
    if isinstance(v, float) and (np.isnan(v) or np.isinf(v)):
        return 0.0
    if isinstance(v, (np.integer,)): return int(v)
    if isinstance(v, (np.floating,)): return round(float(v), 6)
    return v

def _pct_dict(series: pd.Series, total: float) -> Dict[str, dict]:
    return {
        str(k): {"qty": round(float(v), 2), "pct": round(float(v) / total * 100, 4)}
        for k, v in series.items() if float(v) > 0
    }

def process_hr_coil(raw_bytes: bytes) -> dict:
    """
    Main entry point. Returns the full dashboard data dict.
    Raises ValueError with a descriptive message if file is not an HR Coil report.
    """
    buf = io.BytesIO(raw_bytes)
    try:
        xl = pd.ExcelFile(buf)
    except Exception as e:
        raise ValueError(f"Cannot read Excel file: {e}")

    sheet_names_up = {s.upper(): s for s in xl.sheet_names}

    # Locate DATA sheet (required)
    data_sheet = next((sheet_names_up[k] for k in sheet_names_up if 'DATA' in k), None)
    if not data_sheet:
        raise ValueError("No DATA sheet found — this does not look like an HR Coil report.")

    df = pd.read_excel(buf, sheet_name=data_sheet)
    df.columns = [c.strip() for c in df.columns]

    # Required column checks
    required = ['QC STATUS', 'FINAL STATUS', 'Qty(MT)', 'MONTH']
    missing = [r for r in required if r not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df['Qty(MT)'] = pd.to_numeric(df['Qty(MT)'], errors='coerce').fillna(0)
    df['MONTH'] = pd.to_datetime(df['MONTH'], errors='coerce')
    df['month_label'] = df['MONTH'].dt.strftime('%B-%y').str.upper()
    df['QC STATUS'] = df['QC STATUS'].astype(str).str.strip()
    df['FINAL STATUS'] = df['FINAL STATUS'].astype(str).str.strip()

    total_qty = df['Qty(MT)'].sum()
    obs_col = next((c for c in df.columns if 'OBSERVATION' in c.upper()), None)

    # Mark CAT-I rows
    cat1_mask = df['QC STATUS'] == 'CATEGORY-I'
    cat1 = df[cat1_mask].copy()
    if obs_col:
        cat1['defect_type'] = cat1[obs_col].apply(_classify_defect)
    else:
        cat1['defect_type'] = 'OTHER'
    total_cat1_qty = cat1['Qty(MT)'].sum()

    # ── QC STATUS ─────────────────────────────────────────────────────────
    qc_final = df.groupby('FINAL STATUS')['Qty(MT)'].sum()
    qc_status = _pct_dict(qc_final, total_qty)

    # ── CERTIFIED GRADE ───────────────────────────────────────────────────
    cert_col = next((c for c in df.columns if 'CERTIFIED' in c.upper() and 'STANDARD' in c.upper()), None)
    if cert_col:
        cert = df.groupby(cert_col)['Qty(MT)'].sum().sort_values(ascending=False)
        certified_grade = _pct_dict(cert, total_qty)
    else:
        certified_grade = {}

    # ── THICKNESS RANGE ───────────────────────────────────────────────────
    thick_col = next((c for c in df.columns if 'THICKNESS RANGE' in c.upper()), None)
    thickness_range = _pct_dict(df.groupby(thick_col)['Qty(MT)'].sum(), total_qty) if thick_col else {}

    # ── WIDTH RANGE ───────────────────────────────────────────────────────
    width_col = next((c for c in df.columns if 'WIDTH RANGE' in c.upper()), None)
    width_range = _pct_dict(df.groupby(width_col)['Qty(MT)'].sum(), total_qty) if width_col else {}

    # ── STEEL TYPE ────────────────────────────────────────────────────────
    steel_col = next((c for c in df.columns if c.upper() == 'STEEL TYPE'), None)
    steel_type = _pct_dict(df.groupby(steel_col)['Qty(MT)'].sum(), total_qty) if steel_col else {}

    # ── MODE OF KILLING ───────────────────────────────────────────────────
    mode_col = next((c for c in df.columns if 'MODE OF KILLING' in c.upper() or 'MODE OF KILL' in c.upper()), None)
    mode_of_killing = _pct_dict(df.groupby(mode_col)['Qty(MT)'].sum(), total_qty) if mode_col else {}

    # ── CAT-I DEFECTS (Pareto) ─────────────────────────────────────────────
    defect_breakdown = cat1.groupby('defect_type')['Qty(MT)'].sum().sort_values(ascending=False)
    cat1_defects = {
        str(k): {"qty": round(float(v), 2), "pct": round(float(v) / total_qty * 100, 6)}
        for k, v in defect_breakdown.items() if k and k != 'None' and float(v) > 0
    }

    # ── CATEGORY-I GRADE WISE ─────────────────────────────────────────────
    rolled_col = next((c for c in df.columns if c.upper() == 'ROLLED GRADE'), None)
    if rolled_col:
        cat1_grade = cat1.groupby(rolled_col)['Qty(MT)'].sum().sort_values(ascending=False)
        cat1_grade_wise = {
            str(k): {"qty": round(float(v), 2), "pct": round(float(v) / max(total_cat1_qty, 1) * 100, 4)}
            for k, v in cat1_grade.items() if float(v) > 0
        }
    else:
        cat1_grade_wise = {}

    # ── MONTH-WISE CAT-I ──────────────────────────────────────────────────
    monthwise_cat1 = {}
    for month, grp in df.groupby('month_label'):
        total_m = grp['Qty(MT)'].sum()
        cat1_m = grp[grp['QC STATUS'] == 'CATEGORY-I']['Qty(MT)'].sum()
        monthwise_cat1[str(month)] = round(float(cat1_m / max(total_m, 1) * 100), 4)

    # ── MONTH-WISE DEFECTS ────────────────────────────────────────────────
    monthwise_defects = {}
    for month, grp in df.groupby('month_label'):
        total_m = grp['Qty(MT)'].sum()
        cat1_grp = grp[grp['QC STATUS'] == 'CATEGORY-I'].copy()
        if obs_col:
            cat1_grp['defect_type'] = cat1_grp[obs_col].apply(_classify_defect)
        else:
            cat1_grp['defect_type'] = 'OTHER'
        defect_m = cat1_grp.groupby('defect_type')['Qty(MT)'].sum()
        monthwise_defects[str(month)] = {
            str(k): round(float(v) / max(total_m, 1) * 100, 6)
            for k, v in defect_m.items() if k and k != 'None' and float(v) > 0
        }

    # ── GRADE DIVERSION ───────────────────────────────────────────────────
    gd_sheet = next((sheet_names_up[k] for k in sheet_names_up if 'DIVERSION' in k or 'GRADE DIV' in k), None)
    grade_diversion = {}
    if gd_sheet:
        try:
            gd_df = pd.read_excel(buf, sheet_name=gd_sheet)
            gd_df.columns = [c.strip() for c in gd_df.columns]
            gd_qty_col = next((c for c in gd_df.columns if 'QTY' in c.upper() or 'MT' in c.upper()), None)
            gd_label_col = next((c for c in gd_df.columns
                                  if 'GARDE' in c.upper() or 'GRADE DIV' in c.upper()
                                  or 'DIVERSION' in c.upper()), None)
            if gd_qty_col and gd_label_col:
                gd_df[gd_qty_col] = pd.to_numeric(gd_df[gd_qty_col], errors='coerce').fillna(0)
                gd_total = gd_df[gd_qty_col].sum()
                gd = gd_df.groupby(gd_label_col)[gd_qty_col].sum()
                grade_diversion = {
                    str(k): {"qty": round(float(v), 2), "pct": round(float(v) / max(gd_total, 1) * 100, 4)}
                    for k, v in gd.items() if float(v) > 0
                }
        except Exception:
            pass

    # ── SUMMARY METADATA ──────────────────────────────────────────────────
    months = sorted(df['month_label'].dropna().unique().tolist())
    report_month = months[-1] if months else "Unknown"

    return {
        "is_hr_coil": True,
        "report_month": report_month,
        "total_qty": round(float(total_qty), 2),
        "total_batches": int(df['BATCH'].nunique()) if 'BATCH' in df.columns else 0,
        "sections": {
            "qc_status":       qc_status,
            "certified_grade": certified_grade,
            "thickness_range": thickness_range,
            "width_range":     width_range,
            "steel_type":      steel_type,
            "mode_of_killing": mode_of_killing,
            "cat1_defects":    cat1_defects,
            "cat1_grade_wise": cat1_grade_wise,
            "grade_diversion": grade_diversion,
            "monthwise_cat1":  monthwise_cat1,
            "monthwise_defects": monthwise_defects,
        }
    }
