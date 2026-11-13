"""Shared page styling and small presentational components."""

import html

import streamlit as st

from sales_dashboard.config import APP_NAME, APP_TAGLINE, APP_VERSION, CURRENCY_CODE
from sales_dashboard.state import pop_flash

_CSS = """
<style>
:root {
    --sa-brand: #0F766E;
    --sa-brand-dark: #0B3B36;
    --sa-accent: #14B8A6;
    --sa-ink: #0F172A;
    --sa-muted: #475569;
    --sa-line: #E2E8F0;
    --sa-surface: #FFFFFF;
    --sa-bg: #F7FAF9;
}

.stApp {
    background: var(--sa-bg);
}

.block-container {
    max-width: 1180px;
    padding-top: 2.2rem;
    padding-bottom: 3.5rem;
}

h1, h2, h3 {
    color: var(--sa-ink);
    letter-spacing: -0.02em;
}

.sa-hero {
    position: relative;
    overflow: hidden;
    border-radius: 24px;
    padding: 2.6rem 2.8rem;
    background:
        radial-gradient(circle at 92% 8%, rgba(20, 184, 166, 0.30), transparent 34%),
        linear-gradient(135deg, #0B3B36 0%, #0F766E 62%, #115E59 100%);
    color: #F8FAFC;
    box-shadow: 0 22px 45px -28px rgba(15, 118, 110, 0.55);
    margin-bottom: 1.4rem;
}

.sa-hero::after {
    content: "";
    position: absolute;
    right: -70px;
    bottom: -90px;
    width: 260px;
    height: 260px;
    border-radius: 50%;
    border: 1px solid rgba(255, 255, 255, 0.16);
}

.sa-eyebrow {
    text-transform: uppercase;
    letter-spacing: 0.16em;
    font-size: 0.72rem;
    font-weight: 700;
    opacity: 0.8;
    margin-bottom: 0.75rem;
}

.sa-hero h1 {
    color: #FFFFFF;
    font-size: clamp(2.1rem, 4vw, 3.35rem);
    line-height: 1.05;
    margin: 0 0 0.9rem;
    max-width: 820px;
}

.sa-hero p {
    color: rgba(248, 250, 252, 0.86);
    font-size: 1.03rem;
    line-height: 1.65;
    max-width: 720px;
    margin: 0;
}

.sa-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-top: 1.4rem;
}

.sa-chip {
    border: 1px solid rgba(255, 255, 255, 0.18);
    background: rgba(255, 255, 255, 0.08);
    color: #F8FAFC;
    padding: 0.35rem 0.7rem;
    border-radius: 999px;
    font-size: 0.78rem;
}

.sa-section {
    margin: 2.1rem 0 0.9rem;
}

.sa-section h2 {
    font-size: 1.3rem;
    margin: 0 0 0.25rem;
}

.sa-section p {
    color: var(--sa-muted);
    margin: 0;
    font-size: 0.93rem;
}

.sa-card-heading {
    color: var(--sa-ink);
    font-size: 1.12rem;
    font-weight: 700;
    letter-spacing: -0.01em;
    margin: 0 0 0.35rem;
}

.sa-metric {
    background: var(--sa-surface);
    border: 1px solid var(--sa-line);
    border-radius: 16px;
    padding: 0.95rem 1rem;
    min-height: 108px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.sa-metric-label {
    color: var(--sa-muted);
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}

.sa-metric-value {
    color: var(--sa-ink);
    font-size: 1.45rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    margin-top: 0.35rem;
    line-height: 1.15;
}

.sa-metric-value--sm {
    font-size: 1.02rem;
    line-height: 1.35;
}

.sa-metric-note {
    color: var(--sa-muted);
    font-size: 0.75rem;
    margin-top: 0.3rem;
}

.sa-metric-delta {
    font-size: 0.74rem;
    font-weight: 700;
    margin-top: 0.4rem;
}

.sa-delta-up {
    color: #047857;
}

.sa-delta-down {
    color: #B91C1C;
}

.sa-delta-flat {
    color: var(--sa-muted);
}

.sa-insight {
    background: var(--sa-surface);
    border: 1px solid var(--sa-line);
    border-radius: 16px;
    padding: 1rem 1.1rem;
    height: 100%;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}

.sa-insight-icon {
    font-size: 1.15rem;
    line-height: 1;
    margin-bottom: 0.45rem;
}

.sa-insight-title {
    color: var(--sa-ink);
    font-size: 0.95rem;
    font-weight: 700;
    margin-bottom: 0.3rem;
}

.sa-insight-body {
    color: var(--sa-muted);
    font-size: 0.83rem;
    line-height: 1.5;
}

.sa-privacy {
    display: flex;
    gap: 0.9rem;
    align-items: flex-start;
    background: #ECFDF5;
    border: 1px solid #A7F3D0;
    border-radius: 16px;
    padding: 1rem 1.2rem;
    margin-top: 1.5rem;
}

.sa-privacy-icon {
    font-size: 1.2rem;
    line-height: 1;
    margin-top: 0.1rem;
}

.sa-privacy strong {
    color: #064E3B;
}

.sa-privacy p {
    color: #065F46;
    margin: 0.15rem 0 0;
    font-size: 0.88rem;
    line-height: 1.55;
}

.sa-footer {
    margin-top: 2.5rem;
    padding-top: 1.1rem;
    border-top: 1px solid var(--sa-line);
    color: #64748B;
    font-size: 0.78rem;
    display: flex;
    justify-content: space-between;
    gap: 1rem;
    flex-wrap: wrap;
}

.sa-sidebar-brand {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 1.02rem;
    font-weight: 700;
    color: var(--sa-ink);
    padding: 0.25rem 0 0.4rem;
}

.sa-sidebar-brand span:first-child {
    font-size: 1.2rem;
}

.stButton > button,
.stDownloadButton > button {
    border-radius: 10px;
    font-weight: 600;
}

[data-testid="stFileUploaderDropzone"] {
    border-radius: 14px;
    border: 1px dashed #94A3B8;
    background: #F8FAFC;
}
</style>
"""


def inject_styles() -> None:
    """Add the application's visual polish once per page run."""
    st.markdown(_CSS, unsafe_allow_html=True)


def render_hero() -> None:
    """Render the landing hero."""
    chips = (
        "CSV upload",
        "One-click demo",
        "INR-ready",
        "In-memory processing",
    )
    chip_html = "".join(f'<span class="sa-chip">{html.escape(chip)}</span>' for chip in chips)
    st.markdown(
        f"""
        <div class="sa-hero">
            <div class="sa-eyebrow">Portfolio project · Data analytics</div>
            <h1>{html.escape(APP_NAME)}</h1>
            <p>
                {html.escape(APP_TAGLINE)}
                Upload a sales CSV, check the dataset, and prepare it for
                interactive sales analysis.
            </p>
            <div class="sa-chips">{chip_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section(title: str, subtitle: str | None = None) -> None:
    """Render a section heading with an optional supporting sentence."""
    subtitle_html = f"<p>{html.escape(subtitle)}</p>" if subtitle else ""
    st.markdown(
        f'<div class="sa-section"><h2>{html.escape(title)}</h2>{subtitle_html}</div>',
        unsafe_allow_html=True,
    )


def render_metric_card(
    label: str,
    value: str,
    note: str | None = None,
    *,
    small: bool = False,
) -> None:
    """Render a compact KPI-style card."""
    value_class = "sa-metric-value sa-metric-value--sm" if small else "sa-metric-value"
    note_html = f'<div class="sa-metric-note">{html.escape(note)}</div>' if note else ""
    st.markdown(
        f"""
        <div class="sa-metric">
            <div class="sa-metric-label">{html.escape(label)}</div>
            <div class="{value_class}">{html.escape(value)}</div>
            {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_flash() -> None:
    """Show and clear the one-shot message stored in session state."""
    flash = pop_flash()
    if not flash:
        return

    message = flash.get("message", "")
    kind = flash.get("kind", "success")
    if kind == "error":
        st.error(message, icon="⚠️")
    elif kind == "warning":
        st.warning(message, icon="⚠️")
    else:
        st.toast(message, icon="✅")


def render_privacy_note() -> None:
    """Explain how uploaded files are handled."""
    st.markdown(
        """
        <div class="sa-privacy">
            <div class="sa-privacy-icon">🔒</div>
            <div>
                <strong>Your data stays in this session.</strong>
                <p>
                    Uploaded CSVs are processed in memory for this session and
                    are not saved by the application, logged, or sent to a
                    third-party service. Replacing or clearing the dataset
                    removes it from the current session.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_footer() -> None:
    """Render a small footer."""
    st.markdown(
        f"""
        <div class="sa-footer">
            <span>Built with Python · Pandas · Streamlit · Plotly</span>
            <span>v{html.escape(APP_VERSION)} · {html.escape(CURRENCY_CODE)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
