"""Unit tests for data quality analysis."""

import pandas as pd

from app.analytics.quality import analyze_quality


def _make_df(**kwargs: list) -> pd.DataFrame:  # type: ignore[type-arg]
    return pd.DataFrame(kwargs)


class TestAnalyzeQuality:
    def test_no_issues_on_clean_data(self) -> None:
        df = _make_df(a=[1, 2, 3], b=["x", "y", "z"])
        report = analyze_quality(df, {"a": "integer", "b": "string"})
        assert report.total_rows == 3
        assert report.total_columns == 2
        assert report.duplicate_rows == 0
        assert not any(f.code == "DUPLICATE_ROWS" for f in report.findings)

    def test_duplicate_rows_detected(self) -> None:
        df = _make_df(a=[1, 2, 1], b=["x", "y", "x"])
        report = analyze_quality(df, {"a": "integer", "b": "string"})
        assert report.duplicate_rows == 1
        assert any(f.code == "DUPLICATE_ROWS" for f in report.findings)

    def test_missing_values_counted(self) -> None:
        df = _make_df(a=[1, None, 3], b=["x", "y", None])
        report = analyze_quality(df, {"a": "float", "b": "string"})
        a_info = next(c for c in report.columns if c.name == "a")
        b_info = next(c for c in report.columns if c.name == "b")
        assert a_info.missing_count == 1
        assert b_info.missing_count == 1

    def test_empty_column_warning(self) -> None:
        df = _make_df(a=[1, 2, 3], b=[None, None, None])
        report = analyze_quality(df, {"a": "integer", "b": "empty"})
        assert any(f.code == "EMPTY_COLUMN" and f.column == "b" for f in report.findings)

    def test_high_missing_warning(self) -> None:
        nones = [None] * 90
        vals = [1] * 10
        df = pd.DataFrame({"col": nones + vals})
        report = analyze_quality(df, {"col": "float"})
        codes = [f.code for f in report.findings]
        assert "HIGH_MISSING" in codes or "MODERATE_MISSING" in codes

    def test_empty_dataset_error(self) -> None:
        df = pd.DataFrame({"a": []})
        report = analyze_quality(df, {"a": "string"})
        assert any(f.code == "EMPTY_DATASET" for f in report.findings)

    def test_single_value_column_info(self) -> None:
        df = _make_df(a=[5, 5, 5, 5])
        report = analyze_quality(df, {"a": "integer"})
        assert any(f.code == "SINGLE_VALUE_COLUMN" and f.column == "a" for f in report.findings)

    def test_column_quality_missing_pct(self) -> None:
        df = _make_df(x=[1, 2, None, None])
        report = analyze_quality(df, {"x": "float"})
        col = report.columns[0]
        assert col.missing_pct == 50.0
