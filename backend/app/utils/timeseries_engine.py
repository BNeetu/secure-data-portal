"""
Time-series detection engine.

Given an arbitrary uploaded sheet, this module:
  1. Finds the best candidate "date" column (real datetime, parseable text
     dates, a "Year" integer column, or a "Month" text-label column).
  2. Classifies the sheet's temporal shape into one or more of:
       - daily                (multiple distinct days present)
       - cumulative_to_date   (daily data → also computed as a running total)
       - monthly              (one row per month already, OR daily data
                                rolled up to month buckets)
       - month_wise           (same calendar month compared across years,
                                e.g. "every January side by side")
       - cumulative_months    (running total across months)
       - yearly               (one row per year, or daily/monthly data
                                rolled up to year totals)
  3. Builds ready-to-chart series for whichever categories actually apply
     — a sheet can legitimately match more than one (e.g. daily data
     naturally also supports monthly rollups, cumulative, and yearly).

If no usable date signal exists at all, this module returns
{"detected": False} and the caller falls back to the existing
category/numeric breakdown logic untouched.
"""
import re
from typing import Optional

import numpy as np
import pandas as pd

MIN_DISTINCT_DATES_FOR_DAILY = 3
YEAR_MIN, YEAR_MAX = 1990, 2100


# ── Date column detection ─────────────────────────────────────────────────
def _is_year_column(col_name: str, series: pd.Series) -> bool:
    """A numeric column named like 'Year' whose values are plausible years."""
    if not re.search(r"\byear\b|\byr\b", col_name, re.I):
        return False
    if not pd.api.types.is_numeric_dtype(series):
        return False
    vals = series.dropna()
    if vals.empty:
        return False
    return bool(vals.between(YEAR_MIN, YEAR_MAX).mean() > 0.9)


def _is_month_label_column(col_name: str, series: pd.Series) -> bool:
    """A text column whose values parse as dates, OR is literally named 'Month'."""
    name_hint = bool(re.search(r"\bmonth\b|\bmo\b", col_name, re.I))
    if series.dtype == object or pd.api.types.is_string_dtype(series):
        sample = series.dropna().astype(str).head(25)
        if sample.empty:
            return name_hint
        parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
        parse_rate = parsed.notna().mean()
        return name_hint or parse_rate > 0.7
    return False


def find_date_column(df: pd.DataFrame) -> Optional[dict]:
    """
    Returns {"column": str, "kind": "datetime"|"text_date"|"year_int"|"month_label",
             "parsed": pd.Series, "source_granularity": "day"|"month"|"year"}
    for the single best date-like column, or None.

    source_granularity records the TRUE resolution of the original data —
    critical because a "Year" column synthesized to Jan-1st of each year, or
    a "Month" label synthesized to the 1st of each month, must NOT be treated
    as if real day-level timestamps were present. Without this, a 5-row
    yearly summary sheet would incorrectly appear to have "5 distinct days"
    and "5 distinct months" purely as an artifact of the date parsing.

    Priority: real datetime dtype > parseable text dates > Year int > Month label.
    """
    # 1) Native datetime columns — infer true granularity from the values,
    # since even a real datetime64 column can contain only month-starts or
    # only year-starts if it was exported from an already-aggregated report.
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            valid = df[col].dropna()
            if len(valid) >= 2 and (valid.dt.month == 1).all() and (valid.dt.day == 1).all():
                granularity = "year"
            elif len(valid) >= 2 and (valid.dt.day == 1).all():
                granularity = "month"
            else:
                granularity = "day"
            return {"column": col, "kind": "datetime", "parsed": df[col], "source_granularity": granularity}

    # 2) Text columns that are mostly parseable as full dates — but check
    # whether the *parsed result* actually carries day-level resolution.
    # A column of "Jan-2026", "Feb-2026", ... parses successfully as dates,
    # but every value lands on the 1st of its month — that's a month-bucketed
    # source wearing a date dtype, not real daily data. Same logic for a
    # column that's all Jan-1st-of-year (a disguised Year column).
    best_text_candidate = None
    best_parse_rate = 0.0
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            sample = df[col].dropna().astype(str)
            if sample.empty:
                continue
            parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
            rate = parsed.notna().mean()
            name_hint = bool(re.search(r"\bdate\b|\btimestamp\b", col, re.I))
            if (name_hint and rate > 0.5) or rate > 0.85:
                if rate > best_parse_rate:
                    best_parse_rate = rate
                    full_parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
                    valid_parsed = full_parsed.dropna()

                    # Infer true granularity from the parsed values themselves,
                    # not just from successful parsing.
                    if len(valid_parsed) >= 2 and (valid_parsed.dt.month == 1).all() and (valid_parsed.dt.day == 1).all():
                        granularity = "year"   # every value is Jan 1st → year-only source
                    elif len(valid_parsed) >= 2 and (valid_parsed.dt.day == 1).all():
                        granularity = "month"  # every value is the 1st of its month → month-bucketed source
                    else:
                        granularity = "day"    # genuine day-level variation present

                    best_text_candidate = {
                        "column": col, "kind": "text_date", "parsed": full_parsed,
                        "source_granularity": granularity,
                    }
    if best_text_candidate:
        return best_text_candidate

    # 3) "Year" integer column — coarse, year-level granularity only
    for col in df.columns:
        if _is_year_column(col, df[col]):
            parsed = pd.to_datetime(df[col].astype("Int64").astype(str) + "-01-01", errors="coerce")
            return {"column": col, "kind": "year_int", "parsed": parsed, "source_granularity": "year"}

    # 4) "Month" text label column (e.g. "Jan-2026") — month-level granularity only
    for col in df.columns:
        if _is_month_label_column(col, df[col]):
            parsed = pd.to_datetime(df[col], errors="coerce", format="mixed")
            if parsed.notna().mean() > 0.5:
                return {"column": col, "kind": "month_label", "parsed": parsed, "source_granularity": "month"}

    return None


# ── Classification ────────────────────────────────────────────────────────
def classify_temporal_shape(dates: pd.Series, source_granularity: str) -> dict:
    """
    Inspects the actual parsed date values (post-dropna) and returns which
    of the 6 visualization categories genuinely apply, plus descriptive stats
    used later to decide how to build each chart.

    `source_granularity` ("day" | "month" | "year") is a hard ceiling:
      - "year"  source can ONLY produce: yearly
                (no daily/monthly/month-wise — those rows never had that
                resolution; a Year-only column has no real month or day info)
      - "month" source can ONLY produce: monthly, cumulative_months,
                yearly (by summing the months), and month_wise IF ≥2 years
                are present (no "daily" — there's no day-level data)
      - "day"   source can produce all 6 categories, gated by how much
                actual date variety is present (see thresholds below)
    """
    valid = dates.dropna()
    if valid.empty:
        return {"applicable": [], "stats": {}}

    distinct_days = valid.dt.normalize().nunique()
    distinct_months = valid.dt.to_period("M").nunique()
    distinct_years = valid.dt.year.nunique()
    span_days = (valid.max() - valid.min()).days

    applicable = []

    if source_granularity == "day":
        # Daily: meaningfully more than a couple of distinct calendar days
        if distinct_days >= MIN_DISTINCT_DATES_FOR_DAILY:
            applicable.append("daily")
            applicable.append("cumulative_to_date")

        if distinct_months >= 2:
            applicable.append("monthly")
            applicable.append("cumulative_months")

        if distinct_years >= 2 and distinct_months >= 2:
            applicable.append("month_wise")

        if distinct_years >= 2:
            applicable.append("yearly")

    elif source_granularity == "month":
        # Source is a month-bucketed sheet (e.g. "Jan-2026" per row) —
        # there is no real daily resolution to show, ever.
        if distinct_months >= 2:
            applicable.append("monthly")
            applicable.append("cumulative_months")

        if distinct_years >= 2 and distinct_months >= 2:
            applicable.append("month_wise")

        if distinct_years >= 2:
            applicable.append("yearly")

    elif source_granularity == "year":
        # Source is a year-only sheet — only a yearly view makes sense.
        if distinct_years >= 2:
            applicable.append("yearly")

    return {
        "applicable": applicable,
        "stats": {
            "distinct_days": int(distinct_days),
            "distinct_months": int(distinct_months),
            "distinct_years": int(distinct_years),
            "span_days": int(span_days),
            "min_date": valid.min().isoformat(),
            "max_date": valid.max().isoformat(),
            "source_granularity": source_granularity,
        },
    }


# ── Series builders ───────────────────────────────────────────────────────
def _pick_value_columns(df: pd.DataFrame, numeric_cols: list) -> list:
    """Cap to a sane number of numeric columns for time-series charting."""
    return numeric_cols[:6]


def build_daily_series(df: pd.DataFrame, date_col: str, dates: pd.Series, numeric_cols: list) -> dict:
    work = df.copy()
    work["_date"] = dates.dt.normalize()
    work = work.dropna(subset=["_date"]).sort_values("_date")

    value_cols = _pick_value_columns(df, numeric_cols)
    grouped = work.groupby("_date")[value_cols].sum(numeric_only=True).reset_index()

    return {
        "labels": [d.strftime("%Y-%m-%d") for d in grouped["_date"]],
        "series": {col: [round(float(v), 2) for v in grouped[col]] for col in value_cols},
    }


def build_cumulative_to_date_series(daily_series: dict) -> dict:
    labels = daily_series["labels"]
    cum_series = {}
    for col, values in daily_series["series"].items():
        running = 0.0
        cum = []
        for v in values:
            running += v
            cum.append(round(running, 2))
        cum_series[col] = cum
    return {"labels": labels, "series": cum_series}


def build_monthly_series(df: pd.DataFrame, date_col: str, dates: pd.Series, numeric_cols: list) -> dict:
    work = df.copy()
    work["_month"] = dates.dt.to_period("M")
    work = work.dropna(subset=["_month"]).sort_values("_month")

    value_cols = _pick_value_columns(df, numeric_cols)
    grouped = work.groupby("_month")[value_cols].sum(numeric_only=True).reset_index()

    return {
        "labels": [str(p) for p in grouped["_month"]],  # "2026-03"
        "series": {col: [round(float(v), 2) for v in grouped[col]] for col in value_cols},
    }


def build_cumulative_months_series(monthly_series: dict) -> dict:
    labels = monthly_series["labels"]
    cum_series = {}
    for col, values in monthly_series["series"].items():
        running = 0.0
        cum = []
        for v in values:
            running += v
            cum.append(round(running, 2))
        cum_series[col] = cum
    return {"labels": labels, "series": cum_series}


def build_month_wise_series(df: pd.DataFrame, date_col: str, dates: pd.Series, numeric_cols: list) -> dict:
    """
    Same calendar month, compared across years — e.g. Jan-2025 vs Jan-2026
    side by side. Returns one series per year, x-axis = month name (Jan..Dec).
    """
    work = df.copy()
    work["_year"] = dates.dt.year
    work["_month_num"] = dates.dt.month
    work = work.dropna(subset=["_year", "_month_num"])

    value_col = numeric_cols[0] if numeric_cols else None
    if not value_col:
        return {"labels": [], "years": {}}

    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    years = sorted(work["_year"].dropna().unique().astype(int).tolist())

    series_by_year = {}
    for yr in years:
        yr_data = work[work["_year"] == yr]
        monthly_sum = yr_data.groupby("_month_num")[value_col].sum(numeric_only=True)
        series_by_year[str(yr)] = [round(float(monthly_sum.get(m, 0)), 2) for m in range(1, 13)]

    return {"labels": month_names, "years": series_by_year, "value_column": value_col}


def build_yearly_series(df: pd.DataFrame, date_col: str, dates: pd.Series, numeric_cols: list) -> dict:
    work = df.copy()
    work["_year"] = dates.dt.year
    work = work.dropna(subset=["_year"]).sort_values("_year")

    value_cols = _pick_value_columns(df, numeric_cols)
    grouped = work.groupby("_year")[value_cols].sum(numeric_only=True).reset_index()

    return {
        "labels": [str(int(y)) for y in grouped["_year"]],
        "series": {col: [round(float(v), 2) for v in grouped[col]] for col in value_cols},
    }


# ── Main entrypoint ────────────────────────────────────────────────────────
def detect_and_build_timeseries(df: pd.DataFrame, numeric_cols: list) -> dict:
    """
    Returns:
      {"detected": False}  — no usable date column found, caller should fall
                              back to the existing non-temporal dashboard.
      {"detected": True, "date_column": ..., "date_kind": ..., "stats": {...},
       "applicable_categories": [...], "charts": {category: series_dict}}
    """
    if not numeric_cols:
        return {"detected": False}

    date_info = find_date_column(df)
    if date_info is None:
        return {"detected": False}

    classification = classify_temporal_shape(date_info["parsed"], date_info["source_granularity"])
    applicable = classification["applicable"]
    if not applicable:
        return {"detected": False}

    dates = date_info["parsed"]
    date_col = date_info["column"]
    charts = {}

    if "daily" in applicable:
        daily = build_daily_series(df, date_col, dates, numeric_cols)
        charts["daily"] = daily
        if "cumulative_to_date" in applicable:
            charts["cumulative_to_date"] = build_cumulative_to_date_series(daily)

    if "monthly" in applicable:
        monthly = build_monthly_series(df, date_col, dates, numeric_cols)
        charts["monthly"] = monthly
        if "cumulative_months" in applicable:
            charts["cumulative_months"] = build_cumulative_months_series(monthly)

    if "month_wise" in applicable:
        charts["month_wise"] = build_month_wise_series(df, date_col, dates, numeric_cols)

    if "yearly" in applicable:
        charts["yearly"] = build_yearly_series(df, date_col, dates, numeric_cols)

    return {
        "detected": True,
        "date_column": date_col,
        "date_kind": date_info["kind"],
        "stats": classification["stats"],
        "applicable_categories": applicable,
        "charts": charts,
    }
