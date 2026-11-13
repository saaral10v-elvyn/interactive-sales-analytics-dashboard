"""Tests for header normalisation, confidence and manual mapping."""

import pandas as pd
import pytest

from sales_dashboard.schema import (
    FIELD_ALIASES,
    MappingError,
    detect_column_mapping,
    detect_dataframe_mapping,
    mapping_table_rows,
    normalize_column_name,
    resolve_mapping,
)


def test_normalize_column_name_handles_spacing_and_punctuation() -> None:
    assert normalize_column_name(" Order Date ") == "order_date"
    assert normalize_column_name("Qty.") == "qty"
    assert normalize_column_name("Total Amount (INR)") == "total_amount_inr"


def test_detects_common_aliases() -> None:
    mapping = detect_column_mapping(
        ["Order ID", "Order Date", "Product Name", "Qty", "Price", "Amount"]
    )

    assert mapping.is_complete
    assert mapping.fields["order_id"] == "Order ID"
    assert mapping.fields["order_date"] == "Order Date"
    assert mapping.fields["product"] == "Product Name"
    assert mapping.fields["quantity"] == "Qty"
    assert mapping.fields["unit_price"] == "Price"
    assert mapping.fields["line_total"] == "Amount"


def test_missing_required_columns_are_reported() -> None:
    mapping = detect_column_mapping(["Date", "Item"])

    assert not mapping.is_complete
    assert "quantity" in mapping.missing_required
    assert "unit_price or line_total" in mapping.missing_required


def test_every_alias_is_normalised() -> None:
    for aliases in FIELD_ALIASES.values():
        for alias in aliases:
            assert normalize_column_name(alias) == alias


def test_exact_header_matches_have_full_confidence() -> None:
    mapping = detect_column_mapping(["Order Date", "Product", "Qty", "Price"])

    assert mapping.confidence["order_date"] == 1.0
    assert mapping.methods["order_date"] == "header"
    assert not mapping.low_confidence_fields


def test_content_date_and_product_fallbacks_are_low_confidence() -> None:
    dataframe = pd.DataFrame(
        {
            "when": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "thing": ["Pen", "Pad", "Pen"],
            "qty": ["1", "2", "1"],
            "price": ["10", "20", "10"],
        }
    )

    mapping = detect_dataframe_mapping(dataframe)

    assert mapping.fields["order_date"] == "when"
    assert mapping.methods["order_date"] == "content"
    assert mapping.fields["product"] == "thing"
    assert mapping.confidence["product"] < 0.75
    assert mapping.low_confidence_fields


def test_resolve_mapping_applies_manual_overrides() -> None:
    columns = ["Date", "Item", "Qty", "Price", "Amount"]

    mapping = resolve_mapping(
        columns,
        {
            "order_date": "Date",
            "product": "Item",
            "quantity": "Qty",
            "unit_price": "Price",
            "line_total": None,
        },
    )

    assert mapping.is_complete
    assert mapping.fields["unit_price"] == "Price"
    assert "line_total" not in mapping.fields
    assert mapping.confidence["order_date"] == 1.0
    assert mapping.methods["order_date"] == "manual"


def test_resolve_mapping_rejects_duplicate_source_columns() -> None:
    with pytest.raises(MappingError, match="mapped to both"):
        resolve_mapping(
            ["Date", "Item", "Qty", "Price"],
            {"product": "Item", "category": "Item"},
        )


def test_resolve_mapping_rejects_unknown_columns() -> None:
    with pytest.raises(MappingError, match="not present"):
        resolve_mapping(["Date", "Item", "Qty", "Price"], {"product": "Missing"})


def test_removing_a_required_field_reports_it_missing() -> None:
    mapping = resolve_mapping(
        ["Date", "Item", "Qty", "Price"],
        {
            "order_date": "Date",
            "product": None,
            "quantity": "Qty",
            "unit_price": "Price",
        },
    )

    assert not mapping.is_complete
    assert "product" in mapping.missing_required


def test_mapping_table_marks_low_confidence_rows() -> None:
    mapping = detect_dataframe_mapping(
        pd.DataFrame(
            {
                "when": ["2026-01-01", "2026-01-02"],
                "name": ["Pen", "Pad"],
                "num": ["1", "2"],
            }
        )
    )
    rows = {row["Field"]: row for row in mapping_table_rows(mapping)}

    assert rows["order_date"]["Status"] in {"Detected", "Review suggested"}
    assert rows["quantity"]["Status"] == "Not detected"
