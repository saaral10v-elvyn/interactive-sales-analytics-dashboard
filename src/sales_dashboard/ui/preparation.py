"""Home-page preparation UI: mapping review, cleaning and quality report."""

from __future__ import annotations

import logging
from datetime import datetime

import pandas as pd
import streamlit as st

from sales_dashboard.cleaning import (
    CleaningError,
    CleaningOptions,
    clean_dataset,
    inspect_date_column,
)
from sales_dashboard.dates import DateDecisionRequired, decision_label
from sales_dashboard.exports import (
    CSV_MIME,
    dataframe_to_csv_bytes,
    export_filename,
    quality_report_csv_bytes,
)
from sales_dashboard.formatting import format_inr, format_number
from sales_dashboard.models import CleanedDataset, LoadedDataset, ValidationIssue
from sales_dashboard.schema import (
    FIELD_GUIDE,
    FIELD_LABELS,
    FIELD_ORDER,
    PRICE_FIELDS,
    REQUIRED_FIELDS,
    MappingError,
    mapping_table_rows,
    resolve_mapping,
)
from sales_dashboard.state import (
    get_cleaned,
    set_cleaned,
    set_flash,
    update_dataset_mapping,
)
from sales_dashboard.ui.layout import render_metric_card, render_section

logger = logging.getLogger(__name__)

_NOT_MAPPED = "— Not mapped —"
_SEVERITY_LABELS = {"error": "Error", "warning": "Warning", "info": "Info"}
_FIELD_HELP = {guide.column: guide.description for guide in FIELD_GUIDE}


def _widget_suffix(dataset: LoadedDataset) -> str:
    return f"{dataset.filename}_{dataset.size_bytes}"


def render_schema_review(dataset: LoadedDataset) -> None:
    """Show detected columns with confidence and allow manual overrides."""
    mapping = dataset.mapping
    render_section(
        "Schema detection",
        "Review which file column supplies each field. Low-confidence matches "
        "can be overridden before cleaning.",
    )

    status_columns = st.columns(3)
    with status_columns[0]:
        render_metric_card(
            "Required fields",
            f"{len(REQUIRED_FIELDS) - len([f for f in REQUIRED_FIELDS if f not in mapping.fields])}"
            f" / {len(REQUIRED_FIELDS)}",
            "order_date, product, quantity",
        )
    with status_columns[1]:
        price_found = any(field in mapping.fields for field in PRICE_FIELDS)
        render_metric_card(
            "Price field",
            "Found" if price_found else "Missing",
            "unit_price or line_total",
        )
    with status_columns[2]:
        render_metric_card(
            "Review",
            "Needed" if mapping.requires_review else "Not needed",
            "Low-confidence or missing fields",
        )

    st.dataframe(
        pd.DataFrame(mapping_table_rows(mapping)),
        hide_index=True,
        width="stretch",
    )

    if not mapping.is_complete:
        st.error(
            "Required fields are missing: **" + ", ".join(mapping.missing_required) + "**. "
            "Map them manually below, or add the columns to your CSV."
        )
    if mapping.low_confidence_fields:
        labels = ", ".join(FIELD_LABELS[field] for field in mapping.low_confidence_fields)
        st.warning(
            f"Low-confidence detection for: **{labels}**. Check the mapping below before cleaning."
        )

    if mapping.source_for("order_id") is None:
        st.info(
            "**No order_id column detected.** Each row will count as one order. "
            "If one order can contain several products, add an order_id column so "
            "order counts stay accurate."
        )

    with st.expander("Review or override column mapping", expanded=not mapping.is_complete):
        _render_mapping_form(dataset)


def _render_mapping_form(dataset: LoadedDataset) -> None:
    mapping = dataset.mapping
    columns = list(dataset.dataframe.columns)
    options = [_NOT_MAPPED, *columns]
    suffix = _widget_suffix(dataset)

    with st.form(f"mapping_form_{suffix}"):
        st.caption(
            "Required fields are marked. Leave a field as **Not mapped** to exclude it. "
            "A source column can only be used once."
        )
        selections: dict[str, str | None] = {}
        left, right = st.columns(2)
        for index, field in enumerate(FIELD_ORDER):
            target = left if index % 2 == 0 else right
            current = mapping.source_for(field)
            default_index = options.index(current) if current in options else 0
            required = field in REQUIRED_FIELDS or field in PRICE_FIELDS
            label = FIELD_LABELS[field] + (" *" if required else "")
            with target:
                choice = st.selectbox(
                    label,
                    options,
                    index=default_index,
                    help=_FIELD_HELP.get(field),
                    key=f"mapping_{suffix}_{field}",
                )
            selections[field] = None if choice == _NOT_MAPPED else choice

        st.caption(
            "* Required: order_date, product, quantity, and at least one of "
            "unit_price or line_total."
        )
        overrides = dict(selections)
        submitted = st.form_submit_button("Apply mapping", type="primary")

    if not submitted:
        return

    try:
        reviewed = resolve_mapping(columns, overrides)
    except MappingError as exc:
        st.error(str(exc))
        return

    update_dataset_mapping(dataset, reviewed)
    if reviewed.is_complete:
        set_flash("Column mapping applied.")
    else:
        set_flash(
            "Mapping saved, but required fields are still missing: "
            + ", ".join(reviewed.missing_required)
            + ".",
            "warning",
        )
    st.rerun()


def render_cleaning_panel(dataset: LoadedDataset) -> None:
    """Offer date decisions and run validation/cleaning."""
    render_section(
        "Validate and clean",
        "Checks run on the file as read. Nothing is silently removed: every "
        "action appears in the report below.",
    )

    if not dataset.mapping.is_complete:
        st.warning("Complete the required column mapping before running validation and cleaning.")
        return

    inspection = inspect_date_column(dataset.dataframe, dataset.mapping)
    date_decision: str | None = None
    if inspection is not None and inspection.requires_decision:
        st.warning(
            f"**{format_number(inspection.ambiguous_count)} dates are ambiguous** — "
            "for example "
            + ", ".join(f"`{value}`" for value in inspection.ambiguous_examples)
            + ". Choose how they should be read before cleaning."
        )
        if inspection.suggested_format:
            st.caption(
                f"The unambiguous dates in this file look like "
                f"{decision_label(inspection.suggested_format)}. Please confirm."
            )
        date_decision = st.radio(
            "How should ambiguous dates be read?",
            options=["DMY", "MDY"],
            format_func=decision_label,
            index=None,
            key=f"date_decision_{_widget_suffix(dataset)}",
            help=("DMY reads 03/04/2026 as 3 April 2026. MDY reads 03/04/2026 as 4 March 2026."),
        )
        if date_decision is None:
            st.caption("The clean button unlocks once you choose a date format.")

    with st.expander("Cleaning rules used by this milestone"):
        st.markdown(
            "**Duplicates:** exact duplicate rows are removed. Legitimate line "
            "items that share an `order_id` but have different products are kept.\n\n"
            "**Statuses:** `Cancelled`, `Refunded` and `Void` records are excluded "
            "by default. `Returned` orders stay in the data as negative quantities.\n\n"
            "**Returns:** negative quantities reduce revenue and are never dropped "
            "silently.\n\n"
            "**Revenue:** a supplied `line_total` is used when available. Otherwise "
            "revenue is `quantity × unit_price × (1 − discount / 100)`.\n\n"
            "**Discounts:** `discount_percent` is a percentage (0–100). If every "
            "value is between 0 and 1, it is treated as a fraction (`0.10` = 10%).\n\n"
            "**Outliers:** unusual values are flagged and preserved, not removed."
        )

    blocked_by_decision = (
        inspection is not None and inspection.requires_decision and date_decision is None
    )
    if st.button(
        "Validate and clean data",
        type="primary",
        width="stretch",
        disabled=blocked_by_decision,
    ):
        _run_cleaning(dataset, date_decision)


def _run_cleaning(dataset: LoadedDataset, date_decision: str | None) -> None:
    options = CleaningOptions(
        date_format=date_decision or "auto",  # type: ignore[arg-type]
        exclude_statuses=True,
    )
    try:
        with st.spinner("Validating rows and building the cleaned dataset…"):
            cleaned = clean_dataset(
                dataset.dataframe,
                dataset.mapping,
                options,
                source_filename=dataset.filename,
            )
    except DateDecisionRequired as exc:
        set_flash(str(exc), "warning")
        st.rerun()
    except CleaningError as exc:
        set_flash(str(exc), "error")
        st.rerun()
    except Exception:
        logger.exception("Unexpected error while cleaning a dataset")
        set_flash(
            "Something went wrong while cleaning this dataset. "
            "Check the column mapping and try again.",
            "error",
        )
        st.rerun()

    set_cleaned(cleaned)
    report = cleaned.report
    if report.blocked:
        set_flash(
            "Cleaning finished, but no usable rows remain. See the data-quality report.",
            "error",
        )
    elif report.should_warn_about_drops:
        set_flash(
            f"Cleaning finished with a warning: {format_number(report.rows_dropped)} "
            f"rows ({report.dropped_ratio:.0%}) were removed.",
            "warning",
        )
    else:
        set_flash(
            f"Cleaning complete — {format_number(report.rows_output)} usable rows.",
            "success",
        )
    st.rerun()


def _issue_rows(issues: tuple[ValidationIssue, ...]) -> list[dict[str, str]]:
    return [
        {
            "Severity": _SEVERITY_LABELS.get(issue.severity, issue.severity.title()),
            "Code": issue.code,
            "Description": issue.description,
            "Affected rows": format_number(issue.affected_rows),
            "Action taken": issue.action_taken,
            "Examples": issue.example_text,
        }
        for issue in issues
    ]


def _cleaned_revenue(cleaned: CleanedDataset) -> float:
    if "revenue" not in cleaned.dataframe.columns or cleaned.dataframe.empty:
        return 0.0
    revenue = pd.to_numeric(cleaned.dataframe["revenue"], errors="coerce")
    return float(revenue.sum())


def _cleaned_orders(cleaned: CleanedDataset) -> int:
    dataframe = cleaned.dataframe
    if cleaned.order_id_available and "order_id" in dataframe.columns:
        return int(dataframe["order_id"].dropna().nunique())
    return int(len(dataframe))


def render_cleaned_summary(cleaned: CleanedDataset) -> None:
    """Render the quality report and cleaned-data preview."""
    report = cleaned.report
    render_section(
        "Data-quality report",
        "Every check lists its severity, affected rows, action and example values.",
    )

    if report.blocked:
        st.error(
            report.block_reason or "No usable rows remain after validation. Analysis is blocked."
        )
    elif report.should_warn_about_drops:
        st.error(
            f"**More than 20% of rows were removed.** "
            f"{format_number(report.rows_dropped)} of {format_number(report.rows_input)} "
            f"rows ({report.dropped_ratio:.0%}) did not survive validation. "
            "Review the report before using these results."
        )

    summary = st.columns(4)
    with summary[0]:
        render_metric_card(
            "Usable rows",
            format_number(report.rows_output),
            f"from {format_number(report.rows_input)} input rows",
        )
    with summary[1]:
        render_metric_card(
            "Rows removed",
            format_number(report.rows_dropped),
            f"{report.dropped_ratio:.0%} of input",
        )
    with summary[2]:
        render_metric_card(
            "Net revenue",
            format_inr(_cleaned_revenue(cleaned), compact=True),
            cleaned.revenue_source,
        )
    with summary[3]:
        orders = _cleaned_orders(cleaned)
        render_metric_card(
            "Orders",
            format_number(orders),
            "Distinct order_id" if cleaned.order_id_available else "Each row = one order",
        )

    counts = st.columns(3)
    with counts[0]:
        render_metric_card("Errors", format_number(report.issue_count("error")), "Blocking issues")
    with counts[1]:
        render_metric_card(
            "Warnings",
            format_number(report.issue_count("warning")),
            "Review recommended",
        )
    with counts[2]:
        render_metric_card("Info", format_number(report.issue_count("info")), "Actions and notes")

    if report.issues:
        st.dataframe(
            pd.DataFrame(_issue_rows(report.issues)),
            hide_index=True,
            width="stretch",
        )
    else:
        st.success("No data-quality issues were detected.")

    _render_cleaning_details(cleaned)

    if not report.blocked and not cleaned.dataframe.empty:
        with st.expander("Preview cleaned data (first 25 rows)"):
            st.caption(
                "Canonical columns with parsed dates, numeric values and calculated revenue."
            )
            st.dataframe(cleaned.dataframe.head(25), hide_index=True, width="stretch")
        st.caption(
            f"Cleaned {format_number(report.rows_output)} rows · "
            f"{cleaned.revenue_source} · date format: {decision_label(cleaned.date_format_used)}"
        )

    if not report.blocked and not cleaned.dataframe.empty:
        _render_cleaned_downloads(cleaned)


def _render_cleaned_downloads(cleaned: CleanedDataset) -> None:
    """Offer cleaned-data and quality-report downloads after cleaning."""
    render_section(
        "Downloads",
        "Save the cleaned dataset or the full data-quality report for your records.",
    )
    stamp = datetime.now()
    columns = st.columns(2)
    with columns[0]:
        st.download_button(
            "Download cleaned data (CSV)",
            data=dataframe_to_csv_bytes(cleaned.dataframe),
            file_name=export_filename(
                cleaned.source_filename,
                "cleaned",
                timestamp=stamp,
            ),
            mime=CSV_MIME,
            width="stretch",
            key="home_download_cleaned_data",
        )
        st.caption(f"{format_number(len(cleaned.dataframe))} cleaned rows")
    with columns[1]:
        st.download_button(
            "Download quality report (CSV)",
            data=quality_report_csv_bytes(
                cleaned.report,
                source_filename=cleaned.source_filename,
                revenue_source=cleaned.revenue_source,
                date_format_used=cleaned.date_format_used,
            ),
            file_name=export_filename(
                cleaned.source_filename,
                "quality_report",
                timestamp=stamp,
            ),
            mime=CSV_MIME,
            width="stretch",
            key="home_download_quality_report",
        )
        st.caption(f"{format_number(len(cleaned.report.issues))} reported issues")


def _render_cleaning_details(cleaned: CleanedDataset) -> None:
    dataframe = cleaned.dataframe
    returns = 0
    if "quantity" in dataframe.columns and not dataframe.empty:
        returns = int((pd.to_numeric(dataframe["quantity"], errors="coerce") < 0).sum())

    with st.expander("Cleaning details and interpretation"):
        details = pd.DataFrame(
            [
                ("Input rows", format_number(cleaned.report.rows_input)),
                ("Usable rows", format_number(cleaned.report.rows_output)),
                ("Rows removed", format_number(cleaned.report.rows_dropped)),
                ("Revenue source", cleaned.revenue_source),
                ("Date format", decision_label(cleaned.date_format_used)),
                ("Returns kept", format_number(returns)),
                (
                    "Order counting",
                    "Distinct order_id"
                    if cleaned.order_id_available
                    else "Each row counted as one order (no order_id)",
                ),
            ],
            columns=["Property", "Value"],
        )
        st.dataframe(details, hide_index=True, width="stretch")
        st.caption(
            "Discounts are treated as percentages of the line subtotal. When a "
            "line_total is supplied it is treated as already net of discount; "
            "otherwise revenue = quantity × unit_price × (1 − discount / 100). "
            "Outliers are flagged but preserved."
        )


def render_preparation(dataset: LoadedDataset) -> None:
    """Render schema review, cleaning controls and the result if present."""
    render_schema_review(dataset)
    render_cleaning_panel(dataset)
    cleaned = get_cleaned()
    if cleaned is not None:
        render_cleaned_summary(cleaned)
