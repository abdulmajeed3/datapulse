"""Data quality analysis: missing values, duplicates, structural issues."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass
class QualityFinding:
    level: str  # "error" | "warning" | "info"
    code: str
    message: str
    column: str | None = None
    details: dict[str, Any] | None = None


@dataclass
class ColumnQualityInfo:
    name: str
    inferred_type: str
    total_count: int
    missing_count: int
    missing_pct: float
    unique_count: int | None = None


@dataclass
class QualityReport:
    total_rows: int
    total_columns: int
    duplicate_rows: int
    findings: list[QualityFinding] = field(default_factory=list)
    columns: list[ColumnQualityInfo] = field(default_factory=list)


_MISSING_PCT_WARN = 20.0
_MISSING_PCT_ERROR = 80.0
_MAX_UNIQUE_CHECK = 50_000  # skip unique count for very large columns


def analyze_quality(
    df: pd.DataFrame,
    inferred_types: dict[str, str],
) -> QualityReport:
    """Compute data-quality metrics for a DataFrame.

    Does not modify the input DataFrame.
    Duplicate rows are identified by comparing all column values (including NaN equality).
    """
    findings: list[QualityFinding] = []
    column_infos: list[ColumnQualityInfo] = []

    total_rows = len(df)
    total_columns = len(df.columns)

    # Duplicate rows: keep=False marks ALL duplicates
    duplicate_mask = df.duplicated(keep=False)
    duplicate_rows = int(duplicate_mask.sum() // 2) if duplicate_mask.any() else 0

    if duplicate_rows > 0:
        pct = duplicate_rows / total_rows * 100
        findings.append(
            QualityFinding(
                level="warning",
                code="DUPLICATE_ROWS",
                message=f"{duplicate_rows:,} duplicate row(s) detected ({pct:.1f}% of total).",
                details={"count": duplicate_rows, "pct": round(pct, 2)},
            )
        )

    for col in df.columns:
        series = df[col]
        inferred_type = inferred_types.get(col, "string")
        total_count = len(series)
        missing_count = int(series.isna().sum())
        missing_pct = missing_count / total_count * 100 if total_count > 0 else 0.0

        # Unique count (skip for very large string columns)
        unique_count: int | None = None
        if total_count <= _MAX_UNIQUE_CHECK:
            try:
                unique_count = int(series.nunique(dropna=True))
            except Exception:  # noqa: S110
                pass

        column_infos.append(
            ColumnQualityInfo(
                name=col,
                inferred_type=inferred_type,
                total_count=total_count,
                missing_count=missing_count,
                missing_pct=round(missing_pct, 2),
                unique_count=unique_count,
            )
        )

        # Findings per column
        if inferred_type == "empty" or total_count == missing_count:
            findings.append(
                QualityFinding(
                    level="warning",
                    code="EMPTY_COLUMN",
                    message=f"Column '{col}' contains no non-missing values.",
                    column=col,
                )
            )
        elif missing_pct >= _MISSING_PCT_ERROR:
            findings.append(
                QualityFinding(
                    level="warning",
                    code="HIGH_MISSING",
                    message=(
                        f"Column '{col}' is {missing_pct:.1f}% missing "
                        f"({missing_count:,}/{total_count:,} values)."
                    ),
                    column=col,
                    details={"missing_count": missing_count, "missing_pct": round(missing_pct, 2)},
                )
            )
        elif missing_pct >= _MISSING_PCT_WARN:
            findings.append(
                QualityFinding(
                    level="info",
                    code="MODERATE_MISSING",
                    message=(
                        f"Column '{col}' is {missing_pct:.1f}% missing "
                        f"({missing_count:,}/{total_count:,} values)."
                    ),
                    column=col,
                    details={"missing_count": missing_count, "missing_pct": round(missing_pct, 2)},
                )
            )

        if unique_count is not None and unique_count == 1 and total_count > 1:
            findings.append(
                QualityFinding(
                    level="info",
                    code="SINGLE_VALUE_COLUMN",
                    message=f"Column '{col}' has only one unique value across all rows.",
                    column=col,
                )
            )

    if total_rows == 0:
        findings.append(
            QualityFinding(level="error", code="EMPTY_DATASET", message="Dataset has no rows.")
        )

    return QualityReport(
        total_rows=total_rows,
        total_columns=total_columns,
        duplicate_rows=duplicate_rows,
        findings=findings,
        columns=column_infos,
    )
