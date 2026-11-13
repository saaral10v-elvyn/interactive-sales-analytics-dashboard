"""Tests for CSV loading and friendly error handling."""

import pytest

from sales_dashboard.loading import DataLoadError, load_demo_dataset, read_csv_bytes


def test_valid_csv_loads_with_metadata(valid_csv_bytes: bytes) -> None:
    dataset = read_csv_bytes(valid_csv_bytes, "sales.csv")

    assert dataset.filename == "sales.csv"
    assert dataset.encoding == "utf-8"
    assert dataset.delimiter == ","
    assert dataset.mapping.is_complete
    assert dataset.profile.row_count == 3
    assert dataset.profile.order_count == 2
    assert dataset.profile.product_count == 3
    assert dataset.profile.net_revenue == pytest.approx(11274.35)


def test_semicolon_delimiter_is_detected(valid_csv_bytes: bytes) -> None:
    semicolon_csv = valid_csv_bytes.replace(b",", b";")

    dataset = read_csv_bytes(semicolon_csv, "sales.csv")

    assert dataset.delimiter == ";"
    assert dataset.profile.row_count == 3


def test_cp1252_encoding_is_detected(valid_csv_bytes: bytes) -> None:
    text = valid_csv_bytes.decode("utf-8").replace("Wireless Headphones", "Café Headphones")
    payload = text.encode("cp1252")

    dataset = read_csv_bytes(payload, "sales.csv")

    assert dataset.encoding == "cp1252"
    assert dataset.dataframe.loc[0, "product"] == "Café Headphones"


def test_currency_formatted_line_totals_are_profiled() -> None:
    payload = (
        "order_date,product,quantity,unit_price,line_total\n"
        '2026-01-15,Desk Lamp,1,1299,"₹1,23,456.50"\n'
    ).encode()

    dataset = read_csv_bytes(payload, "sales.csv")

    assert dataset.profile.net_revenue == pytest.approx(123456.50)


def test_missing_required_column_loads_for_manual_mapping() -> None:
    payload = b"product,quantity,unit_price\nDesk Lamp,1,1299\n"

    dataset = read_csv_bytes(payload, "sales.csv")

    assert dataset.profile.row_count == 1
    assert not dataset.mapping.is_complete
    assert "order_date" in dataset.mapping.missing_required
    assert dataset.mapping.fields["product"] == "product"
    assert dataset.mapping.fields["quantity"] == "quantity"
    assert dataset.mapping.fields["unit_price"] == "unit_price"


def test_utf16_csv_is_decoded() -> None:
    payload = "order_date,product,quantity,unit_price\n2026-01-15,Desk Lamp,1,1299\n".encode(
        "utf-16"
    )

    dataset = read_csv_bytes(payload, "sales.csv")

    assert dataset.encoding == "utf-16"
    assert dataset.profile.row_count == 1


def test_unsupported_file_type_is_rejected() -> None:
    with pytest.raises(DataLoadError, match="Unsupported file type"):
        read_csv_bytes(b"anything", "sales.xlsx")


def test_empty_file_is_rejected() -> None:
    with pytest.raises(DataLoadError, match="file is empty"):
        read_csv_bytes(b"   \n", "sales.csv")


def test_demo_csv_loads_through_loader(demo_csv_path) -> None:
    dataset = load_demo_dataset(demo_csv_path)

    assert dataset.source == "demo"
    assert dataset.profile.row_count > 1_000
    assert dataset.profile.net_revenue is not None
    assert dataset.mapping.is_complete
