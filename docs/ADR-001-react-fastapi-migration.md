# ADR-001: Migrate the dashboard to React and FastAPI behind a frozen analytics contract

- **Status:** Accepted, implemented
- **Date:** 2026-11-21
- **Deciders:** project owner
- **Supersedes:** none

## Context

Version 1.0.0 of this project started as a Streamlit application. Its analytics
already lived in pure modules under `src/sales_dashboard`, but everything that
presented them was Streamlit-specific: `app.py`, `state.py`, the five page
modules and eight of the nine `ui/` modules. Streamlit's rerun model also made
the app harder to shape into the responsive, portfolio-quality interface the
project was aiming for.

Three constraints shape the migration:

1. The analytics must not be rewritten in TypeScript. The Python rules are the
   product; the new UI is a client of them.
2. A DataFrame must never cross the wire. The API returns JSON-serialisable
   records, summaries and file bytes only.
3. Behaviour must not change. Loading, schema detection, manual mapping,
   validation, cleaning, KPI and chart rules, filter defaults and CSV exports
   are all part of the contract.

## Decision

Split the app into a React + TypeScript frontend, a FastAPI backend and the
existing domain package:

```text
frontend/            React + TypeScript SPA
        │  JSON over HTTP, no DataFrames
        ▼
src/sales_api/       FastAPI routers: upload, mapping, cleaning, pages, exports
        │  calls pure functions only
        ▼
src/sales_dashboard/ unchanged domain layer (analytics, filters, cleaning, …)
```

The migration runs in eight steps: freeze the contract (M7), add the API
skeleton and session store (M8–M9), port upload, mapping and cleaning (M10),
port the pages, exports and frontend (M11–M12), make the new stack the
production surface with single-origin serving and a container (M13), then
delete Streamlit and finish dependency and metadata cleanup (M14). All eight
steps are complete; the repository contains only the API, the React client and
the shared domain package.

## Reuse map

| Module | Decision | Reason |
| --- | --- | --- |
| `loading.py`, `parsing.py`, `profiling.py` | Reuse unchanged | Pure, returns dataclasses and a DataFrame |
| `schema.py`, `validation.py`, `cleaning.py`, `dates.py` | Reuse unchanged | The rules that must not drift |
| `filters.py`, `analytics.py`, `explorer.py`, `exports.py` | Reuse unchanged | Pure inputs and outputs; already tested |
| `models.py`, `formatting.py`, `config.py`, `demo.py` | Reuse unchanged | Shared types and presentation strings |
| `state.py` | Refactor | Currently a `st.session_state` wrapper; becomes the API session store |
| `ui/dashboard.py` | Refactor | Page orchestration becomes route handlers |
| `ui/charts.py`, `ui/tables.py` | Refactor | Plotly figures and row dicts become chart payloads and JSON rows |
| `ui/components.py`, `ui/filters.py`, `ui/layout.py`, `ui/sidebar.py`, `ui/errors.py`, `ui/preparation.py` | Replace | Widget and layout code has no meaning outside Streamlit |
| `app.py`, `pages/`, `.streamlit/` | Replace | The SPA and its router take over |

## Freeze strategy

The freeze is the safety net for every later step, so it was built first.

- `tests/parity_payloads.py` builds eight scenarios: the demo dataset, classic
  models with a manual override, missing order IDs, missing regions, ambiguous
  dates, returns only, a messy file and an incomplete mapping.
- Each payload records the loaded profile and detected mapping, date inspection,
  every validation and cleaning report, all page payloads for the default,
  narrowed and zero-row filter states, filter summaries and the exact CSV bytes
  of every export (length plus SHA-256).
- `tests/test_parity.py` compares each payload with a golden file in
  `tests/golden/` and reports the first differing JSON path. Regeneration is
  explicit: `pytest tests/test_parity.py --update-golden`.
- The builder imports only `sales_dashboard`. It never touches the web layer, a
  database or an HTTP client, so the fixtures stay valid after the presentation
  layer is replaced.
- Floats are rounded to six decimals before comparison. A change in summation
  order is not a behaviour change; a changed total still fails.
- The demo fixture keeps its full daily trend (about 373 KB of the roughly
  608 KB total) so a drift points at a specific date and series rather than at
  one aggregated number.

Freezing exposed two harness-level gaps, both fixed: `date` objects and NumPy
scalars needed normalising, and a whole-payload pass is now done once at the end
of `build_payload` instead of at each call site.

## Consequences

- The pre-migration suite had 193 tests; 160 were estimated to survive
  unchanged. The freeze adds 14 tests, bringing the suite to 207.
- The 24 `AppTest` smoke tests did not survive the move. They were removed in
  M14 together with the Streamlit layer; their coverage lives in the API,
  static-serving and frontend suites.
- The frontend owns presentation only. Any number that appears on screen must
  come from an API payload, which keeps the golden files authoritative.
- Streamlit and FastAPI coexisted until M14, when `app.py`, `state.py`,
  `pages/`, `ui/` and `.streamlit/` were deleted. The production surface has
  been the API + SPA since M13.
- In M14 `pyproject.toml`, `requirements.txt` and `requirements-dev.txt` were
  updated to describe the React + FastAPI app. Streamlit and Plotly are no
  longer dependencies, and the temporary `requirements-api.txt` was folded back
  into `requirements.txt`.

## Decisions

| Topic | Proposal | Alternative |
| --- | --- | --- |
| Charting | Recharts (accepted) | `react-plotly.js`: closer to current figures but a much heavier bundle |
| Session store | In-memory store with a TTL (accepted) | Redis, or signed client-side state |
| Serving | One origin: FastAPI serves the built SPA (accepted; implemented in M13) | Separate static host with CORS |
| Production container | Multi-stage Node + Python image on port 8000 (accepted) | Commit or copy a prebuilt `dist/` |
| Repository layout | Keep `src/sales_dashboard`, add `src/sales_api` and `frontend/` (accepted) | New top-level packages |
| Streamlit lifetime | Keep until parity is signed off, then delete (accepted; deleted in M14) | Delete earlier |
| Mobile | All four pages usable at 390 px (accepted) | Desktop-first with a lighter mobile layout |

## Verification

At the end of M7 the suite is green (207 tests), Ruff lint and format checks
pass, and the golden files are reproducible from a clean checkout. Any later
milestone is accepted only if those fixtures still match.

At the end of M12 the Python suite is green (307 tests, 91% branch coverage),
Ruff lint and format checks pass, the golden files are unchanged, and the
frontend passes oxlint, 26 Vitest tests and a strict TypeScript production
build. The full demo flow was exercised in a browser against the live API:
load demo, inspect and clean, filter, open all four analytics pages, search the
explorer, reload to restore the session, and reset the dataset.

At the end of M13 the Python suite is green (335 tests), Ruff lint and format
checks pass, and the golden files are unchanged. The frontend still passes
oxlint, 26 Vitest tests and the strict production build. A multi-stage container
serves the API and the built SPA on port 8000; CI builds that image and
smoke-tests `/`, `/overview`, `/api/health`, a missing asset, gzip and the
immutable asset cache header. Deep links, session restore, all four pages,
filters, explorer search and downloads were exercised in a browser against the
single-origin production build.

At the end of M14 the Python suite is green (302 tests), Ruff lint and format
checks pass, and the golden files are unchanged. Streamlit, Plotly, the
`AppTest` smoke tests and the chart-builder tests are gone; the runtime
dependencies are a single lean `requirements.txt`. The production container
still builds and serves the SPA, and the README screenshots were regenerated
from the React app.
