"""Summary statistics per column, type-appropriate and edge-case safe."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class NumericStats:
    count: int
    missing: int
    min: float | None
    max: float | None
    mean: float | None
    median: float | None
    std: float | None
    p25: float | None
    p75: float | None


@dataclass
class CategoricalStats:
    count: int
    missing: int
    unique: int
    top_values: list[dict[str, Any]]


@dataclass
class DatetimeStats:
    count: int
    missing: int
    earliest: str | None
    latest: str | None


@dataclass
class ColumnStats:
    name: str
    inferred_type: str
    numeric: NumericStats | None = None
    categorical: CategoricalStats | None = None
    datetime: DatetimeStats | None = None


@dataclass
class StatisticsReport:
    total_rows: int
    total_columns: int
    columns: list[ColumnStats] = field(default_factory=list)


_TOP_VALUES_LIMIT = 20
_NUMERIC_TYPES = {"integer", "float"}
_DATETIME_TYPES = {"datetime"}


def _safe_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (TypeError, ValueError):
        return None


def _numeric_stats(series: pd.Series[Any]) -> NumericStats:
    numeric = pd.to_numeric(series, errors="coerce")
    non_null = numeric.dropna()
    count = int(non_null.count())
    missing = int(series.isna().sum())

    if count == 0:
        return NumericStats(
            count=0,
            missing=missing,
            min=None,
            max=None,
            mean=None,
            median=None,
            std=None,
            p25=None,
            p75=None,
        )

    try:
        desc = non_null.describe(percentiles=[0.25, 0.75])
        return NumericStats(
            count=count,
            missing=missing,
            min=_safe_float(desc.get("min")),
            max=_safe_float(desc.get("max")),
            mean=_safe_float(desc.get("mean")),
            median=_safe_float(non_null.median()),
            std=_safe_float(desc.get("std")),
            p25=_safe_float(desc.get("25%")),
            p75=_safe_float(desc.get("75%")),
        )
    except Exception:
        return NumericStats(
            count=count,
            missing=missing,
            min=None,
            max=None,
            mean=None,
            median=None,
            std=None,
            p25=None,
            p75=None,
        )


def _categorical_stats(series: pd.Series[Any]) -> CategoricalStats:
    non_null = series.dropna()
    count = int(non_null.count())
    missing = int(series.isna().sum())
    unique = int(non_null.nunique())

    top_values: list[dict[str, Any]] = []
    try:
        vc = non_null.value_counts().head(_TOP_VALUES_LIMIT)
        top_values = [{"value": str(k), "count": int(v)} for k, v in vc.items()]
    except Exception:  # noqa: S110
        pass

    return CategoricalStats(count=count, missing=missing, unique=unique, top_values=top_values)


def _datetime_stats(series: pd.Series[Any]) -> DatetimeStats:
    if not pd.api.types.is_datetime64_any_dtype(series):
        series = pd.to_datetime(series, errors="coerce")

    non_null = series.dropna()
    count = int(non_null.count())
    missing = int(series.isna().sum())

    earliest: str | None = None
    latest: str | None = None
    if count > 0:
        try:
            earliest = str(non_null.min().isoformat())
            latest = str(non_null.max().isoformat())
        except Exception:  # noqa: S110
            pass

    return DatetimeStats(count=count, missing=missing, earliest=earliest, latest=latest)


def compute_statistics(
    df: pd.DataFrame,
    inferred_types: dict[str, str],
) -> StatisticsReport:
    """Compute type-appropriate statistics for each column."""
    column_stats: list[ColumnStats] = []

    for col in df.columns:
        series = df[col]
        col_type = inferred_types.get(col, "string")

        stats = ColumnStats(name=col, inferred_type=col_type)

        if col_type in _NUMERIC_TYPES:
            stats.numeric = _numeric_stats(series)
        elif col_type in _DATETIME_TYPES:
            stats.datetime = _datetime_stats(series)
        else:
            stats.categorical = _categorical_stats(series)

        column_stats.append(stats)

    return StatisticsReport(
        total_rows=len(df),
        total_columns=len(df.columns),
        columns=column_stats,
    )
