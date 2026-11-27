# Deployment

## Production architecture

The deployed application is a single container on port `8000`:

- FastAPI serves the JSON API under `/api` and the CSV downloads under
  `/exports`.
- The same process serves the built React client from `frontend/dist`, so the
  browser talks to one origin and CORS is not required.
- The React Router fallback returns `index.html` for client routes such as
  `/overview` and `/explorer`, but never for `/api`, `/exports` or a missing
  asset.
- The container runs as a non-root user and reports readiness at
  `/api/health`.

## Docker

Build the React client and the API runtime in one image:

```powershell
docker build -t sales-dashboard .
docker run --rm -p 8000:8000 sales-dashboard
```

Open <http://localhost:8000>. The Node build stage produces `frontend/dist`;
the Python stage installs only the runtime requirements and copies `src`, `data`
and the built client.

To supply a different demo file without rebuilding:

```powershell
docker run --rm -p 8000:8000 `
  -v "${PWD}/data/sample:/app/data/sample:ro" `
  sales-dashboard
```

The image sets `SALES_API_HOST=0.0.0.0`, `SALES_API_PORT=8000`,
`SALES_API_STATIC_DIR=/app/frontend/dist` and `PYTHONPATH=/app/src`.

## Local production build

Run the same build the container runs, without Docker:

```powershell
cd frontend
npm ci
npm run build
cd ..

$env:PYTHONPATH = "src"
$env:SALES_API_STATIC_DIR = "frontend/dist"
python -m sales_api
```

Open <http://localhost:8000>. On macOS or Linux:

```bash
PYTHONPATH=src SALES_API_STATIC_DIR=frontend/dist python -m sales_api
```

For frontend development, keep the two-process workflow in
[frontend/README.md](../frontend/README.md): `npm run dev` on port 5173 and the
API on port 8000. Vite proxies `/api`, so no CORS configuration is needed.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `SALES_API_HOST` | `127.0.0.1` | Bind address; the container sets `0.0.0.0` |
| `SALES_API_PORT` | `8000` | HTTP port |
| `SALES_API_STATIC_DIR` | `frontend/dist` if present | Built SPA directory; leave unset for API-only runs |
| `SALES_API_SESSION_TTL_SECONDS` | `1800` | Idle session lifetime |
| `SALES_API_MAX_SESSIONS` | `100` | In-memory session cap with LRU eviction |
| `SALES_API_CORS_ORIGINS` | empty | Comma-separated allow-list; only needed for a split-origin dev setup |
| `SALES_API_ENABLE_DOCS` | `true` | Serves `/api/docs` and `/api/openapi.json` |
| `SALES_API_GZIP_MIN_SIZE` | `1024` | Minimum response size for gzip; `0` compresses everything |
| `SALES_API_SECURITY_HEADERS` | `true` | Adds nosniff, frame-denial, referrer and permissions headers |

Set `SALES_API_ENABLE_DOCS=false` if the public deployment should not expose the
OpenAPI schema.

## Session model and scaling

Sessions are process-local and hold the loaded and cleaned DataFrames in memory:

- Sessions expire after 30 minutes of inactivity and are capped at 100, with
  least-recently-used eviction.
- A restart invalidates every session, so a visitor must upload the file again.
- Run **one worker and one instance**. Multiple workers would each hold a
  different session set, and a visitor would randomly lose their dataset.
- Horizontal scaling requires replacing the store with a shared implementation
  such as Redis. That is out of scope for this release.

Uploads are capped at 50 MB and 250,000 rows, but a wide file near those limits
can need several times its size in memory while it is parsed and cleaned. Size
the instance for the expected uploads, not just the idle app.

## Platform checklist

Any container host works: Render, Fly.io, Railway, Google Cloud Run, Azure
Container Apps or ECS.

1. Build from the repository `Dockerfile`.
2. Expose port `8000`.
3. Set `SALES_API_STATIC_DIR=/app/frontend/dist` if the platform does not keep
   the image environment variables.
4. Use `/api/health` as the health-check path.
5. Run a single instance with one worker.
6. Let the platform terminate HTTPS; the application does not redirect or
   assume a scheme.

## Verify a deployment

- `GET /api/health` returns `{"status": "ok", ...}`.
- `GET /` returns the React shell with `<div id="root"></div>`.
- Open `/overview` directly and refresh; the same shell should load.
- Load the demo dataset, validate and clean it, and open all four analytics
  pages.
- Apply a date filter, search the Data Explorer, and download a CSV to confirm
  `Content-Disposition` and the exported bytes work over HTTPS.
- Reload the page and confirm the session is restored; use **New dataset** and
  confirm the old session is gone.
- Check the browser console for failed asset requests or CORS errors.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Blank page or 404 on refresh | Confirm `SALES_API_STATIC_DIR` points at a directory containing `index.html`; rebuild with `npm run build` |
| Missing JavaScript or CSS | Confirm the build copied `frontend/dist/assets`; the container does this from the Node stage |
| API returns 404 for `/` | The static directory is unset or has no `index.html`; this is intentional for API-only runs |
| Sessions disappear after a request | More than one worker or instance is running, or the process restarted |
| `/api/docs` returns 404 | `SALES_API_ENABLE_DOCS` is disabled |
| Upload rejected as too large | The limit is 50 MB and 250,000 rows in the domain configuration |
| Ambiguous dates block cleaning | Choose **Day first (DMY)** or **Month first (MDY)**; the app never guesses |
| CORS error in development | Run Vite with its `/api` proxy, or add the Vite origin to `SALES_API_CORS_ORIGINS` |

## Privacy

Uploaded files are processed in memory for the lifetime of the API session and
are never written to disk or sent to a third-party service. Clearing or replacing
the dataset removes it from the session. As with any hosted service, the server
receives the uploaded bytes while the session is active.
