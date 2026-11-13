# Deployment

The app is a standard Streamlit project: `app.py` is the entry point, runtime
dependencies are pinned in `requirements.txt`, and `app.py` adds `src/` to the
import path, so no package installation step is required.

## Streamlit Community Cloud

1. Push this repository to GitHub.
2. Sign in at <https://share.streamlit.io> with the GitHub account that owns the
   repository.
3. Choose **Create app** and select the repository and branch.
4. Set **Main file path** to `app.py`.
5. Open **Advanced settings** and select Python 3.12.
6. Deploy. The first build installs `requirements.txt` and usually takes a few
   minutes.

No secrets or environment variables are required. The app reads only the
bundled demo CSV and files uploaded by the current visitor.

### Verify the deployment

- Open `https://<your-app>.streamlit.app/_stcore/health`; it should return `ok`.
- Load the demo dataset, run **Validate and clean data**, and open every page.
- Download one file from the Data Explorer to confirm exports work over HTTPS.

### Resource limits

Community Cloud provides roughly 1 GB of memory per app. The application caps
uploads at 50 MB and 250,000 rows, but a wide file near those limits can still
need several times its size in memory while it is parsed and cleaned. If a large
upload crashes the app, reduce the file size or raise the instance resources on
a paid plan.

## Docker

Build and run a self-hosted container:

```powershell
docker build -t sales-dashboard .
docker run --rm -p 8501:8501 sales-dashboard
```

Then open <http://localhost:8501>. The image runs as a non-root user and includes
a health check against `/_stcore/health`.

Use a bind mount to supply a different demo file without rebuilding:

```powershell
docker run --rm -p 8501:8501 -v "${PWD}/data/sample:/app/data/sample:ro" sales-dashboard
```

## Configuration

| Setting | Location |
|---|---|
| App name, tagline and version | `src/sales_dashboard/config.py` |
| Currency code and symbol | `src/sales_dashboard/config.py` |
| Upload size limit | `src/sales_dashboard/config.py` and `.streamlit/config.toml` |
| Theme colours | `.streamlit/config.toml` |
| Demo dataset range and seed | `src/sales_dashboard/config.py` |

The interface theme is light-only by design, because the custom cards and charts
use a fixed palette that is tuned for light backgrounds.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ModuleNotFoundError: sales_dashboard` | Run Streamlit from the repository root, or confirm `app.py` is the entry point. The script adds `src/` automatically. |
| Upload rejected as too large | The limit is 50 MB in both `.streamlit/config.toml` and the app configuration. Raise both values together. |
| App restarts or shows a memory error | Reduce the CSV size or move to an instance with more memory. |
| Ambiguous dates block cleaning | Choose **Day first (DMY)** or **Month first (MDY)** in the cleaning panel. This is deliberate: the app never guesses. |
| Charts look empty in a screenshot | Give Plotly a moment to render. The live app is interactive; this only affects automated captures. |

## Privacy

Uploaded files are processed in memory for the lifetime of the Streamlit session
and are never written to disk or sent to a third-party service. Clearing or
replacing the dataset removes it from session state. As with any hosted service,
the server receives the uploaded bytes while the session is active.
