"""Canonical payloads that freeze the v1.0.0 analytics behaviour.

The JSON files in ``tests/golden`` are generated from this module and asserted
by ``tests/test_parity.py``. They exist so the migration can prove that every
number, string and CSV byte produced by the domain layer is unchanged.

Regenerate after an intentional behaviour change::

    pytest tests/test_parity.py --update-golden

Only the pure domain package is imported here: no web framework, chart library
or HTTP client. That keeps the contract meaningful as the presentation layer
changes, and it means these fixtures describe the rules rather than the UI.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Any

import pandas as pd

from sales_dashboard.cleaning import (
    CleaningError,
    CleaningOptions,
    clean_dataset,
    inspect_date_column,
)
from sales_dashboard.dates import DateDecisionRequired
from sales_dashboard.explorer import search_dataframe
from sales_dashboard.exports import (
    dataframe_to_csv_bytes,
    export_filename,
    quality_report_csv_bytes,
)
from sales_dashboard.filters import (
    PRESET_KEYS,
    apply_filters,
    dataset_date_bounds,
    default_filter_state,
    filter_options,
    preset_range,
    resolve_filter_state,
    summarize_filters,
)
from sales_dashboard.loading import load_demo_dataset, read_csv_bytes
from sales_dashboard.models import CleanedDataset, FilterState, LoadedDataset
from sales_dashboard.page_payloads import (
    explorer_payload,
    overview_payload,
    products_payload,
    regions_payload,
)
from sales_dashboard.payloads import (
    cleaning_summary as summarize_cleaned,
)
from sales_dashboard.payloads import (
    dataset_summary as summarize_loaded,
)
from sales_dashboard.payloads import (
    filter_state_dict as _state_dict,
)
from sales_dashboard.payloads import (
    jsonable,
)
from sales_dashboard.payloads import (
    mapping_summary as summarize_mapping,
)
from sales_dashboard.schema import FIELD_ORDER, resolve_mapping

# A fixed timestamp keeps export filenames stable between runs.
FIXED_TIMESTAMP = datetime(2026, 1, 1, 12, 0, 0)

CLASSIC_MODELS_CSV = """\
ORDERNUMBER,ORDERLINENUMBER,PRODUCTCODE,PRODUCTNAME,PRODUCTLINE,QUANTITYORDERED,PRICEEACH,SALES,ORDERDATE,STATUS,TERRITORY,MSRP
10101,1,S10_1678,1969 Harley Davidson Ultimate Chopper,Motorcycles,30,95.70,2871.00,2003-01-06,Shipped,NA,95
10101,2,S10_1949,1952 Alpine Renault 1300,Classic Cars,50,214.30,10715.00,2003-01-06,Shipped,NA,214
10102,1,S10_4757,1972 Alfa Romeo GTA,Classic Cars,22,136.00,2992.00,2003-01-10,Shipped,EMEA,136
10103,1,S700_4002,1972 Trek 1000,Motorcycles,10,60.00,600.00,2003-01-29,Resolved,APAC,60
10104,1,S24_2011,1998 Chrysler Plymouth Prowler,Classic Cars,5,150.00,750.00,2003-02-14,Cancelled,NA,150
"""

NO_ORDER_ID_CSV = """\
order_date,product,category,region,quantity,unit_price,status
2026-01-05,Alpha Widget,Widgets,North,2,100,Completed
2026-01-05,Beta Widget,Widgets,North,1,50,Completed
2026-01-09,Gamma Gadget,Gadgets,South,4,25,Completed
2026-02-02,Alpha Widget,Widgets,South,3,100,Completed
"""

NO_REGION_CSV = """\
order_id,order_date,product,quantity,unit_price,line_total
N-1,2026-01-03,Alpha Widget,2,100,200
N-2,2026-01-07,Beta Widget,1,50,50
N-3,2026-02-11,Gamma Gadget,5,20,100
"""

AMBIGUOUS_DATES_CSV = """\
order_id,order_date,product,quantity,unit_price
A-1,03/04/2026,Alpha Widget,1,100
A-2,05/06/2026,Beta Widget,2,50
A-3,07/08/2026,Alpha Widget,1,75
A-4,11/12/2026,Beta Widget,3,20
"""

RETURNS_ONLY_CSV = """\
order_id,order_date,product,category,region,quantity,unit_price,status
R-1,2026-02-01,Alpha Widget,Widgets,North,-2,100,Returned
R-2,2026-02-02,Beta Widget,Widgets,South,-1,50,Returned
"""

MESSY_CSV = """\
order_id,order_date,product,category,region,quantity,unit_price,discount_percent,line_total,status
M-1,2026-03-01,Alpha Widget,Widgets,North,2,100,0,200,Completed
M-1,2026-03-01,Alpha Widget,Widgets,North,2,100,0,200,Completed
M-2,2026-03-02,Beta Widget,widgets,north,1,50,10,45,completed
M-3,2026-03-03,Gamma Gadget,Widgets,South,abc,50,0,0,Completed
M-4,not-a-date,Delta Device,Widgets,South,1,10,0,10,Completed
M-5,2026-03-05,,Widgets,South,1,10,0,10,Completed
M-6,2026-03-06,Epsilon Widget,Widgets,North,1,10,0,10,Cancelled
M-7,2026-03-07,Zeta Widget,Widgets,North,1,10,0,15,Completed
M-8,2026-03-08,Eta Widget,Widgets,West,1,10,0,,Completed
M-9,2026-03-09,Theta Widget,Widgets,West,0,10,0,0,Completed
M-10,2026-03-10,Iota Widget,Widgets,West,1,-10,0,-10,Completed
"""

UNMAPPED_REQUIRED_CSV = """\
order_id,order_date,product,unit_price
U-1,2026-01-01,Alpha Widget,100
"""

# Manual overrides that exercise the "user wins, but a column stays unique" rule.
MANUAL_OVERRIDES: dict[str, dict[str, str]] = {
    "classic_models": {"product": "PRODUCTCODE"},
}


def _load(csv_text: str, filename: str) -> LoadedDataset:
    return read_csv_bytes(csv_text.lstrip().encode("utf-8"), filename, source="upload")


CASE_LOADERS: dict[str, Any] = {
    "demo": load_demo_dataset,
    "classic_models": lambda: _load(CLASSIC_MODELS_CSV, "classic_models.csv"),
    "no_order_id": lambda: _load(NO_ORDER_ID_CSV, "no_order_id.csv"),
    "no_region": lambda: _load(NO_REGION_CSV, "no_region.csv"),
    "ambiguous_dates": lambda: _load(AMBIGUOUS_DATES_CSV, "ambiguous_dates.csv"),
    "returns_only": lambda: _load(RETURNS_ONLY_CSV, "returns_only.csv"),
    "messy": lambda: _load(MESSY_CSV, "messy.csv"),
    "unmapped_required": lambda: _load(UNMAPPED_REQUIRED_CSV, "unmapped_required.csv"),
}

CASE_NAMES: tuple[str, ...] = tuple(sorted(CASE_LOADERS))


def _attempt_cleaning(
    loaded: LoadedDataset,
    date_format: str,
) -> dict[str, Any]:
    options = CleaningOptions(date_format=date_format, exclude_statuses=True)  # type: ignore[arg-type]
    try:
        cleaned = clean_dataset(
            loaded.dataframe,
            loaded.mapping,
            options,
            source_filename=loaded.filename,
        )
    except (DateDecisionRequired, CleaningError) as exc:
        payload: dict[str, Any] = {
            "ok": False,
            "date_format": date_format,
            "error": {"type": type(exc).__name__, "message": str(exc)},
        }
        if isinstance(exc, DateDecisionRequired):
            payload["error"]["inspection"] = jsonable(exc.inspection)
        return payload

    return {
        "ok": True,
        "date_format": date_format,
        "cleaned": summarize_cleaned(cleaned),
    }


def _narrow_state(
    dataframe: pd.DataFrame,
    bounds: tuple[date, date],
    options: dict[str, tuple[str, ...]],
) -> FilterState | None:
    categories = options.get("category", ())
    regions = options.get("region", ())
    if not categories and not regions:
        return None
    state = FilterState(
        start_date=bounds[0],
        end_date=bounds[1],
        preset="custom",
        categories=(categories[0],) if categories else (),
        regions=(regions[0],) if regions else (),
    )
    return resolve_filter_state(dataframe, state)


_STATE_KEYS = {
    "category": "categories",
    "product": "products",
    "region": "regions",
}


def _combo_state(
    start: date,
    end: date,
    dimension: str,
    value: str,
    status: str,
) -> FilterState:
    """Build a custom-range state selecting one dimension value and one status."""
    return FilterState(
        start_date=start,
        end_date=end,
        preset="custom",
        statuses=(status,),
        **{_STATE_KEYS[dimension]: (value,)},
    )


def _empty_state(
    dataframe: pd.DataFrame,
    bounds: tuple[date, date],
    options: dict[str, tuple[str, ...]],
) -> FilterState | None:
    """Find the first dimension/status pair that matches no rows, if one exists.

    The demo dataset is fully crossed for category and status, so the search
    also covers products and regions. Whichever pair hits first is stable
    because ``filter_options`` returns sorted values.
    """
    start, end = bounds
    statuses = options.get("status", ())
    for dimension in ("category", "product", "region"):
        for value in options.get(dimension, ()):
            for status in statuses:
                state = _combo_state(start, end, dimension, value, status)
                if apply_filters(dataframe, state).empty:
                    return resolve_filter_state(dataframe, state)
    return None


def pages_payload(cleaned: CleanedDataset) -> dict[str, Any]:
    """Build every page payload for the default and (for the demo) edge states."""
    bounds = dataset_date_bounds(cleaned.dataframe)
    if bounds is None:
        return {"bounds": None}
    options = filter_options(cleaned.dataframe)
    default_state = default_filter_state(cleaned.dataframe)
    assert default_state is not None

    payload: dict[str, Any] = {
        "bounds": list(bounds),
        "options": {field: list(values) for field, values in options.items()},
        "presets": {
            preset: list(preset_range(preset, bounds[0], bounds[1]))
            for preset in PRESET_KEYS
            if preset != "custom"
        },
        "default_state": _state_dict(default_state),
        "default": {
            "overview": overview_payload(cleaned, default_state),
            "products": products_payload(cleaned, default_state),
            "regions": regions_payload(cleaned, default_state),
            "explorer": explorer_payload(cleaned, default_state),
        },
    }

    narrow = _narrow_state(cleaned.dataframe, bounds, options)
    if narrow is not None:
        payload["narrow_state"] = _state_dict(narrow)
        payload["narrow"] = {
            "overview": overview_payload(cleaned, narrow),
            "products": products_payload(cleaned, narrow),
        }

    empty = _empty_state(cleaned.dataframe, bounds, options)
    if empty is not None:
        payload["empty_state"] = _state_dict(empty)
        payload["empty"] = {
            "overview": overview_payload(cleaned, empty),
            "products": products_payload(cleaned, empty),
            "regions": regions_payload(cleaned, empty),
            "explorer": explorer_payload(cleaned, empty),
        }

    return payload


def exports_payload(cleaned: CleanedDataset, state: FilterState) -> dict[str, Any]:
    """Freeze exported filenames and the exact CSV bytes behind them."""
    filtered = apply_filters(cleaned.dataframe, state)
    searched = search_dataframe(filtered, "")

    def describe(data: bytes, label: str) -> dict[str, Any]:
        return {
            "filename": export_filename(
                cleaned.source_filename,
                label,
                timestamp=FIXED_TIMESTAMP,
            ),
            "size_bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }

    payload = {
        "cleaned": describe(
            dataframe_to_csv_bytes(cleaned.dataframe),
            "cleaned",
        ),
        "filtered": describe(
            dataframe_to_csv_bytes(searched),
            "filtered",
        ),
        "quality_report": describe(
            quality_report_csv_bytes(
                cleaned.report,
                source_filename=cleaned.source_filename,
                revenue_source=cleaned.revenue_source,
                date_format_used=cleaned.date_format_used,
            ),
            "quality_report",
        ),
    }

    if cleaned.source_filename == "sales_demo.csv":
        payload["sample"] = describe(
            dataframe_to_csv_bytes(cleaned.dataframe),
            "sample",
        )
    return payload


def mapping_contract(loaded: LoadedDataset) -> dict[str, Any]:
    """Freeze the manual-override rules: overrides win, columns stay unique."""
    columns = [str(column) for column in loaded.dataframe.columns]
    contract: dict[str, Any] = {
        "manual_override": None,
        "duplicate_source_error": None,
        "unknown_column_error": None,
    }

    override = MANUAL_OVERRIDES.get(loaded.filename.removesuffix(".csv"))
    if override:
        contract["manual_override"] = {
            "requested": override,
            "mapping": summarize_mapping(resolve_mapping(columns, override)),
        }

    mapped = [
        (field, loaded.mapping.source_for(field))
        for field in FIELD_ORDER
        if loaded.mapping.source_for(field) is not None
    ]
    if len(mapped) >= 2:
        first_field, _ = mapped[0]
        _, second_source = mapped[1]
        try:
            resolve_mapping(columns, {first_field: second_source})
        except Exception as exc:  # noqa: BLE001 - the message is the contract
            contract["duplicate_source_error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }

    first_field = mapped[0][0] if mapped else FIELD_ORDER[0]
    try:
        resolve_mapping(columns, {first_field: "__not_a_column__"})
    except Exception as exc:  # noqa: BLE001 - the message is the contract
        contract["unknown_column_error"] = {
            "type": type(exc).__name__,
            "message": str(exc),
        }

    return contract


def build_payload(case: str) -> dict[str, Any]:
    """Build the complete parity payload for one registered case."""
    if case not in CASE_LOADERS:
        raise KeyError(f"Unknown parity case: {case!r}")

    loaded = CASE_LOADERS[case]()
    auto = _attempt_cleaning(loaded, "auto")
    dmy = None if auto["ok"] else _attempt_cleaning(loaded, "DMY")

    payload: dict[str, Any] = {
        "case": case,
        "dataset": summarize_loaded(loaded),
        "date_inspection": jsonable(inspect_date_column(loaded.dataframe, loaded.mapping)),
        "mapping_contract": mapping_contract(loaded),
        "cleaning": {"auto": auto, "dmy": dmy},
        "filters": None,
        "pages": None,
        "exports": None,
    }

    outcome = auto if auto["ok"] else dmy
    if outcome and outcome["ok"]:
        cleaned = clean_dataset(
            loaded.dataframe,
            loaded.mapping,
            CleaningOptions(
                date_format=outcome["date_format"],  # type: ignore[arg-type]
                exclude_statuses=True,
            ),
            source_filename=loaded.filename,
        )
        payload["pages"] = pages_payload(cleaned)
        if payload["pages"] and payload["pages"].get("bounds"):
            state = default_filter_state(cleaned.dataframe)
            assert state is not None
            payload["filters"] = {
                "default_state": _state_dict(state),
                "summary": summarize_filters(state),
                "filtered_rows": len(apply_filters(cleaned.dataframe, state)),
            }
            payload["exports"] = exports_payload(cleaned, state)

    # Normalise the whole tree once: this rounds floats, converts dates and
    # proves that every value is JSON-serialisable before it reaches a fixture.
    return jsonable(payload)


def build_all() -> dict[str, Any]:
    """Build every registered case, keyed by name."""
    return {case: build_payload(case) for case in CASE_NAMES}
