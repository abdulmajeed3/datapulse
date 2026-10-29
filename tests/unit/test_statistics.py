"""Unit tests for summary statistics computation."""

import pandas as pd
import pytest

from app.analytics.statistics import compute_statistics


class TestNumericStats:
    def test_basic_numeric(self) -> None:
        df = pd.DataFrame({"v": [1.0, 2.0, 3.0, 4.0, 5.0]})
        report = compute_statistics(df, {"v": "float"})
        col = report.columns[0]
        assert col.numeric is not None
        assert col.numeric.count == 5
        assert col.numeric.min == 1.0
        assert col.numeric.max == 5.0
        assert col.numeric.mean == pytest.approx(3.0)
        assert col.numeric.median == pytest.approx(3.0)

    def test_all_missing(self) -> None:
        df = pd.DataFrame({"v": [None, None, None]})
        report = compute_statistics(df, {"v": "float"})
        col = report.columns[0]
        assert col.numeric is not None
        assert col.numeric.count == 0
        assert col.numeric.mean is None

    def test_single_value(self) -> None:
        df = pd.DataFrame({"v": [42.0]})
        report = compute_statistics(df, {"v": "float"})
        col = report.columns[0]
        assert col.numeric is not None
        assert col.numeric.count == 1
        assert col.numeric.min == 42.0
        assert col.numeric.max == 42.0

    def test_nonfinite_values_excluded(self) -> None:
        df = pd.DataFrame({"v": [1.0, float("inf"), float("nan"), 3.0]})
        report = compute_statistics(df, {"v": "float"})
        col = report.columns[0]
        assert col.numeric is not None
        # NaN becomes missing; inf becomes None in safe_float
        assert col.numeric.max is None or col.numeric.max != float("inf")

    def test_std_not_none_with_multiple_values(self) -> None:
        df = pd.DataFrame({"v": [1.0, 2.0, 3.0]})
        report = compute_statistics(df, {"v": "float"})
        col = report.columns[0]
        assert col.numeric is not None
        assert col.numeric.std is not None


class TestCategoricalStats:
    def test_basic_categorical(self) -> None:
        df = pd.DataFrame({"cat": ["a", "b", "a", "c", "b", "a"]})
        report = compute_statistics(df, {"cat": "string"})
        col = report.columns[0]
        assert col.categorical is not None
        assert col.categorical.count == 6
        assert col.categorical.unique == 3
        assert len(col.categorical.top_values) > 0
        # "a" should be the most frequent
        assert col.categorical.top_values[0]["value"] == "a"
        assert col.categorical.top_values[0]["count"] == 3

    def test_missing_values_in_categorical(self) -> None:
        df = pd.DataFrame({"cat": ["a", None, "b", None]})
        report = compute_statistics(df, {"cat": "string"})
        col = report.columns[0]
        assert col.categorical is not None
        assert col.categorical.missing == 2
        assert col.categorical.count == 2

    def test_all_unique(self) -> None:
        df = pd.DataFrame({"cat": ["x", "y", "z"]})
        report = compute_statistics(df, {"cat": "string"})
        col = report.columns[0]
        assert col.categorical is not None
        assert col.categorical.unique == 3


class TestDatetimeStats:
    def test_datetime_range(self) -> None:
        dates = pd.to_datetime(["2024-01-01", "2024-06-15", "2024-12-31"])
        df = pd.DataFrame({"dt": dates})
        report = compute_statistics(df, {"dt": "datetime"})
        col = report.columns[0]
        assert col.datetime is not None
        assert col.datetime.count == 3
        assert "2024-01-01" in (col.datetime.earliest or "")
        assert "2024-12-31" in (col.datetime.latest or "")

    def test_datetime_with_missing(self) -> None:
        df = pd.DataFrame({"dt": pd.to_datetime(["2024-01-01", None, "2024-12-31"])})
        report = compute_statistics(df, {"dt": "datetime"})
        col = report.columns[0]
        assert col.datetime is not None
        assert col.datetime.missing == 1
        assert col.datetime.count == 2


class TestStatisticsReport:
    def test_total_rows_and_columns(self) -> None:
        df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"], "c": [0.1, 0.2, 0.3]})
        report = compute_statistics(df, {"a": "integer", "b": "string", "c": "float"})
        assert report.total_rows == 3
        assert report.total_columns == 3
        assert len(report.columns) == 3
