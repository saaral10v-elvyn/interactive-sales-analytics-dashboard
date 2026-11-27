# Build the React client first, then ship only the API runtime and its output.
FROM node:24-slim AS frontend-build

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src \
    SALES_API_HOST=0.0.0.0 \
    SALES_API_PORT=8000 \
    SALES_API_STATIC_DIR=/app/frontend/dist

WORKDIR /app

RUN useradd --create-home --uid 1000 appuser

COPY requirements.txt ./
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY src ./src
COPY data ./data
COPY --from=frontend-build /build/dist ./frontend/dist

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

ENTRYPOINT ["python", "-m", "sales_api"]
