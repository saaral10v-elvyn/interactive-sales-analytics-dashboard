"""Pure helpers for searching the cleaned dataset in the Data Explorer."""

from __future__ import annotations

import pandas as pd


def search_dataframe(dataframe: pd.DataFrame, query: str) -> pd.DataFrame:
    """Return rows whose text or date columns contain the query.

    Matching is case-insensitive and literal, so characters such as ``%`` or
    ``.`` are not treated as regular expressions. Numeric-only datasets have no
    searchable text, in which case the full frame is returned unchanged.
    """
    term = query.strip()
    if not term or dataframe.empty:
        return dataframe.copy()

    masks: list[pd.Series] = []
    for column in dataframe.columns:
        series = dataframe[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            text = series.dt.strftime("%Y-%m-%d %H:%M:%S")
            masks.append(text.str.contains(term, case=False, regex=False, na=False))
        elif isinstance(series.dtype, pd.CategoricalDtype) or pd.api.types.is_string_dtype(series):
            masks.append(
                series.astype("string").str.contains(
                    term,
                    case=False,
                    regex=False,
                    na=False,
                )
            )

    if not masks:
        return dataframe.copy()

    matched = masks[0]
    for mask in masks[1:]:
        matched = matched | mask
    return dataframe.loc[matched]
