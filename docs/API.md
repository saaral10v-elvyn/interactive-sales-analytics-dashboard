# API reference

The FastAPI backend in `src/sales_api` exposes the analytics domain over JSON.
It powers the React client.

## Running it

```powershell
$env:PYTHONPATH = "src"
python -m sales_api
```

The server listens on `127.0.0.1:8000`. Interactive docs are served at
`/api/docs` and the schema at `/api/openapi.json`. Tests use FastAPI's
`TestClient`; no running server is required.

To serve the built React client from the same origin, build `frontend/` and set
`SALES_API_STATIC_DIR=frontend/dist`. When that directory exists, `python -m
sales_api` detects it automatically.

## Sessions

Uploaded data never leaves the server as a DataFrame. A successful upload or
demo load creates a session that owns the loaded (and later cleaned) data, and
the response returns an opaque `session_id`. Every later request names that id.

- Sessions expire after 30 minutes of inactivity by default and are stored in
  memory, so restarting the API invalidates them.
- At most 100 sessions are kept. Creating a new one evicts the least recently
  used session once the cap is reached.
- A missing or expired id returns `404` with `code: "SESSION_NOT_FOUND"`.

Configuration is read from the environment at startup:

| Variable | Default | Purpose |
| --- | --- | --- |
| `SALES_API_SESSION_TTL_SECONDS` | `1800` | Idle timeout per session |
| `SALES_API_MAX_SESSIONS` | `100` | Hard cap on live sessions |
| `SALES_API_CORS_ORIGINS` | empty | Comma-separated dev origins |
| `SALES_API_HOST` | `127.0.0.1` | Bind address for `python -m sales_api` |
| `SALES_API_PORT` | `8000` | Bind port for `python -m sales_api` |

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/health` | Liveness, version and live session count |
| `GET` | `/api/meta` | App labels, currency, limits, CSV guide, filter presets |
| `POST` | `/api/datasets/demo` | Create a session from the bundled demo CSV |
| `POST` | `/api/datasets` | Create a session from a multipart `file` upload |
| `GET` | `/api/datasets/{session_id}` | Dataset summary and any cleaning result |
| `DELETE` | `/api/datasets/{session_id}` | Forget the session and its data |
| `PUT` | `/api/datasets/{session_id}/mapping` | Apply manual column overrides |
| `GET` | `/api/datasets/{session_id}/date-inspection` | Describe the date column before cleaning |
| `POST` | `/api/datasets/{session_id}/cleaning` | Validate and clean; store the result |
| `GET` | `/api/datasets/{session_id}/filters` | Options, presets and the default filter state |
| `POST` | `/api/datasets/{session_id}/filters/resolve` | Clamp a proposed filter selection |
| `POST` | `/api/datasets/{session_id}/overview` | Overview page payload |
| `POST` | `/api/datasets/{session_id}/products` | Products page payload |
| `POST` | `/api/datasets/{session_id}/regions` | Regions page payload |
| `POST` | `/api/datasets/{session_id}/explorer` | Data Explorer payload with search and limit |
| `GET` | `/api/datasets/{session_id}/exports/cleaned` | Download every cleaned row as CSV |
| `POST` | `/api/datasets/{session_id}/exports/filtered` | Download the filtered rows as CSV |
| `GET` | `/api/datasets/{session_id}/exports/quality-report` | Download the quality report as CSV |

Upload limits come from `sales_dashboard.config` (50 MB, 250,000 rows) and are
enforced before parsing. Unsupported extensions and unreadable files return
`400 INVALID_DATASET` with a `hint`; oversized files return `413`.

### Mapping

`PUT .../mapping` accepts canonical fields mapped to source columns. `null` or
`""` removes a field. Overrides are applied on top of automatic detection, so a
partial body only changes the named fields. A source column may belong to one
canonical field only. A successful change refreshes the profile, clears any
cleaning result and increments `revision`.

```json
{"fields": {"product": "PRODUCTCODE"}}
```

### Cleaning

`POST .../cleaning` accepts `date_format` (`auto`, `DMY`, `MDY`) and
`exclude_statuses` (default `true`). `auto` answers `409 DATE_DECISION_REQUIRED`
with the inspection in `details` when day/month values are ambiguous; re-send
the request with `DMY` or `MDY`. A dataset whose mapping is still incomplete
answers `422 CLEANING_FAILED` and is never modified.

```json
{"date_format": "auto", "exclude_statuses": true}
```

### Filters

`GET .../filters` returns the dataset bounds, available options, preset ranges
and the state the dashboard opens with (`last_90_days`). `POST .../filters/resolve`
accepts any subset of `start_date`, `end_date`, `preset`, `categories`,
`regions`, `products` and `statuses`. Dates are clamped to the dataset, unknown
values are dropped rather than rejected, and a named preset takes precedence
over explicit dates. Both endpoints require a cleaned dataset.

### Pages

`POST .../overview`, `.../products`, `.../regions` and `.../explorer` return the
page body the frontend renders. The request body is optional and accepts the
same filter fields as `.../filters/resolve`; omitting it (or sending `{}`) uses
the state the dashboard opens with. Dates and selections are clamped and
sanitised by one shared helper, so a page can never disagree with the filter
panel that produced its state. Every response is byte-for-byte the payload
frozen in `tests/golden/demo.json` (`pages.default`, `pages.narrow`,
`pages.empty`).

`.../explorer` adds two fields:

| Field | Default | Meaning |
| --- | --- | --- |
| `search` | omitted | Case-insensitive literal search across text and date columns. Omitted asks the server to pick a stable term from the data; `""` means no search. |
| `limit` | `25` | Preview rows, from 1 to 500. Counts and revenue always cover every matching row. |

Page endpoints require a cleaned dataset (`409 DATASET_NOT_CLEANED`) with
usable dates (`409 NO_DATE_COLUMN`).

### Exports

Three CSV downloads are available once cleaning has run. Each response sets
`Content-Disposition: attachment` with a safe, timestamped filename built from
the uploaded file's name, and its bytes match the `exports` block in
`tests/golden/`.

| Method | Path | Contents |
| --- | --- | --- |
| `GET` | `.../exports/cleaned` | Every cleaned row |
| `POST` | `.../exports/filtered` | Rows matching the filter body, optionally narrowed by `search` |
| `GET` | `.../exports/quality-report` | The quality summary and issue rows |

Files are UTF-8 CSV with a byte-order mark so Excel reads them correctly. The
filtered body accepts the same fields as the page endpoints; `search` defaults
to `""` (no search). The filtered download needs usable dates
(`409 NO_DATE_COLUMN`), while the cleaned data and quality report can still be
downloaded when cleaning blocked the analysis. `Content-Disposition` is exposed
through CORS for the dev frontend.

The React client in `frontend/` consumes these endpoints through a Vite dev
proxy. Run `npm run dev` there while the API listens on port 8000; see
`frontend/README.md`. In production, FastAPI serves `frontend/dist` from the
same origin with a client-route fallback; see `docs/DEPLOYMENT.md`.

## Response shapes

A dataset response wraps the same serialisers the golden fixtures use, so the
frozen contract in `tests/golden/` is also the wire contract:

```json
{
  "session_id": "…",
  "dataset": {
    "filename": "sales_demo.csv",
    "source": "demo",
    "row_count": 4899,
    "column_count": 12,
    "profile": {"...": "..."},
    "mapping": {"fields": {}, "is_complete": true, "table": []},
    "preview": [{"...": "..."}]
  },
  "cleaned": null,
  "mapping_override": {},
  "revision": 0
}
```

`cleaned` is a cleaning summary once preparation has run. Every response passes
through `sales_dashboard.payloads.jsonable`, the same serialiser used to build
the golden files, so floats are rounded to six decimals and dates are ISO
strings on the wire exactly as they are in `tests/golden/`. Raw NumPy scalars
never reach a client.

## Errors

Every failure uses one envelope, including framework 404s and validation
errors:

```json
{
  "error": {
    "code": "INVALID_DATASET",
    "message": "Unsupported file type (.txt).",
    "details": {"hint": "Upload a .csv file."}
  }
}
```

| Code | Status | Meaning |
| --- | --- | --- |
| `SESSION_NOT_FOUND` | 404 | Unknown or expired session |
| `INVALID_DATASET` | 400 | Domain load failure (extension, encoding, empty file) |
| `EMPTY_UPLOAD` / `MISSING_FILENAME` | 400 | Malformed upload |
| `UPLOAD_TOO_LARGE` | 413 | Over the 50 MB limit |
| `INVALID_MAPPING` | 422 | Unknown column or a column assigned twice |
| `DATE_DECISION_REQUIRED` | 409 | Ambiguous dates; inspection in `details` |
| `CLEANING_FAILED` | 422 | Required columns or a mapped column is missing |
| `DATASET_NOT_CLEANED` | 409 | The dashboard was requested before cleaning |
| `NO_DATE_COLUMN` | 409 | Cleaning left no usable dates |
| `INVALID_REQUEST` | 422 | FastAPI request validation, with `details.errors` |
| `INTERNAL_ERROR` | 500 | Unexpected failure; details are logged, not returned |

## Tests

```powershell
python -m pytest tests/test_api_sessions.py tests/test_api_routes.py tests/test_api_config.py tests/test_api_preparation.py tests/test_api_filters.py tests/test_api_pages.py tests/test_api_exports.py tests/test_payloads.py
```

`test_api_routes.py` compares the demo dataset response with
`tests/golden/demo.json`. `test_api_preparation.py` and `test_api_filters.py`
compare mapping, date inspection, cleaning reports and resolved filter states
with the same fixtures, `test_api_pages.py` compares all four page bodies for
the default, narrow and zero-row selections, and `test_api_exports.py` compares
the downloaded filename, size and SHA-256 with the frozen export. The HTTP layer
therefore cannot drift from the frozen contract.
