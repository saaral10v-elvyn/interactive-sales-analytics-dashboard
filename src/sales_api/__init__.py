"""FastAPI backend for the sales analytics dashboard.

The HTTP layer is deliberately thin: every rule lives in
:mod:`sales_dashboard`, and the API adds sessions, routing and JSON transport on
top. Importing this package does not start a server; call
:func:`sales_api.app.create_app` or run ``python -m sales_api``.
"""

from sales_api.app import create_app

__all__ = ["create_app"]
