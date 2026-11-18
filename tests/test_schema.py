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


def test_no_alias_is_shared_between_two_fields() -> None:
    owners: dict[str, list[str]] = {}
    for field, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            owners.setdefault(alias, []).append(field)

    clashes = {alias: fields for alias, fields in owners.items() if len(fields) > 1}
    assert not clashes, f"Aliases claimed by more than one field: {clashes}"


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


def test_detects_classic_models_columns() -> None:
    mapping = detect_column_mapping(
        [
            "ORDERNUMBER",
            "ORDERLINENUMBER",
            "PRODUCTCODE",
            "PRODUCTNAME",
            "PRODUCTLINE",
            "QUANTITYORDERED",
            "PRICEEACH",
            "SALES",
            "ORDERDATE",
            "STATUS",
            "TERRITORY",
            "MSRP",
        ]
    )

    assert mapping.is_complete
    assert mapping.fields == {
        "order_id": "ORDERNUMBER",
        "order_date": "ORDERDATE",
        "product": "PRODUCTNAME",
        "category": "PRODUCTLINE",
        "region": "TERRITORY",
        "quantity": "QUANTITYORDERED",
        "unit_price": "PRICEEACH",
        "line_total": "SALES",
        "status": "STATUS",
    }
    assert set(mapping.confidence.values()) == {1.0}
    assert set(mapping.methods.values()) == {"header"}


def test_detects_classic_models_columns_in_lowercase() -> None:
    mapping = detect_column_mapping(
        [
            "ordernumber",
            "orderdate",
            "productname",
            "productline",
            "quantityordered",
            "priceeach",
            "sales",
        ]
    )

    assert mapping.fields["order_id"] == "ordernumber"
    assert mapping.fields["order_date"] == "orderdate"
    assert mapping.fields["product"] == "productname"
    assert mapping.fields["category"] == "productline"
    assert mapping.fields["quantity"] == "quantityordered"
    assert mapping.fields["unit_price"] == "priceeach"
    assert mapping.fields["line_total"] == "sales"
    assert mapping.is_complete


def test_detects_aliases_with_spaces_underscores_and_punctuation() -> None:
    mapping = detect_column_mapping(
        [
            "Order Number",
            "Order-Date",
            "Product_Name",
            "Product-Line",
            "Quantity Ordered",
            "Price/Each",
            "Total Sales",
            "Status",
            "Territory",
        ]
    )

    assert mapping.fields == {
        "order_id": "Order Number",
        "order_date": "Order-Date",
        "product": "Product_Name",
        "category": "Product-Line",
        "region": "Territory",
        "quantity": "Quantity Ordered",
        "unit_price": "Price/Each",
        "line_total": "Total Sales",
        "status": "Status",
    }
    assert mapping.is_complete


def test_existing_aliases_still_match() -> None:
    mapping = detect_column_mapping(
        ["Order ID", "Purchase Date", "Item", "Qty", "Price", "Amount", "Territory"]
    )

    assert mapping.fields["order_id"] == "Order ID"
    assert mapping.fields["order_date"] == "Purchase Date"
    assert mapping.fields["product"] == "Item"
    assert mapping.fields["quantity"] == "Qty"
    assert mapping.fields["unit_price"] == "Price"
    assert mapping.fields["line_total"] == "Amount"
    assert mapping.fields["region"] == "Territory"


def test_fuzzy_header_matching_still_works_after_new_aliases() -> None:
    mapping = detect_column_mapping(["Ordre Date", "Prodct Name", "Qty", "Price"])

    assert mapping.fields["order_date"] == "Ordre Date"
    assert mapping.fields["product"] == "Prodct Name"
    assert mapping.methods["order_date"] == "header (fuzzy)"
    assert mapping.methods["product"] == "header (fuzzy)"
    assert 0.75 <= mapping.confidence["order_date"] <= 0.95


def test_product_name_is_preferred_over_product_code() -> None:
    mapping = detect_column_mapping(
        ["Order Number", "Order Date", "PRODUCTCODE", "PRODUCTNAME", "Qty", "Price"]
    )

    assert mapping.fields["product"] == "PRODUCTNAME"
    assert "PRODUCTCODE" not in mapping.fields.values()


def test_duplicate_normalised_headers_map_only_once() -> None:
    mapping = detect_column_mapping(
        ["Order Date", "order_date", "ORDERDATE", "Product", "Qty", "Price"]
    )

    assert mapping.fields["order_date"] == "Order Date"
    assert list(mapping.fields.values()).count("order_date") == 0
    assert list(mapping.fields.values()).count("ORDERDATE") == 0
    assert len(mapping.fields.values()) == len(set(mapping.fields.values()))


def test_ambiguous_columns_are_never_assigned_to_two_fields() -> None:
    mapping = detect_column_mapping(
        ["Date", "Description", "Qty", "Price", "Sales", "Total Sales", "Amount"]
    )

    assert mapping.fields["product"] == "Description"
    assert mapping.fields["line_total"] in {"Sales", "Total Sales", "Amount"}
    assert len(mapping.fields.values()) == len(set(mapping.fields.values()))


def test_manual_override_beats_automatic_detection_and_is_preserved() -> None:
    columns = [
        "ORDERNUMBER",
        "ORDERDATE",
        "PRODUCTCODE",
        "PRODUCTNAME",
        "PRODUCTLINE",
        "QUANTITYORDERED",
        "PRICEEACH",
        "SALES",
        "STATUS",
    ]

    mapping = resolve_mapping(columns, {"product": "PRODUCTCODE"})

    assert mapping.fields["product"] == "PRODUCTCODE"
    assert mapping.confidence["product"] == 1.0
    assert mapping.methods["product"] == "manual"
    assert mapping.fields["order_id"] == "ORDERNUMBER"
    assert mapping.methods["order_id"] == "header"
    assert "PRODUCTNAME" not in mapping.fields.values()
    assert mapping.is_complete


def test_missing_required_fields_are_not_invented_for_classic_models() -> None:
    mapping = detect_column_mapping(
        ["ORDERNUMBER", "ORDERDATE", "PRODUCTNAME", "PRICEEACH", "SALES"]
    )

    assert "quantity" in mapping.missing_required
    assert "quantity" not in mapping.fields
    assert not mapping.is_complete
