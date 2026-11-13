"""Deterministic demo sales dataset.

Run ``python -m sales_dashboard.demo`` to regenerate
``data/sample/sales_demo.csv``. The seed and date range come from config.py.
"""

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from sales_dashboard.config import (
    DEMO_CSV_PATH,
    DEMO_END_DATE,
    DEMO_SEED,
    DEMO_START_DATE,
)

PRODUCTS: tuple[dict[str, object], ...] = (
    {"name": "Wireless Headphones", "category": "Electronics", "price": 2499},
    {"name": "Bluetooth Speaker", "category": "Electronics", "price": 1899},
    {"name": "Smart Watch", "category": "Electronics", "price": 6999},
    {"name": "USB-C Hub", "category": "Electronics", "price": 2799},
    {"name": "Laptop Stand", "category": "Electronics", "price": 1499},
    {"name": "Webcam", "category": "Electronics", "price": 3499},
    {"name": "Ergonomic Chair", "category": "Furniture", "price": 12999},
    {"name": "Standing Desk", "category": "Furniture", "price": 24999},
    {"name": "Bookshelf", "category": "Furniture", "price": 5999},
    {"name": "Filing Cabinet", "category": "Furniture", "price": 8999},
    {"name": "Desk Lamp", "category": "Furniture", "price": 1299},
    {"name": "Notebook Set", "category": "Office Supplies", "price": 499},
    {"name": "Gel Pen Pack", "category": "Office Supplies", "price": 249},
    {"name": "Printer Paper", "category": "Office Supplies", "price": 399},
    {"name": "Sticky Notes", "category": "Office Supplies", "price": 199},
    {"name": "Stapler", "category": "Office Supplies", "price": 349},
    {"name": "Coffee Maker", "category": "Home & Kitchen", "price": 4499},
    {"name": "Air Fryer", "category": "Home & Kitchen", "price": 8999},
    {"name": "Cookware Set", "category": "Home & Kitchen", "price": 6999},
    {"name": "Water Bottle", "category": "Home & Kitchen", "price": 799},
    {"name": "Blender", "category": "Home & Kitchen", "price": 3499},
    {"name": "Cotton T-Shirt", "category": "Apparel", "price": 799},
    {"name": "Denim Jacket", "category": "Apparel", "price": 3499},
    {"name": "Running Shoes", "category": "Apparel", "price": 2999},
    {"name": "Backpack", "category": "Apparel", "price": 1999},
    {"name": "Yoga Mat", "category": "Sports", "price": 999},
    {"name": "Dumbbell Set", "category": "Sports", "price": 4999},
    {"name": "Cricket Bat", "category": "Sports", "price": 2499},
    {"name": "Badminton Racket", "category": "Sports", "price": 1899},
    {"name": "Cycling Helmet", "category": "Sports", "price": 2299},
)

REGIONS: tuple[tuple[str, float], ...] = (
    ("North", 0.28),
    ("West", 0.24),
    ("South", 0.22),
    ("East", 0.18),
    ("Central", 0.08),
)

MONTH_FACTORS = {
    1: 0.88,
    2: 0.92,
    3: 1.02,
    4: 0.96,
    5: 1.00,
    6: 0.94,
    7: 0.98,
    8: 1.04,
    9: 1.08,
    10: 1.38,
    11: 1.48,
    12: 1.22,
}

WEEKDAY_FACTORS = (1.00, 0.96, 0.98, 1.04, 1.18, 1.30, 1.12)

STATUS_OPTIONS = ("Completed", "Cancelled", "Returned")
STATUS_PROBABILITIES = (0.965, 0.020, 0.015)

DISCOUNT_OPTIONS = (0, 5, 10, 15, 20)
DISCOUNT_PROBABILITIES = (0.45, 0.20, 0.18, 0.11, 0.06)

BASE_ORDERS_PER_DAY = 3.6
ORDER_LINE_COUNTS = (1, 2, 3, 4)
ORDER_LINE_PROBABILITIES = (0.36, 0.34, 0.20, 0.10)
QUANTITY_OPTIONS = (1, 2, 3, 4)
QUANTITY_PROBABILITIES = (0.60, 0.25, 0.10, 0.05)

COLUMNS = (
    "order_id",
    "order_date",
    "customer_id",
    "product",
    "category",
    "region",
    "quantity",
    "unit_price",
    "discount_percent",
    "line_total",
    "status",
)


def build_demo_dataframe(
    *,
    seed: int = DEMO_SEED,
    start: date = DEMO_START_DATE,
    end: date = DEMO_END_DATE,
) -> pd.DataFrame:
    """Build a deterministic, realistic line-item sales dataset."""
    if end < start:
        raise ValueError("The demo end date must be on or after the start date.")

    rng = np.random.default_rng(seed)
    days = pd.date_range(start=start, end=end, freq="D")

    product_weights = rng.lognormal(mean=0.0, sigma=0.55, size=len(PRODUCTS))
    product_weights = product_weights / product_weights.sum()

    region_names = np.array([name for name, _ in REGIONS])
    region_probabilities = np.array([weight for _, weight in REGIONS])

    rows: list[dict[str, object]] = []
    order_number = 1
    total_days = max(len(days) - 1, 1)

    for day_index, current_date in enumerate(days):
        growth = 0.85 + 0.35 * (day_index / total_days)
        expected_orders = (
            BASE_ORDERS_PER_DAY
            * growth
            * MONTH_FACTORS[current_date.month]
            * WEEKDAY_FACTORS[current_date.weekday()]
        )
        order_count = max(1, int(rng.poisson(expected_orders)))

        for _ in range(order_count):
            order_id = f"ORD-{order_number:05d}"
            order_number += 1
            customer_id = f"CUST-{int(rng.integers(1, 651)):04d}"
            region = str(rng.choice(region_names, p=region_probabilities))
            status = str(rng.choice(STATUS_OPTIONS, p=STATUS_PROBABILITIES))

            line_count = int(rng.choice(ORDER_LINE_COUNTS, p=ORDER_LINE_PROBABILITIES))
            product_indices = rng.choice(
                len(PRODUCTS),
                size=line_count,
                replace=False,
                p=product_weights,
            )

            for product_index in product_indices:
                product = PRODUCTS[int(product_index)]
                quantity = int(rng.choice(QUANTITY_OPTIONS, p=QUANTITY_PROBABILITIES))
                discount = int(rng.choice(DISCOUNT_OPTIONS, p=DISCOUNT_PROBABILITIES))

                if status == "Returned":
                    quantity = -quantity

                unit_price = int(product["price"])
                line_total = round(quantity * unit_price * (1 - discount / 100), 2)

                rows.append(
                    {
                        "order_id": order_id,
                        "order_date": current_date.date(),
                        "customer_id": customer_id,
                        "product": product["name"],
                        "category": product["category"],
                        "region": region,
                        "quantity": quantity,
                        "unit_price": unit_price,
                        "discount_percent": discount,
                        "line_total": line_total,
                        "status": status,
                    }
                )

    dataframe = pd.DataFrame(rows, columns=COLUMNS)
    dataframe = dataframe.sort_values(["order_date", "order_id"], kind="stable")
    return dataframe.reset_index(drop=True)


def write_demo_csv(path: Path = DEMO_CSV_PATH) -> pd.DataFrame:
    """Generate the demo dataset and save it as a CSV file."""
    dataframe = build_demo_dataframe()
    path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(path, index=False, date_format="%Y-%m-%d", float_format="%.2f")
    return dataframe


def main() -> None:
    """Regenerate the committed demo dataset."""
    dataframe = write_demo_csv()
    print(f"Wrote {len(dataframe):,} line items to {DEMO_CSV_PATH}")


if __name__ == "__main__":
    main()
