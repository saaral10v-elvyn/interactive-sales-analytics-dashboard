"""Tests for the deterministic demo dataset."""

from pathlib import Path

import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal

from sales_dashboard.config import DEMO_END_DATE, DEMO_START_DATE
from sales_dashboard.demo import COLUMNS, build_demo_dataframe


def test_committed_demo_dataset_is_present_and_realistic(demo_csv_path: Path) -> None:
    assert demo_csv_path.exists()
    dataframe = pd.read_csv(demo_csv_path)

    assert list(dataframe.columns) == list(COLUMNS)
    assert len(dataframe) >= 2_000

    dates = pd.to_datetime(dataframe["order_date"])
    assert dates.min().date() == DEMO_START_DATE
    assert dates.max().date() == DEMO_END_DATE

    assert dataframe["product"].nunique() == 30
    assert dataframe["category"].nunique() == 6
    assert dataframe["region"].nunique() == 5
    assert dataframe["order_id"].nunique() > 1_000

    assert (dataframe["discount_percent"] > 0).any()
    assert (dataframe["quantity"] < 0).any()
    assert (dataframe["status"] == "Cancelled").any()
    assert (dataframe["status"] == "Returned").any()


def test_line_totals_are_internally_consistent(demo_csv_path: Path) -> None:
    dataframe = pd.read_csv(demo_csv_path)
    expected = (
        dataframe["quantity"] * dataframe["unit_price"] * (1 - dataframe["discount_percent"] / 100)
    )

    assert np.allclose(dataframe["line_total"], expected, atol=0.01)


def test_returns_are_negative_and_completed_sales_are_positive(demo_csv_path: Path) -> None:
    dataframe = pd.read_csv(demo_csv_path)

    returns = dataframe[dataframe["status"] == "Returned"]
    assert not returns.empty
    assert (returns["quantity"] < 0).all()
    assert (returns["line_total"] < 0).all()

    sales = dataframe[dataframe["status"] != "Returned"]
    assert (sales["quantity"] > 0).all()


def test_generator_is_deterministic() -> None:
    first = build_demo_dataframe()
    second = build_demo_dataframe()

    assert_frame_equal(first, second)


def test_committed_file_is_in_sync_with_generator(demo_csv_path: Path) -> None:
    committed = pd.read_csv(demo_csv_path)
    generated = build_demo_dataframe()

    assert len(committed) == len(generated)
    assert committed["order_id"].tolist() == generated["order_id"].tolist()
    assert committed["quantity"].tolist() == generated["quantity"].tolist()
    assert np.allclose(committed["line_total"], generated["line_total"], atol=0.01)
