"""Tests for the last-resort error screen."""

from streamlit.testing.v1 import AppTest

from sales_dashboard.ui.errors import error_summary


def test_error_summary_uses_the_type_and_first_line() -> None:
    assert error_summary(ValueError("bad value\nsecond line")) == "ValueError: bad value"
    assert error_summary(ValueError()) == "ValueError"


def test_error_screen_hides_details_behind_an_expander() -> None:
    app = AppTest.from_string(
        "import streamlit as st\n"
        "from sales_dashboard.ui.errors import render_error_screen\n"
        "render_error_screen(RuntimeError('simulated failure'))\n",
        default_timeout=30,
    )
    app.run()

    assert not app.exception
    error_text = "\n".join(element.value for element in app.error)
    assert "Something went wrong while drawing this page" in error_text
    assert "dataset is still loaded" in error_text
    assert [expander.label for expander in app.expander] == ["Technical details (for a bug report)"]
    assert "RuntimeError: simulated failure" in app.get("code")[0].value
