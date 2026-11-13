"""CSV loading with friendly, user-facing error messages."""

import csv
import io
from pathlib import Path
from typing import Literal

import pandas as pd

from sales_dashboard.config import (
    ALLOWED_EXTENSIONS,
    DEMO_CSV_PATH,
    LARGE_DATASET_ROWS,
    MAX_ROWS,
    MAX_UPLOAD_BYTES,
    MAX_UPLOAD_MB,
    SUPPORTED_DELIMITERS,
    SUPPORTED_ENCODINGS,
)
from sales_dashboard.models import LoadedDataset
from sales_dashboard.profiling import profile_dataset
from sales_dashboard.schema import detect_dataframe_mapping


class DataLoadError(Exception):
    """A problem that can be explained to the person using the app."""

    def __init__(self, message: str, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def __str__(self) -> str:
        if self.hint:
            return f"{self.message}\n\n**What to try:** {self.hint}"
        return self.message


def _validate_filename(filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        shown = suffix or "no extension"
        raise DataLoadError(
            f"Unsupported file type ({shown}).",
            "Upload a .csv file. A downloadable sample is available on the Home page.",
        )


def _decode_bytes(data: bytes) -> tuple[str, str]:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return data.decode("utf-16"), "utf-16"
        except UnicodeDecodeError:
            pass
    if data.startswith(b"\xef\xbb\xbf"):
        try:
            return data.decode("utf-8-sig"), "utf-8-sig"
        except UnicodeDecodeError:
            pass

    for encoding in SUPPORTED_ENCODINGS:
        if encoding == "utf-8-sig":
            continue
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    raise DataLoadError(
        "The file could not be decoded as text.",
        "Save it as a UTF-8 CSV and upload it again.",
    )


def _detect_delimiter(text: str) -> str:
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=SUPPORTED_DELIMITERS)
        if dialect.delimiter in SUPPORTED_DELIMITERS:
            return dialect.delimiter
    except csv.Error:
        pass

    counts = {delimiter: sample.count(delimiter) for delimiter in SUPPORTED_DELIMITERS}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def read_csv_bytes(
    data: bytes,
    filename: str,
    *,
    source: Literal["demo", "upload"] = "upload",
) -> LoadedDataset:
    """Read CSV bytes into a string-preserving DataFrame.

    Values are intentionally kept as text here. Type coercion, validation and
    cleaning belong to the data pipeline in the next milestone.
    """
    _validate_filename(filename)
    if not data or not data.strip():
        raise DataLoadError(
            "This file is empty.",
            "Choose a CSV with a header row and at least one data row.",
        )
    if len(data) > MAX_UPLOAD_BYTES:
        raise DataLoadError(
            f"This file is larger than the {MAX_UPLOAD_MB} MB limit.",
            "Reduce the file size or split it into smaller CSV files.",
        )

    text, encoding = _decode_bytes(data)
    if "\x00" in text:
        raise DataLoadError(
            "This file does not look like a text-based CSV.",
            "Export the data as a UTF-8 CSV and try again.",
        )

    delimiter = _detect_delimiter(text)
    try:
        dataframe = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            dtype=str,
            keep_default_na=False,
            na_filter=False,
            skipinitialspace=True,
        )
    except pd.errors.EmptyDataError as exc:
        raise DataLoadError(
            "The CSV has no readable header or data.",
            "Check that the first row contains column names.",
        ) from exc
    except pd.errors.ParserError as exc:
        raise DataLoadError(
            "The CSV could not be parsed.",
            "Check for broken quotes or inconsistent delimiters, then upload it again.",
        ) from exc
    except (UnicodeError, ValueError) as exc:
        raise DataLoadError(
            "The CSV could not be read.",
            "Open the file in a spreadsheet tool, export it as a clean CSV, and try again.",
        ) from exc

    dataframe.columns = [str(column).strip() for column in dataframe.columns]

    if dataframe.empty:
        raise DataLoadError(
            "The CSV has column headers but no data rows.",
            "Add at least one row of sales data and upload it again.",
        )
    if len(dataframe) > MAX_ROWS:
        raise DataLoadError(
            f"This file contains {len(dataframe):,} rows, above the {MAX_ROWS:,}-row limit.",
            "Reduce the dataset or split it into smaller files.",
        )

    # Incomplete mappings are not fatal: the Home page shows the missing fields
    # and lets the user map them manually before validation and cleaning.
    mapping = detect_dataframe_mapping(dataframe)

    warnings: list[str] = []
    if len(dataframe) > LARGE_DATASET_ROWS:
        warnings.append(
            f"This dataset has {len(dataframe):,} rows. Initial views may take a little longer."
        )

    profile = profile_dataset(dataframe, mapping)
    return LoadedDataset(
        dataframe=dataframe,
        filename=filename,
        source=source,
        size_bytes=len(data),
        encoding=encoding,
        delimiter=delimiter,
        mapping=mapping,
        profile=profile,
        warnings=tuple(warnings),
    )


def load_demo_dataset(path: Path = DEMO_CSV_PATH) -> LoadedDataset:
    """Load the bundled demo CSV through the same path as an upload."""
    if not path.exists():
        raise DataLoadError(
            "The bundled demo dataset is missing.",
            "Regenerate it with `python -m sales_dashboard.demo` and reload the app.",
        )
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise DataLoadError(
            "The bundled demo dataset could not be read.",
            "Check that the file exists in data/sample and try again.",
        ) from exc
    return read_csv_bytes(payload, path.name, source="demo")
