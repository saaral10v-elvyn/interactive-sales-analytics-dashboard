"""Golden-file parity tests for the domain layer.

These tests freeze the numbers, strings and CSV bytes that the v1.0.0 app
produced. The FastAPI migration must return exactly the same values, so any
accidental behaviour change fails here before the UI is involved.

Regenerate the fixtures after an intentional change::

    pytest tests/test_parity.py --update-golden
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from parity_payloads import CASE_NAMES, build_payload

GOLDEN_DIR = Path(__file__).resolve().parent / "golden"
UPDATE_FLAG = "--update-golden"


def _dump(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def _first_difference(expected: Any, actual: Any, path: str = "$") -> str | None:
    """Return a readable description of the first structural difference."""
    if type(expected) is not type(actual):
        return f"{path}: expected {type(expected).__name__}, found {type(actual).__name__}"

    if isinstance(expected, dict):
        missing = sorted(set(expected) - set(actual))
        if missing:
            return f"{path}: missing keys {missing}"
        extra = sorted(set(actual) - set(expected))
        if extra:
            return f"{path}: unexpected keys {extra}"
        for key in expected:
            difference = _first_difference(expected[key], actual[key], f"{path}.{key}")
            if difference:
                return difference
        return None

    if isinstance(expected, list):
        if len(expected) != len(actual):
            return f"{path}: expected {len(expected)} items, found {len(actual)}"
        for index, (expected_item, actual_item) in enumerate(zip(expected, actual, strict=True)):
            difference = _first_difference(expected_item, actual_item, f"{path}[{index}]")
            if difference:
                return difference
        return None

    if expected != actual:
        return f"{path}: expected {expected!r}, found {actual!r}"
    return None


@pytest.mark.parametrize("case", CASE_NAMES)
def test_domain_payload_matches_golden_file(case: str, request: pytest.FixtureRequest) -> None:
    """The pipeline must still produce the exact frozen payload."""
    payload = build_payload(case)
    golden_path = GOLDEN_DIR / f"{case}.json"

    if request.config.getoption(UPDATE_FLAG):
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(_dump(payload), encoding="utf-8", newline="\n")
        return

    assert golden_path.exists(), (
        f"Missing golden file {golden_path.name}. Run: pytest tests/test_parity.py {UPDATE_FLAG}"
    )

    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    difference = _first_difference(expected, payload)
    if difference is not None:
        rendered = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False)
        pytest.fail(
            f"{case}: behaviour drifted from the frozen contract.\n"
            f"{difference}\n\n"
            f"Regenerate only if the change is intentional:\n"
            f"    pytest tests/test_parity.py {UPDATE_FLAG}\n\n"
            f"Actual payload:\n{rendered}",
            pytrace=False,
        )


def test_every_registered_case_has_a_golden_file() -> None:
    """A new case must ship with its fixture, not silently skip the freeze."""
    present = {path.stem for path in GOLDEN_DIR.glob("*.json")}
    assert present == set(CASE_NAMES), (
        "Golden files and parity cases are out of sync. "
        f"Missing: {sorted(set(CASE_NAMES) - present)}. "
        f"Unexpected: {sorted(present - set(CASE_NAMES))}."
    )


def test_freeze_covers_the_required_edge_cases() -> None:
    """The registry must keep covering the situations that broke the old app."""
    required = {
        "demo",
        "classic_models",
        "no_order_id",
        "no_region",
        "ambiguous_dates",
        "returns_only",
        "messy",
        "unmapped_required",
    }
    assert required <= set(CASE_NAMES)


def test_standard_cases_clean_successfully() -> None:
    """Cases expected to clean must still clean, so parity is not vacuous."""
    for case in ("demo", "classic_models", "no_order_id", "no_region", "returns_only", "messy"):
        payload = build_payload(case)
        assert payload["cleaning"]["auto"]["ok"] is True, case
        assert payload["pages"] is not None, case
        assert payload["exports"] is not None, case


def test_ambiguous_dates_require_a_decision() -> None:
    """Ambiguity must stay a hard stop, never a guess."""
    payload = build_payload("ambiguous_dates")

    auto = payload["cleaning"]["auto"]
    assert auto["ok"] is False
    assert auto["error"]["type"] == "DateDecisionRequired"
    assert auto["error"]["inspection"]["ambiguous_count"] == 4

    dmy = payload["cleaning"]["dmy"]
    assert dmy["ok"] is True
    assert dmy["cleaned"]["date_format_used"] == "DMY"


def test_demo_freeze_covers_default_narrow_and_empty_states() -> None:
    """The primary fixture must keep the zero-row branch as well as the happy path."""
    pages = build_payload("demo")["pages"]

    assert {"default", "narrow", "empty"} <= set(pages)
    assert pages["empty"]["overview"]["kpis"]["current"]["rows"] == 0
    assert pages["empty"]["products"]["notes"]["pareto_unavailable"] == "empty_selection"
    assert pages["empty"]["overview"]["trend"]["daily"] == []


def test_missing_required_fields_are_never_invented() -> None:
    """An incomplete mapping must fail closed rather than fabricate data."""
    payload = build_payload("unmapped_required")

    assert payload["dataset"]["mapping"]["is_complete"] is False
    assert "quantity" in payload["dataset"]["mapping"]["missing_required"]
    assert payload["cleaning"]["auto"]["ok"] is False
    assert payload["cleaning"]["auto"]["error"]["type"] == "CleaningError"
    assert payload["pages"] is None
