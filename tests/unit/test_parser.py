"""Unit tests for CSV/JSON parsing and column type inference."""

import pandas as pd
import pytest

from app.analytics.parser import (
    _infer_column_type,
    _sanitize_column_names,
    parse_csv,
    parse_json,
)
from app.core.exceptions import ProcessingError, UploadError

MAX_ROWS = 1_000_000
MAX_COLS = 500


class TestColumnTypeInference:
    def test_integer_column(self) -> None:
        s = pd.Series([1, 2, 3, 4, 5], dtype="Int64")
        assert _infer_column_type(s) == "integer"

    def test_float_column(self) -> None:
        s = pd.Series([1.1, 2.2, 3.3])
        assert _infer_column_type(s) == "float"

    def test_string_column(self) -> None:
        s = pd.Series(["Alice", "Bob", "Charlie"])
        assert _infer_column_type(s) == "string"

    def test_boolean_column(self) -> None:
        s = pd.Series([True, False, True])
        assert _infer_column_type(s) == "boolean"

    def test_datetime_column(self) -> None:
        s = pd.to_datetime(pd.Series(["2024-01-01", "2024-06-15", "2024-12-31"]))
        assert _infer_column_type(s) == "datetime"

    def test_empty_series(self) -> None:
        s = pd.Series([], dtype=object)
        assert _infer_column_type(s) == "empty"

    def test_all_null_series(self) -> None:
        s = pd.Series([None, None, None])
        assert _infer_column_type(s) == "empty"


class TestSanitizeColumnNames:
    def test_strips_whitespace(self) -> None:
        df = pd.DataFrame(columns=["  name ", " age"])
        result, _ = _sanitize_column_names(df)
        assert list(result.columns) == ["name", "age"]

    def test_duplicate_detection(self) -> None:
        df = pd.DataFrame(columns=["a", "b", "a"])
        _, warnings = _sanitize_column_names(df)
        assert any("Duplicate" in w for w in warnings)

    def test_no_duplicates(self) -> None:
        df = pd.DataFrame(columns=["x", "y", "z"])
        _, warnings = _sanitize_column_names(df)
        assert warnings == []


class TestParseCSV:
    def test_basic_csv(self) -> None:
        csv = b"name,age\nAlice,30\nBob,25\n"
        result = parse_csv(csv, "test.csv", MAX_ROWS, MAX_COLS)
        assert len(result.df) == 2
        assert list(result.df.columns) == ["name", "age"]

    def test_missing_values(self) -> None:
        csv = b"name,age\nAlice,\nBob,25\n"
        result = parse_csv(csv, "test.csv", MAX_ROWS, MAX_COLS)
        assert result.df["age"].isna().sum() == 1

    def test_empty_file_raises(self) -> None:
        with pytest.raises(UploadError, match="empty"):
            parse_csv(b"", "test.csv", MAX_ROWS, MAX_COLS)

    def test_header_only_raises(self) -> None:
        with pytest.raises(UploadError, match="no data rows"):
            parse_csv(b"name,age\n", "test.csv", MAX_ROWS, MAX_COLS)

    def test_row_limit_truncates(self) -> None:
        rows = "a,b\n" + "\n".join(f"{i},{i * 2}" for i in range(10))
        result = parse_csv(rows.encode(), "test.csv", max_rows=5, max_columns=MAX_COLS)
        assert len(result.df) == 5
        assert any("truncated" in w.lower() for w in result.warnings)

    def test_column_limit_raises(self) -> None:
        header = ",".join(f"col{i}" for i in range(10))
        row = ",".join("1" for _ in range(10))
        csv = f"{header}\n{row}\n".encode()
        with pytest.raises(UploadError, match="exceeding the limit"):
            parse_csv(csv, "test.csv", MAX_ROWS, max_columns=5)

    def test_utf8_encoding(self) -> None:
        csv = "name,city\nÄlice,München\n".encode()
        result = parse_csv(csv, "test.csv", MAX_ROWS, MAX_COLS)
        assert len(result.df) == 1

    def test_latin1_encoding(self) -> None:
        csv = "name,city\n\xe4lice,M\xfcnchen\n"  # latin-1
        result = parse_csv(csv.encode("latin-1"), "test.csv", MAX_ROWS, MAX_COLS)
        assert len(result.df) == 1

    def test_inferred_types_populated(self) -> None:
        csv = b"name,age,score\nAlice,30,95.5\nBob,25,87.2\n"
        result = parse_csv(csv, "test.csv", MAX_ROWS, MAX_COLS)
        assert "name" in result.inferred_types
        assert result.inferred_types["age"] in ("integer", "float")

    def test_numeric_na_values(self) -> None:
        csv = b"x\nNA\nnull\n1\n2\n"
        result = parse_csv(csv, "test.csv", MAX_ROWS, MAX_COLS)
        assert result.df["x"].isna().sum() == 2


class TestParseJSON:
    def test_basic_json(self) -> None:
        data = b'[{"name":"Alice","age":30},{"name":"Bob","age":25}]'
        result = parse_json(data, "test.json", MAX_ROWS, MAX_COLS)
        assert len(result.df) == 2

    def test_empty_json_raises(self) -> None:
        with pytest.raises(UploadError):
            parse_json(b"", "test.json", MAX_ROWS, MAX_COLS)

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(ProcessingError):
            parse_json(b"not json", "test.json", MAX_ROWS, MAX_COLS)
