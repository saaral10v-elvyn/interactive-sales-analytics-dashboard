"""Tests for Data Explorer search behaviour."""

import pandas as pd

from sales_dashboard.explorer import search_dataframe


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": ["ORD-001", "ORD-002", "ORD-003"],
            "order_date": pd.to_datetime(["2026-01-05", "2026-02-10", "2026-03-15"]),
            "product": ["Wireless Headphones", "Coffee Maker", "Water Bottle"],
            "revenue": [4498.2, 4499.0, 2277.15],
        }
    )


def test_search_matches_text_case_insensitively() -> None:
    result = search_dataframe(_frame(), "coffee")

    assert result["order_id"].tolist() == ["ORD-002"]
    assert result["product"].tolist() == ["Coffee Maker"]


def test_search_matches_order_ids_dates_and_multiple_terms() -> None:
    result = search_dataframe(_frame(), "ord-00")

    assert len(result) == 3

    february = search_dataframe(_frame(), "2026-02")
    assert february["order_id"].tolist() == ["ORD-002"]


def test_search_treats_regex_characters_literally() -> None:
    dataframe = pd.DataFrame(
        {
            "product": ["A.B", "AXB", "C*D"],
            "order_id": ["1", "2", "3"],
        }
    )

    dotted = search_dataframe(dataframe, "A.B")
    starred = search_dataframe(dataframe, "C*D")

    assert dotted["order_id"].tolist() == ["1"]
    assert starred["order_id"].tolist() == ["3"]


def test_blank_search_returns_every_row() -> None:
    for query in ("", "   "):
        result = search_dataframe(_frame(), query)

        assert len(result) == 3
        assert result is not _frame()


def test_search_returns_an_empty_frame_when_nothing_matches() -> None:
    result = search_dataframe(_frame(), "does-not-exist")

    assert result.empty
    assert list(result.columns) == list(_frame().columns)


def test_search_handles_missing_values_and_numeric_only_data() -> None:
    dataframe = pd.DataFrame(
        {
            "product": pd.Series(["Lamp", None, ""], dtype="string"),
            "revenue": [100.0, 200.0, 300.0],
        }
    )

    assert search_dataframe(dataframe, "lamp")["revenue"].tolist() == [100.0]
    assert len(search_dataframe(dataframe, "999")) == 0

    numeric_only = pd.DataFrame({"revenue": [100.0, 200.0]})
    assert len(search_dataframe(numeric_only, "100")) == 2
