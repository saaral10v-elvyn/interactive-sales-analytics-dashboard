# Sales Analytics frontend

React 19 + TypeScript client for the FastAPI analytics API. The frontend is a
presentation layer only: every KPI, chart point, table row and export byte comes
from the Python domain package, so the analytics rules stay in one place.

## Requirements

- Node 24 (the version CI uses)
- The API running on <http://127.0.0.1:8000>

## Development

From this directory:

```powershell
npm install
npm run dev
```

The dev server runs on <http://localhost:5173> and proxies `/api` to
`127.0.0.1:8000`. Override the target when the API is elsewhere:

```powershell
$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:9000"
npm run dev
```

Start the API from the repository root first:

```powershell
$env:PYTHONPATH = "src"
python -m sales_api
```

## Checks

```powershell
npm run lint      # oxlint
npm run typecheck # strict TypeScript build
npm test          # Vitest + Testing Library
npm run build     # production bundle in dist/
```

The lockfile is committed and kept in sync with `package.json`; CI and the
container both use `npm ci`. After changing dependencies, run `npm install` and
commit the updated `package-lock.json`.

## Production build

`npm run build` writes `dist/`. FastAPI serves it from the same origin when
`SALES_API_STATIC_DIR` points at the directory (or when `frontend/dist` exists).
The production container builds this directory automatically; see
[docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md).

## Structure

```text
src/
├── api/          typed client and wire types for the FastAPI contract
├── components/   shell, filters, charts, tables and feedback primitives
├── context/      session, cleaning, filters and notices
├── lib/          display formatting, page-payload hook
├── pages/        Home, Prepare, Overview, Products, Regions, Explorer
└── test/         Vitest setup (jsdom + jest-dom)
```

The app stores only the opaque session id in `sessionStorage`; the dataset lives
in the API's in-memory session store. Refreshing restores the session while it
has not expired, and "New dataset" deletes it.

## Design notes

- No analytics in TypeScript. Filters are resolved by the API and pages render
  the returned payload.
- Recharts draws the charts (ADR-001); tables are native HTML with client-side
  sorting.
- INR formatting mirrors `sales_dashboard.formatting`, including Indian digit
  grouping and lakh/crore shorthand.
- Analytics routes are loaded lazily so the initial bundle stays small. In
  development Vite proxies `/api`; in production FastAPI serves the built
  client from the same origin.
