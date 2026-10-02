"""
Chart intelligence engine.

Takes a cleaned dataframe and decides, column by column, what the BEST
chart type is to represent it — instead of always pairing every category
with the same bar+donut combo regardless of whether that makes sense.

Also filters out columns that look like real data but aren't useful for
charting at all:
  - "Unnamed: N" ghost columns from merged Excel header cells
  - Columns where every row has the same single value (e.g. a report-level
    "Issue Date" repeated on every line — not a per-row category)
  - Free-text columns where almost every value is unique (e.g. a Remarks
    field) — these belong in the data table, not a bar chart
  - Columns that are clearly an ID/serial-number field, not a metric

For each surviving column, returns a recommended chart spec:
  {column, kind, chart_type, title, description, x_label, y_label}

chart_type is one of:
  bar, horizontal_bar, pie, donut, line, area, scatter, stacked_bar, kpi_only
"""
import re
from typing import Optional

import numpy as np
import pandas as pd

MAX_PIE_SLICES = 8          # beyond this, a pie/donut becomes unreadable — use bar instead
MAX_BAR_CATEGORIES = 15     # beyond this, a vertical bar gets unreadably crowded — use horizontal bar
MIN_USEFUL_CARDINALITY = 2  # a column with only 1 distinct value tells us nothing
UNIQUE_RATIO_THRESHOLD = 0.9  # if >90% of values are unique, it's free text / an ID, not a category


# ── Column quality filters ────────────────────────────────────────────────
def is_ghost_column(col_name: str) -> bool:
    """Pandas auto-names empty/merged Excel header cells 'Unnamed: N'."""
    return bool(re.match(r"^Unnamed:\s*\d+$", str(col_name).strip(), re.I))


def is_id_like_column(col_name: str, series: pd.Series) -> bool:
    """Serial numbers, document numbers, row IDs — not meaningful as chart categories."""
    name_hint = bool(re.search(r"\b(id|s\.?no|sr\.?no|serial|doc\.?\s*no|sl\.?\s*no)\b", col_name, re.I))
    if not name_hint:
        return False
    nunique = series.nunique(dropna=True)
    total = series.dropna().shape[0]
    if total == 0:
        return False
    return (nunique / total) > 0.85  # near-unique values under an ID-like name


def is_constant_column(series: pd.Series) -> bool:
    """A column where every row has the same value carries zero comparative information."""
    return series.nunique(dropna=True) < MIN_USEFUL_CARDINALITY


def is_free_text_column(series: pd.Series, total_rows: int) -> bool:
    """Mostly-unique short text (remarks, notes, descriptions) — not a charting category."""
    nunique = series.nunique(dropna=True)
    non_null = series.dropna().shape[0]
    if non_null == 0 or total_rows == 0:
        return False
    return (nunique / non_null) > UNIQUE_RATIO_THRESHOLD and nunique > MAX_BAR_CATEGORIES


def humanize_column_name(col_name: str) -> str:
    """
    Turns raw spreadsheet headers into readable labels:
      'unit_cost' -> 'Unit Cost', 'DOC. NO.: IMS/NSL/QA/BF/ABI/RC/14' -> 'Doc No'
    """
    name = str(col_name).strip()
    # If there's a colon, the part before it is usually the real label and
    # everything after is a value/code/reference number (e.g. "Issue Date: 01/03/2025",
    # "DOC. NO.: IMS/NSL/QA/BF/ABI/RC/14") — keep only the label side.
    if ":" in name:
        name = name.split(":")[0]
    name = name.replace("_", " ").replace(".", " ")
    name = re.sub(r"\s+", " ", name).strip()
    # Defensive cap — even after cleaning, an unusually long header shouldn't
    # blow up chart titles/axis labels.
    if len(name) > 40:
        name = name[:40].rstrip() + "…"
    if len(name) <= 4 and name.isupper():
        return name
    return name.title()


def is_numeric_but_actually_categorical(col_name: str, series: pd.Series, total_rows: int) -> bool:
    """
    A numeric column with very few distinct small integer values (e.g. Tap
    Hole No: 1,2,3,4 or Shift: 1,2,3) is functionally a category code, not a
    continuous measurement — summing/averaging it produces a meaningless KPI
    ("average Tap Hole No = 2.5" tells nobody anything). These read far
    better as a bar/donut breakdown than as a KPI card.

    Heuristic: integer-valued, very low cardinality relative to row count,
    and the values look like small ordinal codes (not large continuous
    quantities like revenue or weight).
    """
    non_null = series.dropna()
    if non_null.empty:
        return False
    if not non_null.apply(lambda v: float(v).is_integer()).all():
        return False  # has real decimals — it's a measurement, not a code
    nunique = non_null.nunique()
    if nunique < 2 or nunique > MAX_PIE_SLICES * 2:
        return False
    # If almost every row has its own value, it's an ID/serial, not a code
    if (nunique / len(non_null)) > 0.5 and len(non_null) > 10:
        return False
    return True


def filter_chartable_columns(df: pd.DataFrame, categorical_cols: list) -> list:
    """Returns the subset of categorical_cols that are actually worth charting."""
    total_rows = len(df)
    keep = []
    for col in categorical_cols:
        if is_ghost_column(col):
            continue
        if is_id_like_column(col, df[col]):
            continue
        if is_constant_column(df[col]):
            continue
        if is_free_text_column(df[col], total_rows):
            continue
        keep.append(col)
    return keep


def find_categorical_numeric_columns(df: pd.DataFrame, numeric_cols: list) -> list:
    """Scans numeric columns for ones that are actually category codes in disguise (see above)."""
    total_rows = len(df)
    found = []
    for col in numeric_cols:
        if is_numeric_but_actually_categorical(col, df[col], total_rows):
            found.append(col)
    return found


# ── Chart type selection ──────────────────────────────────────────────────
def choose_chart_type_for_category(series: pd.Series, has_numeric_pair: bool) -> str:
    """
    Decides the best chart type for a single categorical column, based on
    how many distinct values it has — not a one-size-fits-all bar+donut.
    """
    nunique = series.nunique(dropna=True)

    if nunique <= MAX_PIE_SLICES:
        return "donut"  # small number of categories — proportions are the interesting story
    elif nunique <= MAX_BAR_CATEGORIES:
        return "bar"    # moderate count — a clean vertical bar chart reads fine
    else:
        return "horizontal_bar"  # many categories — horizontal bars keep labels readable


def build_chart_spec(col: str, df: pd.DataFrame, numeric_col: Optional[str], numeric_label: Optional[str]) -> dict:
    """Builds a complete, ready-to-render chart specification for one categorical column."""
    series = df[col]
    nunique = series.nunique(dropna=True)
    chart_type = choose_chart_type_for_category(series, has_numeric_pair=bool(numeric_col))
    readable = humanize_column_name(col)

    if numeric_col:
        description = f"Shows how total {humanize_column_name(numeric_col)} breaks down across each {readable.lower()}."
        y_label = humanize_column_name(numeric_col)
    else:
        description = f"Shows how many records fall into each {readable.lower()}."
        y_label = "Number of Records"

    return {
        "column": col,
        "title": readable,
        "description": description,
        "chart_type": chart_type,
        "x_label": readable,
        "y_label": y_label,
        "category_count": int(nunique),
    }


def build_numeric_chart_spec(col: str, kpi: dict) -> dict:
    """For a standalone numeric column with no useful category pairing — shown as a KPI, not forced into a chart."""
    readable = humanize_column_name(col)
    return {
        "column": col,
        "title": readable,
        "description": f"Summary statistics for {readable.lower()} across all records.",
        "chart_type": "kpi_only",
        "x_label": None,
        "y_label": readable,
    }


def detect_correlation_pair(df: pd.DataFrame, numeric_cols: list) -> Optional[dict]:
    """
    If there are exactly 2+ numeric columns with a plausible relationship
    (e.g. Unit Cost vs Retail Price), a scatter plot is the right chart —
    not another bar chart. Picks the pair with the strongest absolute
    correlation, if any pair correlates meaningfully.
    """
    if len(numeric_cols) < 2:
        return None
    best_pair = None
    best_corr = 0.0
    for i in range(len(numeric_cols)):
        for j in range(i + 1, len(numeric_cols)):
            a, b = numeric_cols[i], numeric_cols[j]
            try:
                corr = df[[a, b]].dropna().corr().iloc[0, 1]
            except Exception:
                continue
            if pd.notna(corr) and abs(corr) > abs(best_corr) and abs(corr) > 0.3:
                best_corr = corr
                best_pair = (a, b)
    if not best_pair:
        return None
    a, b = best_pair
    return {
        "x_column": a, "y_column": b,
        "x_label": humanize_column_name(a), "y_label": humanize_column_name(b),
        "title": f"{humanize_column_name(a)} vs {humanize_column_name(b)}",
        "description": f"Each point is one record, plotting {humanize_column_name(a).lower()} against {humanize_column_name(b).lower()} to reveal any relationship between them.",
        "chart_type": "scatter",
        "correlation": round(float(best_corr), 2),
    }
