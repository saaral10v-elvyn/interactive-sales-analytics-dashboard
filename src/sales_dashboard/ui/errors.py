"""Friendly last-resort screen for unexpected page failures."""

from __future__ import annotations

import logging
import traceback

import streamlit as st

logger = logging.getLogger(__name__)


def error_summary(exc: BaseException) -> str:
    """Return a short, single-line description of an unexpected error."""
    name = type(exc).__name__
    message = str(exc).strip().splitlines()[0] if str(exc).strip() else ""
    return f"{name}: {message}" if message else name


def render_error_screen(exc: BaseException) -> None:
    """Explain a failure without showing a raw traceback to the user.

    The full traceback stays available behind a disclosure so a bug report can
    include it, while the default message reassures the user that the loaded
    dataset is untouched.
    """
    logger.error("Unhandled page error: %s", error_summary(exc), exc_info=exc)
    st.error(
        "**Something went wrong while drawing this page.**\n\n"
        "Your dataset is still loaded and nothing was saved or uploaded. "
        "Try the button below. If the problem continues, reload the browser tab.",
        icon="⚠️",
    )
    if st.button("Try again", type="primary"):
        st.rerun()
    with st.expander("Technical details (for a bug report)"):
        st.code(
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
            language="text",
        )
