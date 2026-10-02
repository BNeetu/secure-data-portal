"""
Universal Excel → Dashboard Engine
====================================
Works on ANY uploaded Excel file regardless of structure by:
  1. Trying every sheet + every likely header row and scoring each combination
  2. Cleaning column names (strips spaces/newlines, resolves duplicates, drops Unnamed)
  3. Coercing mixed-type columns to numeric where sensible
  4. Detecting: numeric, categorical, date, percentage, boolean, text columns
  5. Auto-selecting the best chart type per column based on cardinality + data shape
  6. Building KPIs, breakdowns, top-N, scatter/correlation, time-series
  7. Never returning an empty dashboard — always finds something to visualize
"""
import math
import re
import warnings
from typing import Any, Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

MAX_CATEGORY_VALUES   = 50   # categorical columns with more unique vals become text (too noisy)
MIN_CATEGORY_VALUES   = 2    # need at least 2 distinct values to make a chart
MAX_RECORDS_RETURNED  = 2000
MAX_NUMERIC_KPI       = 10
MAX_CATEGORICAL_CHARTS= 12
MAX_TOP_N             = 10
MAX_SCATTER_PAIRS     = 3


# ── helpers ──────────────────────────────────────────────────────────────────

def _clean(val: Any) -> Any:
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        v = float(val)
        return round(v, 6)
    if isinstance(val, (pd.Timestamp,)):
        return val.isoformat()
    if isinstance(val, (np.bool_,)):
        return bool(val)
    return val


def _humanize(name: str) -> str:
    """Convert raw column names to readable labels."""
    s = str(name).strip()
    # Remove newlines / excess whitespace
    s = re.sub(r'\s+', ' ', s.replace('\n', ' ').replace('\r', ' '))
    # Strip trailing spaces around unit notations
    s = s.strip()
    # Title-case if all-upper
    if s.isupper() and len(s) > 3:
        s = s.title()
    return s


def _clean_col_name(name: str) -> str:
    s = str(name).strip()
    s = re.sub(r'\s+', ' ', s.replace('\n', ' ').replace('\r', ' '))
    return s.strip()


def _score_df(df: pd.DataFrame) -> float:
    """Score a candidate dataframe — higher = better data table."""
    if df is None or df.empty or len(df.columns) < 2:
        return 0.0
    unnamed = sum(1 for c in df.columns if re.match(r'Unnamed:\s*\d+', str(c)))
    unnamed_ratio = unnamed / len(df.columns)
    numeric_cols = df.select_dtypes(include="number").columns
    numeric_ratio = len(numeric_cols) / max(len(df.columns), 1)
    row_score = min(len(df) / 20, 1.0)
    col_score = min(len(df.columns) / 5, 1.0)
    return (1 - unnamed_ratio) * 0.35 + numeric_ratio * 0.35 + row_score * 0.2 + col_score * 0.1


def _try_numeric(series: pd.Series) -> pd.Series:
    """Try to coerce a series to numeric, stripping currency/percent symbols."""
    if pd.api.types.is_numeric_dtype(series):
        return series
    s = series.astype(str).str.strip()
    s = s.str.replace(r'[₹$€£,\s]', '', regex=True)
    s = s.str.replace(r'%$', '', regex=True)
    coerced = pd.to_numeric(s, errors='coerce')
    if coerced.notna().mean() > 0.6:
        return coerced
    return series


def _load_best_dataframe(file_bytes: bytes) -> pd.DataFrame:
    """
    Try every sheet × every likely header row. Pick the combination that
    scores highest as a proper data table (most named numeric columns, fewest
    Unnamed columns, most rows).
    """
    best_score = -1.0
    best_df    = None

    try:
        import io as _io
        buf = _io.BytesIO(file_bytes) if isinstance(file_bytes, (bytes, bytearray)) else file_bytes
        xl = pd.ExcelFile(buf)
    except Exception:
        return pd.DataFrame()

    sheet_names = xl.sheet_names or []

    for sheet in sheet_names:
        for hdr in range(7):          # try rows 0-6 as the header row
            try:
                buf2 = _io.BytesIO(file_bytes) if isinstance(file_bytes, (bytes, bytearray)) else file_bytes
                df = pd.read_excel(buf2, sheet_name=sheet, header=hdr)
                df = df.dropna(how="all").dropna(axis=1, how="all")
                if df.empty:
                    continue

                # If the first data row looks like column names (row of strings),
                # promote it — handles sheets where the real header is one row down
                if df.dtypes.apply(lambda x: x == object).all() and len(df) > 1:
                    row0 = df.iloc[0]
                    if row0.notna().sum() > len(df.columns) * 0.5 and \
                       all(isinstance(v, str) for v in row0.dropna()):
                        df.columns = [str(v).strip() for v in row0]
                        df = df.iloc[1:].reset_index(drop=True)
                        df = df.dropna(how="all").dropna(axis=1, how="all")

                sc = _score_df(df)
                if sc > best_score:
                    best_score = sc
                    best_df    = df.copy()
                    best_df.attrs["_source_sheet"] = sheet
            except Exception:
                continue

    return best_df if best_df is not None else pd.DataFrame()


def _clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean column names, drop fully empty rows/cols, coerce mixed types,
    resolve duplicate column names.
    """
    # Clean column names
    new_cols = []
    seen = {}
    for c in df.columns:
        cleaned = _clean_col_name(str(c))
        if re.match(r'Unnamed:\s*\d+', cleaned):
            cleaned = f"Col_{len(new_cols)+1}"
        if cleaned in seen:
            seen[cleaned] += 1
            cleaned = f"{cleaned}_{seen[cleaned]}"
        else:
            seen[cleaned] = 0
        new_cols.append(cleaned)
    df.columns = new_cols

    # Drop columns that are ALL identical values (no information)
    for col in df.columns:
        if df[col].nunique(dropna=True) <= 1 and len(df) > 5:
            pass  # keep them — might still be useful for filters

    # Try to coerce object columns that look numeric
    for col in df.columns:
        if df[col].dtype == object:
            coerced = _try_numeric(df[col])
            if coerced is not df[col]:
                df[col] = coerced

    # Parse date-like string columns
    for col in df.columns:
        if df[col].dtype == object:
            sample = df[col].dropna().head(20).astype(str)
            parsed = pd.to_datetime(sample, errors="coerce", dayfirst=True)
            if parsed.notna().mean() > 0.7:
                df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)

    return df.dropna(how="all").dropna(axis=1, how="all")


def _classify_columns(df: pd.DataFrame) -> dict:
    """Return lists of column names by type."""
    numeric     = []
    categorical = []
    date        = []
    boolean     = []
    text        = []

    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            continue

        if pd.api.types.is_bool_dtype(series) or \
           (pd.api.types.is_integer_dtype(series) and series.nunique() == 2):
            boolean.append(col)
        elif pd.api.types.is_datetime64_any_dtype(series):
            date.append(col)
        elif pd.api.types.is_numeric_dtype(series):
            numeric.append(col)
        elif pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
            n_unique = series.nunique()
            if MIN_CATEGORY_VALUES <= n_unique <= MAX_CATEGORY_VALUES:
                categorical.append(col)
            else:
                text.append(col)

    # Exclude S.No. / index-like pure-integer columns from KPIs
    numeric = [c for c in numeric if not re.match(r'^(s\.?\s*no|sr\.?\s*no|sl\.?\s*no|index|row|#)$',
                                                    c.strip(), re.I)]

    return {"numeric": numeric, "categorical": categorical,
            "date": date, "boolean": boolean, "text": text}


def _choose_chart_type(col: str, series: pd.Series, n_unique: int) -> str:
    """
    Pick the best chart type for a categorical column:
      - donut      : ≤6 categories (easy to read as pie)
      - bar        : 7–20 categories (vertical bars)
      - horizontal_bar : 21–50 categories (labels fit horizontally)
      - radar      : exactly if column name suggests a multi-axis comparison
    """
    if n_unique <= 6:
        return "donut"
    if n_unique <= 20:
        return "bar"
    if n_unique <= 50:
        return "horizontal_bar"
    return "horizontal_bar"


def _build_kpis(df: pd.DataFrame, numeric_cols: list) -> dict:
    kpis = {}
    for col in numeric_cols[:MAX_NUMERIC_KPI]:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            continue
        label = _humanize(col)
        kpis[col] = {
            "label": label,
            "sum":   round(float(series.sum()), 4),
            "avg":   round(float(series.mean()), 4),
            "min":   round(float(series.min()), 4),
            "max":   round(float(series.max()), 4),
            "count": int(series.count()),
        }
    return kpis


def _build_breakdowns(df: pd.DataFrame, cat_cols: list, numeric_cols: list) -> dict:
    breakdowns = {}
    primary_num = numeric_cols[0] if numeric_cols else None

    for col in cat_cols[:MAX_CATEGORICAL_CHARTS]:
        series = df[col].dropna().astype(str)
        n_unique = series.nunique()
        if n_unique < MIN_CATEGORY_VALUES:
            continue

        counts = series.value_counts().to_dict()
        chart_type = _choose_chart_type(col, series, n_unique)
        label = _humanize(col)

        # Build sums of every numeric column grouped by this category
        sums = {}
        for num_col in numeric_cols[:6]:
            try:
                grouped = df.groupby(col)[num_col].sum(numeric_only=True)
                sums[num_col] = {str(k): round(float(v), 4) for k, v in grouped.items()
                                 if not math.isnan(float(v))}
            except Exception:
                pass

        # Smart description
        top_cat  = max(counts, key=counts.get) if counts else "—"
        top_pct  = round(counts.get(top_cat, 0) / max(sum(counts.values()), 1) * 100, 1)
        desc = (
            f"{n_unique} unique values. '{top_cat}' is the most common "
            f"({top_pct}% of records)."
        )
        if primary_num and sums.get(primary_num):
            top_sum_cat = max(sums[primary_num], key=lambda k: sums[primary_num][k])
            desc += f" Highest {_humanize(primary_num)}: '{top_sum_cat}'."

        breakdowns[col] = {
            "counts":     {str(k): int(v) for k, v in counts.items()},
            "sums":       sums,
            "chart_spec": {
                "chart_type":  chart_type,
                "title":       f"{label} Distribution",
                "description": desc,
                "x_label":     label,
                "y_label":     "Count",
            },
        }
    return breakdowns


def _build_top_n(df: pd.DataFrame, numeric_cols: list, label_col: Optional[str]) -> dict:
    top_n = {}
    for col in numeric_cols[:6]:
        series = pd.to_numeric(df[col], errors="coerce")
        if series.isna().all():
            continue
        col_label = _humanize(col)

        if label_col and label_col in df.columns:
            grp = df.groupby(label_col)[col].sum(numeric_only=True).nlargest(MAX_TOP_N)
            rows = [{"label": str(k), "value": round(float(v), 4)} for k, v in grp.items()]
        else:
            # Use row index as label
            top = series.nlargest(MAX_TOP_N)
            rows = [{"label": f"Row {i+1}", "value": round(float(v), 4)} for i, v in top.items()]

        if not rows:
            continue

        top_n[col] = {
            "title":         f"Top {len(rows)} by {col_label}",
            "description":   f"Records ranked by {col_label} (highest first).",
            "value_label":   col_label,
            "category_label": _humanize(label_col) if label_col else "Record",
            "rows":          rows,
        }
    return top_n


def _build_correlation(df: pd.DataFrame, numeric_cols: list) -> Optional[dict]:
    """Find the numeric pair with the strongest absolute correlation."""
    if len(numeric_cols) < 2:
        return None
    sub = df[numeric_cols].apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all")
    valid = sub.columns.tolist()
    if len(valid) < 2:
        return None
    try:
        corr_matrix = sub[valid].corr()
    except Exception:
        return None

    best_r, best_x, best_y = 0.0, None, None
    for i, x in enumerate(valid):
        for y in valid[i+1:]:
            r = corr_matrix.loc[x, y]
            if pd.isna(r):
                continue
            if abs(r) > abs(best_r):
                best_r, best_x, best_y = r, x, y

    if best_x is None or abs(best_r) < 0.15:
        return None

    direction = "positive" if best_r > 0 else "negative"
    strength  = "strong" if abs(best_r) > 0.7 else "moderate" if abs(best_r) > 0.4 else "weak"
    return {
        "x_column":    best_x,
        "y_column":    best_y,
        "x_label":     _humanize(best_x),
        "y_label":     _humanize(best_y),
        "correlation": round(float(best_r), 4),
        "title":       f"{_humanize(best_x)} vs {_humanize(best_y)}",
        "description": f"{strength.title()} {direction} correlation (r = {best_r:.2f}) between {_humanize(best_x)} and {_humanize(best_y)}.",
    }


def _build_numeric_distributions(df: pd.DataFrame, numeric_cols: list) -> dict:
    """
    For each numeric column, build a histogram-style distribution
    (10 equal-width buckets) so we can show distribution charts.
    """
    distributions = {}
    for col in numeric_cols[:8]:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(series) < 5:
            continue
        try:
            counts, edges = np.histogram(series, bins=min(15, max(5, series.nunique())))
            buckets = []
            for i, cnt in enumerate(counts):
                label = f"{edges[i]:.2g}–{edges[i+1]:.2g}"
                buckets.append({"name": label, "value": int(cnt)})
            col_label = _humanize(col)
            distributions[col] = {
                "buckets":     buckets,
                "chart_spec": {
                    "chart_type":  "bar",
                    "title":       f"{col_label} Distribution",
                    "description": f"How values of {col_label} are spread across ranges. Mean = {series.mean():.2g}, StdDev = {series.std():.2g}.",
                    "x_label":     col_label,
                    "y_label":     "Count",
                },
            }
        except Exception:
            continue
    return distributions


def _find_label_column(df: pd.DataFrame, cat_cols: list, text_cols: list) -> Optional[str]:
    """Pick the best column to use as a record label for Top-N charts."""
    priority = ["name", "grade", "product", "item", "title", "description",
                "batch", "id", "category", "type", "group", "class"]
    for kw in priority:
        for col in cat_cols + text_cols:
            if kw in col.lower():
                return col
    return cat_cols[0] if cat_cols else (text_cols[0] if text_cols else None)


# ── main entry point ──────────────────────────────────────────────────────────

def process_excel(df: pd.DataFrame) -> dict:
    """
    Process an already-loaded DataFrame (called by the upload router).
    Also used by the smart loader below.
    """
    df = _clean_dataframe(df.copy())
    cols = _classify_columns(df)

    numeric_cols  = cols["numeric"]
    cat_cols      = cols["categorical"]
    date_cols     = cols["date"]
    bool_cols     = cols["boolean"]
    text_cols     = cols["text"]

    # Treat boolean columns as categoricals
    for col in bool_cols:
        df[col] = df[col].map({True: "Yes", False: "No", 1: "Yes", 0: "No"}).fillna(df[col].astype(str))
        cat_cols.append(col)

    label_col = _find_label_column(df, cat_cols, text_cols)
    all_cols  = list(df.columns)

    kpis          = _build_kpis(df, numeric_cols)
    breakdowns    = _build_breakdowns(df, cat_cols, numeric_cols)
    top_n         = _build_top_n(df, numeric_cols, label_col)
    correlation   = _build_correlation(df, numeric_cols)
    distributions = _build_numeric_distributions(df, numeric_cols)

    # Time-series detection
    from app.utils.timeseries_engine import detect_and_build_timeseries
    timeseries = detect_and_build_timeseries(df, numeric_cols)

    # Records (capped)
    records = []
    for row in df.head(MAX_RECORDS_RETURNED).to_dict(orient="records"):
        records.append({k: _clean(v) for k, v in row.items()})

    return {
        "meta": {
            "row_count":           int(len(df)),
            "column_count":        int(len(all_cols)),
            "columns":             all_cols,
            "numeric_columns":     numeric_cols,
            "categorical_columns": cat_cols,
            "date_columns":        date_cols,
            "text_columns":        text_cols,
            "label_column":        label_col,
            "source_sheet":        df.attrs.get("_source_sheet", ""),
        },
        "kpis":          kpis,
        "breakdowns":    breakdowns,
        "top_n":         top_n,
        "correlation_chart": correlation,
        "distributions": distributions,
        "timeseries":    timeseries,
        "records":       records,
    }


def process_excel_bytes(file_bytes: bytes, selected_data_type: str = "") -> dict:
    """
    Top-level entry: accepts raw file bytes (from upload), intelligently selects
    the best sheet + header row, then processes it fully.
    Called from the upload router instead of pd.read_excel directly.
    """
    df = _load_best_dataframe(file_bytes)
    if df is None or df.empty:
        return {
            "meta": {"row_count": 0, "column_count": 0, "columns": [],
                     "numeric_columns": [], "categorical_columns": [],
                     "date_columns": [], "text_columns": [], "label_column": None, "source_sheet": ""},
            "kpis": {}, "breakdowns": {}, "top_n": {},
            "correlation_chart": None, "distributions": {}, "timeseries": {"detected": False}, "records": [],
            "error": "Could not find a usable data table in this file.",
        }
    result = process_excel(df)
    result["selected_data_type"] = selected_data_type
    return result
