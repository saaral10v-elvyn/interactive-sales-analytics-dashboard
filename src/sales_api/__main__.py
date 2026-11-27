"""Run the API with ``python -m sales_api``.

The session store is process-local, so uvicorn's default of one worker is
deliberate: extra workers would each hold a different set of sessions.
"""

from __future__ import annotations

import os


def main() -> None:
    """Start uvicorn on the configured host and port."""
    import uvicorn

    host = os.environ.get("SALES_API_HOST", "127.0.0.1")
    try:
        port = int(os.environ.get("SALES_API_PORT", "8000"))
    except ValueError:
        port = 8000
    uvicorn.run("sales_api.app:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
