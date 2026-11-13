"""Shared pytest fixtures."""

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def demo_csv_path(project_root: Path) -> Path:
    return project_root / "data" / "sample" / "sales_demo.csv"


@pytest.fixture
def valid_csv_bytes() -> bytes:
    rows = [
        (
            "order_id,order_date,product,category,region,quantity,"
            "unit_price,discount_percent,line_total,status"
        ),
        "ORD-001,2026-01-15,Wireless Headphones,Electronics,North,2,2499,10,4498.20,Completed",
        "ORD-002,2026-01-16,Coffee Maker,Home & Kitchen,South,1,4499,0,4499.00,Completed",
        "ORD-002,2026-01-16,Water Bottle,Home & Kitchen,South,3,799,5,2277.15,Completed",
    ]
    return ("\n".join(rows) + "\n").encode("utf-8")
