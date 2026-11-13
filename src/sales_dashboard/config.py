"""Central configuration for the application.

Currency, upload limits and demo-data settings live here so they can be changed
in one place.
"""

from datetime import date
from pathlib import Path

APP_NAME = "Interactive Sales Analytics Dashboard"
APP_SHORT_NAME = "Sales Analytics"
APP_TAGLINE = "Turn a sales CSV into a clear, interactive view of your business."
APP_VERSION = "1.0.0"

# Change these two values to switch the whole application's currency.
CURRENCY_CODE = "INR"
CURRENCY_SYMBOL = "₹"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SAMPLE_DATA_DIR = PROJECT_ROOT / "data" / "sample"
DEMO_CSV_PATH = SAMPLE_DATA_DIR / "sales_demo.csv"

DEMO_SEED = 42
DEMO_START_DATE = date(2025, 5, 1)
DEMO_END_DATE = date(2026, 10, 31)

MAX_UPLOAD_MB = 50
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024
MAX_ROWS = 250_000
LARGE_DATASET_ROWS = 100_000

SUPPORTED_ENCODINGS = ("utf-8", "utf-8-sig", "cp1252", "latin-1")
SUPPORTED_DELIMITERS = ",;\t|"
ALLOWED_EXTENSIONS = (".csv",)

# Brand colours for custom UI elements and, later, charts.
BRAND_COLOR = "#0F766E"
ACCENT_COLOR = "#14B8A6"
SLATE_900 = "#0F172A"
SLATE_600 = "#475569"
SLATE_200 = "#E2E8F0"
