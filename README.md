# Interactive Sales Analytics Dashboard

A portfolio-quality sales analytics application built with Python, Streamlit,
Pandas and Plotly. A business user can upload a sales CSV, validate and clean
it, explore interactive KPIs and charts, filter results, and download the
processed data.

**Current status:** Complete — v1.0.0. All six milestones are implemented and
verified locally.

## Overview

The app is designed for people who do not want to write code or wrestle with
spreadsheets. The application provides:

- A polished Home page with a clear product introduction.
- One-click loading of a bundled demo dataset.
- CSV upload with automatic encoding and delimiter detection, friendly errors,
  and the existing 50 MB / 250,000-row limits.
- Automatic detection of common column names and aliases, with a confidence
  indicator and a manual mapping override for uncertain matches.
- A structured validation report with severity, check code, description,
  affected row count, action taken and example values.
- Reusable cleaning functions for dates, numbers, text, duplicates, revenue,
  discounts, statuses, returns and outliers.
- A downloadable sample CSV and a complete column-format guide.
- An Overview dashboard with five KPI cards, period-over-period comparisons,
  interactive Plotly charts and deterministic business insights.
- A Products page with a sortable performance table, top-10 revenue ranking,
  Pareto analysis with an 80% threshold, and per-product drill-down.
- A Regions page with a regional performance table, revenue-by-region chart,
  category-by-region stacked bars and a multi-line regional revenue trend.
- A Data Explorer with global filters, case-insensitive search, column selection,
  row limits and sortable previews of the cleaned data.
- CSV downloads for the filtered view, the full cleaned dataset and the
  data-quality report, with Excel-friendly UTF-8 encoding.
- Shared sidebar filters for date presets and ranges, category, region, product
  and status. Selections persist across pages and reset when the dataset changes.
- A privacy note explaining that uploaded data is processed in memory only.

The demo dataset spans approximately 18 months and includes 30 products across
6 categories, 5 regions, multiple line items per order, discounts, cancellations
and returns.

## Screenshots

Captured from the running app with the bundled demo dataset.

| Home and preparation | Overview |
|---|---|
| ![Home page with the upload card, demo loader and CSV format guide](docs/screenshots/01-home.png) | ![Overview page with KPI cards, revenue trend and category charts](docs/screenshots/03-overview.png) |

| Products | Regions |
|---|---|
| ![Products page with the performance table, top-10 chart and Pareto analysis](docs/screenshots/04-products.png) | ![Regions page with regional performance and revenue charts](docs/screenshots/05-regions.png) |

| Data Explorer and exports | Data-quality report |
|---|---|
| ![Data Explorer with search, column selection and download buttons](docs/screenshots/06-data-explorer.png) | ![Data-quality report with summary cards, issues and downloads](docs/screenshots/02-quality-report.png) |

## Technology stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| App framework | Streamlit |
| Data processing | Pandas, NumPy |
| Visualisation | Plotly |
| Testing and linting | pytest, Ruff |
| CI | GitHub Actions |

The app requires Streamlit 1.59 or newer (for `persist_state`) and was
verified locally with Streamlit 1.67.0.

## Architecture

```text
CSV upload / demo file
        │
        ▼
loading.py      encoding, delimiter and size checks
        │
        ▼
schema.py       column detection, aliases, confidence, manual overrides
        │
        ▼
validation.py   issues with severity, affected rows and examples
        │
        ▼
cleaning.py     typed canonical columns, revenue, discounts, returns
        │
        ▼
filters.py      one shared FilterState for every page
        │
        ├──▶ analytics.py ──▶ ui/charts.py, ui/tables.py  (Overview, Products, Regions)
        └──▶ explorer.py  ──▶ exports.py                  (Data Explorer, downloads)
```

Design choices:

- Business logic lives in pure functions (`analytics.py`, `filters.py`,
  `cleaning.py`, `explorer.py`, `exports.py`) with no Streamlit imports. The UI
  layers only format and render their results.
- Every page reads the same cleaned dataframe and applies the same
  `FilterState`, so a filter set on Overview changes Products, Regions and the
  Data Explorer identically.
- Session state is limited to the loaded file, the cleaned result, the shared
  filter store and one-shot flash messages. Uploaded bytes are never written to
  disk.
- The app fails closed: a blocked cleaning result hides the analytical pages,
  missing optional columns explain themselves, and an unexpected page error
  shows a friendly retry screen instead of a traceback.

## Quickstart (Windows PowerShell)

```powershell
cd path\to\Interactive-sales-analytics-dashboard
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
streamlit run app.py
```

Open the URL Streamlit prints, usually <http://localhost:8501>.

On macOS or Linux, create the environment with `python3 -m venv .venv` and
activate it with `source .venv/bin/activate`.

If PowerShell blocks virtual-environment activation, allow it for the current
terminal session only:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

For a runtime-only install:

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

The entry point adds `src/` to the import path automatically, so an editable
install is optional. To install the package itself for development:

```powershell
python -m pip install -e .
```

## Using the app

1. Start the app with `streamlit run app.py`.
2. Click **Load demo dataset** to explore without a file, or upload a CSV.
3. Review the dataset overview and raw preview.
4. Check the **Schema detection** table. If a required field is missing or a
   match is low-confidence, open **Review or override column mapping**, choose
   the correct source columns and click **Apply mapping**.
5. If the file contains ambiguous dates such as `03/04/2026`, choose **Day first
   (DMY)** or **Month first (MDY)**. The app does not guess.
6. Click **Validate and clean data**.
7. Review the **Data-quality report**, including any prominent warning when more
   than 20% of rows were removed. Analysis is blocked when no usable rows remain.
8. Open **Overview** in the sidebar. The dashboard appears only after a valid
   cleaned dataset exists.
9. Use the shared sidebar filters to change the date preset or range, category,
   region, product or status. Filters persist across pages and reset when a new
   dataset is loaded.
10. Open **Products** to sort product performance, inspect the top-10 ranking and
    Pareto analysis, and drill into one product's revenue trend.
11. Open **Regions** to compare regional performance, category mix and regional
    revenue trends.
12. Open **Data Explorer** to search the filtered rows, choose preview columns,
    limit the table rows and download the matching data.
13. Switch the revenue trend between daily, weekly and monthly aggregation, then
    hover, zoom or pan any chart.
14. Download the cleaned dataset or data-quality report from the Home page, or
    grab filtered and full exports from the Data Explorer.
15. Use **Download sample CSV** to see the expected format.
16. Use **Clear loaded dataset** to remove the file and cleaning result from the
    current session.

### Dashboard metrics

The Overview page calculates every metric from the same filtered rows:

| Metric | Definition |
|---|---|
| Total revenue | Sum of net revenue, after discounts and returns |
| Total orders | Distinct non-empty `order_id` values; blank IDs count individually. Without `order_id`, each row is one order. |
| Average order value | Total revenue ÷ total orders (zero when there are no orders) |
| Total units sold | Sum of `quantity`, including negative returns |
| Total products | Distinct non-empty product names |

Every KPI is compared with the immediately preceding period of equal length.
The comparison period is shown under each card. Absolute and percentage changes
are displayed; when the previous value is zero, the percentage is shown as
unavailable instead of dividing by zero. For an all-time selection, the previous
period usually predates the dataset and the cards say so explicitly.

Date presets are anchored to the dataset's maximum date rather than today's
date. The default is the last 90 days so a comparison period normally exists.

### Products analytics

The Products page uses the same filtered rows as the Overview:

| Element | Behaviour |
|---|---|
| Product performance | Revenue, units sold, distinct orders, average order value and revenue share per product, sorted by revenue by default. |
| Revenue share | Product revenue ÷ total net revenue. When total net revenue is zero or negative, share is shown as unavailable instead of a misleading percentage. |
| Top 10 products | The ten highest-revenue products in an interactive bar chart. |
| Pareto analysis | Positive-revenue products ranked from highest to lowest, with cumulative revenue share and the first product that reaches 80%. Return-only products are excluded so the cumulative line ends at 100%. |
| Product drill-down | Revenue, units, orders and AOV for the selected product, plus a daily, weekly or monthly revenue trend. |

### Regions analytics

| Element | Behaviour |
|---|---|
| Regional performance | Revenue, orders, units, average order value and revenue share by region, sorted by revenue by default. |
| Revenue by region | Horizontal bar chart ranked by net revenue. |
| Category mix by region | Stacked bars showing each category's revenue within every region. |
| Regional revenue trend | Multi-line revenue trend with missing periods filled with zero so lines stay continuous. |

Blank regions are grouped as **Unknown region** and blank categories as
**Uncategorised**. If the cleaned dataset has no `region` column, the Regions
page explains that the analysis is unavailable rather than failing. Empty
filtered selections show friendly empty states on every table and chart.

### Data Explorer and exports

The Data Explorer uses the same globally filtered rows as every other page and
adds page-local controls:

| Element | Behaviour |
|---|---|
| Search | Case-insensitive literal search across text and date columns. Matching rows update immediately. |
| Columns to preview | Any subset of cleaned columns, in the order shown. This only affects the table preview. |
| Rows to display | 25, 50, 100, 250, 500 or all matching rows. The preview is capped by default to keep the page responsive. |
| Filtered data download | Every row matching the current global filters and search, with all cleaned columns. |
| Full cleaned data download | The complete cleaned dataset, independent of filters and search. |
| Quality report download | Summary metrics plus every validation issue with severity, code, affected rows, action and examples. |

Exports are UTF-8 CSV files with a byte-order mark, so Excel opens Indian digit
grouping and non-ASCII product names correctly. Download filenames include the
source filename and a timestamp. The Home page also offers the cleaned dataset
and quality report immediately after cleaning.

## CSV format

Required columns:

| Column | Requirement | Notes |
|---|---|---|
| `order_date` | Required | Sale date; `YYYY-MM-DD` recommended |
| `product` | Required | Product or item name |
| `quantity` | Required | Units sold; negative values are returns |
| `unit_price` | One of `unit_price` / `line_total` | Price per unit |
| `line_total` | One of `unit_price` / `line_total` | Net amount for the line |

Recommended and optional columns:

| Column | Requirement | Notes |
|---|---|---|
| `order_id` | Recommended | Used to count distinct orders |
| `category` | Optional | Product category |
| `region` | Optional | Sales region or territory |
| `discount_percent` | Optional | Discount from 0 to 100 |
| `status` | Optional | e.g. Completed, Cancelled, Returned |
| `customer_id` | Optional | Customer identifier |

Common aliases are detected automatically. For example, `Date`, `Purchase Date`,
`Qty`, `Price`, `Amount`, `Territory` and `Product Name` are accepted. Matching is
case-insensitive and ignores spaces and punctuation. Classic Models headers such
as `ORDERNUMBER`, `ORDERDATE`, `PRODUCTNAME`, `PRODUCTLINE`, `QUANTITYORDERED`,
`PRICEEACH` and `SALES` are recognised too. Each detected field carries a
confidence score; low-confidence matches can be overridden manually on the Home
page. A column can only be mapped to one field.

### Dates and ambiguity

ISO dates (`2026-01-15`) are recommended. Day-first (`15/04/2026`) and
month-first (`04/15/2026`) dates are both supported. A value such as
`03/04/2026` is ambiguous: it could mean 3 April or 4 March. When such values are
present, the app asks for an explicit **DMY** or **MDY** decision instead of
guessing. Invalid or blank dates are reported and their rows are dropped.

### Cleaning rules

| Area | Behaviour |
|---|---|
| Duplicates | Exact duplicate rows are removed; the first copy is kept. Different products sharing an `order_id` remain as legitimate line items. |
| Missing required values | Rows missing `order_date`, `product`, `quantity` or usable revenue are dropped and reported. |
| Text | Whitespace is trimmed and category, region and status labels are standardised. |
| Status | `Cancelled`, `Refunded` and `Void` records are excluded by default when a status column exists. `Returned` stays in the data. |
| Returns | Negative quantities are preserved and netted against revenue. |
| Revenue | A supplied `line_total` is used when available; otherwise revenue is `quantity × unit_price × (1 − discount / 100)`. |
| Discounts | `discount_percent` is a percentage from 0 to 100. If every value is between 0 and 1, it is treated as a fraction (`0.10` = 10%). Out-of-range discounts are reported and use 0 for the calculation. |
| Outliers | Unusual quantity or revenue values are flagged and preserved, never removed silently. |
| Missing `order_id` | Each row is counted as one order, and the report explains this. |

If more than 20% of rows are removed, the report shows a prominent warning. If no
usable rows remain, analysis is blocked with an explanation.

## Project structure

```text
.
├── app.py
├── src/sales_dashboard/
│   ├── config.py
│   ├── models.py
│   ├── schema.py
│   ├── dates.py
│   ├── parsing.py
│   ├── profiling.py
│   ├── loading.py
│   ├── validation.py
│   ├── cleaning.py
│   ├── filters.py
│   ├── analytics.py
│   ├── explorer.py
│   ├── exports.py
│   ├── formatting.py
│   ├── state.py
│   ├── demo.py
│   ├── ui/
│   │   ├── layout.py
│   │   ├── components.py
│   │   ├── preparation.py
│   │   ├── filters.py
│   │   ├── charts.py
│   │   ├── dashboard.py
│   │   ├── tables.py
│   │   ├── errors.py
│   │   └── sidebar.py
│   └── pages/
│       ├── home.py
│       ├── overview.py
│       ├── products.py
│       ├── regions.py
│       └── explorer.py
├── data/sample/sales_demo.csv
├── docs/
│   ├── DEPLOYMENT.md
│   └── screenshots/
├── tests/
├── .streamlit/config.toml
├── .github/workflows/ci.yml
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
└── README.md
```

## Demo dataset

The demo CSV is committed at `data/sample/sales_demo.csv` and generated by a
seeded NumPy process. Regenerate it after changing the generator:

```powershell
$env:PYTHONPATH = "src"
python -m sales_dashboard.demo
```

If the package is installed in editable mode, the simpler command works:

```powershell
python -m sales_dashboard.demo
```

The dataset is deterministic: the same seed and date range always produce the
same rows.

## Tests and linting

```powershell
python -m pytest
python -m pytest --cov=sales_dashboard --cov-report=term-missing
python -m ruff check .
python -m ruff format --check .
```

The suite contains 192 tests. It covers the demo dataset, schema alias detection
and confidence, CSV loading and error handling, date ambiguity decisions,
validation checks, cleaning rules, profiling and INR formatting. Dashboard
coverage includes every KPI formula, distinct and fallback order counting,
zero-order AOV, period comparisons, max-date-anchored presets, individual and
combined filters, persistence and dataset-change reset, daily/weekly/monthly
trends, category and top-10 calculations, insight generation, and navigation
visibility. Products and Regions coverage includes product and regional
performance, revenue share, order counts and AOV, top-10 limits, Pareto
cumulative shares and the 80% threshold, zero and negative revenue, product
drill-down snapshots and trends, category-by-region aggregation, missing region
columns, empty filtered results and all page charts. Data Explorer and export
coverage includes literal case-insensitive text and date search, empty searches,
column validation, UTF-8 BOM CSV round-trips, safe timestamped filenames,
quality-report summary and issue rows, page downloads and global-filter
consistency. Chart tests verify unique date-axis labels and edge padding, and
version tests keep the package, config and `pyproject.toml` in sync. Smoke tests
use Streamlit's `AppTest` to boot `app.py`, load and clean the demo dataset, open
the Overview, Products, Regions and Data Explorer pages, interact with filters,
drill-downs, search, column selection, row limits and chart controls, and
confirm the Home and preparation flow still work, including the friendly error
boundary. The GitHub Actions workflow runs linting, formatting checks and tests
with a coverage report on Python 3.11 and 3.12.

## Deployment

The repository is ready for Streamlit Community Cloud and includes a
`Dockerfile` for self-hosting:

```powershell
docker build -t sales-dashboard .
docker run --rm -p 8501:8501 sales-dashboard
```

Streamlit Community Cloud needs the repository, the `main` branch and
`app.py` as the entry point; select Python 3.12 and let the platform install
`requirements.txt`. For the full checklist, resource limits, configuration and
troubleshooting, see [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).

## Data privacy

Uploaded CSVs are processed in memory for the current Streamlit session. The
application does not save uploaded files, log their contents, or send them to a
third-party service. Replacing or clearing the dataset removes it from the
session. As with any hosted application, the server running Streamlit receives
the uploaded bytes while the session is active.

## Roadmap

- **M1 (complete):** scaffold, demo dataset and Home page.
- **M2 (complete):** validation, cleaning, manual column mapping and data-quality report.
- **M3 (complete):** business metrics, global filters and Overview page.
- **M4 (complete):** Products and Regions analytics pages.
- **M5 (complete):** Data Explorer, CSV exports and quality-report downloads.
- **M6 (complete):** error boundary, loading spinners, accessibility and chart
  polish, screenshots, deployment guide, Dockerfile, coverage reporting and
  v1.0.0 release.

## License

Released under the MIT License. See [LICENSE](LICENSE).
