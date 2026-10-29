"""CSV/JSON parsing, encoding detection, and column type inference."""

from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.core.exceptions import ProcessingError, UploadError

SUPPORTED_MIME_TYPES = frozenset(
    {"text/csv", "application/csv", "text/plain", "application/json", "text/json"}
)
SUPPORTED_EXTENSIONS = frozenset({".csv", ".json"})
MAX_FIELD_LENGTH = 65_536  # bytes; fields longer than this are truncated


@dataclass
class ParseResult:
    df: pd.DataFrame
    original_filename: str
    inferred_types: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)


def _infer_column_type(series: pd.Series[Any]) -> str:
    """Infer a stable type name for a pandas Series."""
    non_null = series.dropna()
    if len(non_null) == 0:
        return "empty"

    dtype = series.dtype
    # Use dtype.kind — works for both numpy dtypes and pandas extension dtypes (Int64, Float64,
    # etc.) without triggering deprecation warnings from is_integer_dtype / is_float_dtype.
    kind = getattr(dtype, "kind", "O")
    if kind == "b":
        return "boolean"
    if kind in ("i", "u"):
        return "integer"
    if kind == "f":
        return "float"
    if kind == "M":
        return "datetime"
    if pd.api.types.is_datetime64_any_dtype(dtype):
        return "datetime"

    # Attempt heuristic coercion for string-like columns.
    # pandas 2.x returns StringDtype for dtype=str CSV reads, not numpy object,
    # but both have kind == "O" so we check kind instead of `dtype is object`.
    if kind == "O":
        sample = non_null.head(200)
        try:
            parsed = pd.to_datetime(sample, errors="coerce")
            if parsed.notna().sum() / len(sample) >= 0.8:
                return "datetime"
        except Exception:  # noqa: S110
            pass

        # Attempt numeric coercion
        try:
            numeric = pd.to_numeric(non_null.head(200), errors="coerce")
            if numeric.notna().sum() / min(200, len(non_null)) >= 0.9:
                if all(str(v).isdigit() for v in non_null.head(50) if pd.notna(v)):
                    return "integer"
                return "float"
        except Exception:  # noqa: S110
            pass

    return "string"


def _safe_float(value: Any) -> float | None:
    """Convert a value to float, returning None for non-finite or non-convertible."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        f = float(value)
        return None if not math.isfinite(f) else f
    except (ValueError, TypeError):
        return None


def _sanitize_column_names(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Normalize column names; report duplicates before normalization."""
    warnings: list[str] = []
    raw_names = list(df.columns)

    # Detect duplicates in original names
    seen: set[str] = set()
    for name in raw_names:
        if name in seen:
            warnings.append(f"Duplicate column name detected: '{name}'")
        seen.add(name)

    # Strip whitespace and truncate
    new_names = [str(n).strip()[:255] for n in raw_names]
    df.columns = pd.Index(new_names)
    return df, warnings


def parse_csv(
    content: bytes,
    original_filename: str,
    max_rows: int,
    max_columns: int,
) -> ParseResult:
    """Parse CSV bytes into a ParseResult."""
    if len(content) == 0:
        raise UploadError("Uploaded file is empty.")

    # Attempt to detect encoding; fall back to utf-8 with replacement
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = content.decode("utf-8", errors="replace")

    warnings: list[str] = []

    try:
        df = pd.read_csv(
            io.StringIO(text),
            nrows=max_rows + 1,  # read one extra to detect overflow
            dtype=str,  # read everything as str initially
            keep_default_na=False,
            na_values=["", "NA", "N/A", "null", "NULL", "None", "NaN", "nan", "#N/A"],
            on_bad_lines="warn",
            low_memory=False,
        )
    except pd.errors.EmptyDataError as exc:
        raise UploadError("CSV file contains no data.") from exc
    except Exception as exc:
        raise ProcessingError(f"Failed to parse CSV: {exc}") from exc

    if len(df) == 0:
        raise UploadError("CSV file has headers but no data rows.")

    if len(df) > max_rows:
        df = df.head(max_rows)
        warnings.append(
            f"Dataset truncated to {max_rows:,} rows (upload limit). "
            "Only the first {max_rows:,} rows were processed."
        )

    if len(df.columns) > max_columns:
        raise UploadError(
            f"Dataset has {len(df.columns)} columns, exceeding the limit of {max_columns}."
        )

    df, col_warnings = _sanitize_column_names(df)
    warnings.extend(col_warnings)

    # Infer types per column
    inferred: dict[str, str] = {}
    for col in df.columns:
        try:
            # Attempt numeric/datetime coercion for better type inference
            col_type = _infer_column_type(df[col])
            if col_type == "integer":
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
            elif col_type == "float":
                df[col] = pd.to_numeric(df[col], errors="coerce")
            elif col_type == "datetime":
                df[col] = pd.to_datetime(df[col], errors="coerce")
            # Re-infer after coercion
            inferred[col] = _infer_column_type(df[col])
        except Exception:
            inferred[col] = "string"

    return ParseResult(
        df=df,
        original_filename=original_filename,
        inferred_types=inferred,
        warnings=warnings,
    )


def _json_to_dataframe(raw: Any) -> pd.DataFrame:
    """Convert a parsed JSON value into a DataFrame, handling multiple layouts.

    Supported formats:
    - Array of objects:      [{col: val}, {col: val}, ...]
    - Column-oriented dict:  {col: [v1, v2, ...], col2: [v1, v2, ...]}
    - Single record object:  {col: val, col2: val2}
    - Wrapped records key:   {"data": [{...}]} or {"records": [{...}]}
    """
    if isinstance(raw, list):
        if len(raw) == 0:
            return pd.DataFrame()
        # Flatten non-dict rows into {"value": row}
        rows = [r if isinstance(r, dict) else {"value": r} for r in raw]
        return pd.DataFrame(rows)

    if isinstance(raw, dict):
        # Check for a single well-known wrapper key containing the records list
        for key in ("data", "records", "rows", "results", "items"):
            if key in raw and isinstance(raw[key], list):
                return _json_to_dataframe(raw[key])

        values = list(raw.values())
        if not values:
            return pd.DataFrame()

        if isinstance(values[0], list):
            # Column-oriented: {col: [v1, v2, ...]} — truncate to shortest array
            min_len = min(len(v) for v in values if isinstance(v, list))
            aligned = {
                k: (v[:min_len] if isinstance(v, list) else [v] * min_len) for k, v in raw.items()
            }
            return pd.DataFrame(aligned)

        # Single record — wrap in list
        return pd.DataFrame([raw])

    raise ProcessingError(
        "JSON must be an array of objects, a column-oriented object "
        "{col: [values]}, or a single record object."
    )


def parse_json(
    content: bytes,
    original_filename: str,
    max_rows: int,
    max_columns: int,
) -> ParseResult:
    """Parse JSON bytes into a ParseResult."""
    if len(content) == 0:
        raise UploadError("Uploaded file is empty.")

    import json as _json  # stdlib json — always available

    try:
        text = content.decode("utf-8", errors="replace")
        raw = _json.loads(text)
    except _json.JSONDecodeError as exc:
        raise ProcessingError(f"Invalid JSON: {exc}") from exc

    try:
        df = _json_to_dataframe(raw)
    except ProcessingError:
        raise
    except Exception as exc:
        raise ProcessingError(f"Failed to parse JSON: {exc}") from exc

    if len(df) == 0:
        raise UploadError("JSON file contains no records.")

    if len(df) > max_rows:
        df = df.head(max_rows)

    if len(df.columns) > max_columns:
        raise UploadError(f"Dataset has {len(df.columns)} columns, exceeding the limit.")

    df, col_warnings = _sanitize_column_names(df)
    inferred = {col: _infer_column_type(df[col]) for col in df.columns}

    return ParseResult(
        df=df,
        original_filename=original_filename,
        inferred_types=inferred,
        warnings=col_warnings,
    )


def parse_file(
    content: bytes,
    original_filename: str,
    max_rows: int,
    max_columns: int,
) -> ParseResult:
    """Dispatch to the appropriate parser based on file extension."""
    name_lower = original_filename.lower()
    if name_lower.endswith(".json"):
        return parse_json(content, original_filename, max_rows, max_columns)
    # Default to CSV (also handles .csv and any ambiguous extension)
    return parse_csv(content, original_filename, max_rows, max_columns)
