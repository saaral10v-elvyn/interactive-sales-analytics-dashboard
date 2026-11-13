"""Tests for the lightweight dataset profile."""

import pandas as pd

from sales_dashboard.profiling import profile_dataset
from sales_dashboard.schema import detect_column_mapping


def test_profile_counts_missing_values_and_duplicates() -> None:
    dataframe = pd.DataFrame(
        {
            "order_id": ["A", "A", "B"],
            "order_date": ["2026-01-01", "2026-01-01", "2026-01-02"],
            "product": ["Desk Lamp", "Desk Lamp", "Yoga Mat"],
            "category": ["", "", "Sports"],
            "region": ["North", "North", ""],
            "quantity": ["1", "1", "2"],
            "line_total": ["100", "100", "250"],
        }
    )
    mapping = detect_column_mapping(dataframe.columns)

    profile = profile_dataset(dataframe, mapping)

    assert profile.row_count == 3
    assert profile.column_count == 7
    assert profile.missing_cells == 3
    assert profile.duplicate_rows == 1
    assert profile.order_count == 2
    assert profile.product_count == 2
    assert profile.category_count == 1
    assert profile.region_count == 1
    assert profile.net_revenue == 450
    assert profile.date_min.isoformat() == "2026-01-01"
    assert profile.date_max.isoformat() == "2026-01-02"
