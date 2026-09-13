"""Year coverage — detecting and describing partial years.

A year with only part of its months present is not comparable with a full one.
This module makes that visible everywhere a figure is aggregated per year, so
it cannot quietly distort a total, a growth rate or a ranking.

Why this exists as its own module rather than a note in the UI: the warning has
to appear on every page that aggregates by year, and a helper is the only way
to guarantee a new tab added later inherits it. No Streamlit imports.
"""
from __future__ import annotations

import pandas as pd

MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def year_coverage(df: pd.DataFrame) -> pd.DataFrame:
    """One row per year: how many of its 12 months carry data.

    Returns columns: year, months_present, first_month, last_month,
    is_partial, coverage_label.
    """
    d = df[df["issuance_date"].notna()].copy()
    if d.empty:
        return pd.DataFrame(columns=["year", "months_present", "first_month",
                                     "last_month", "is_partial", "coverage_label"])
    d["_m"] = d["issuance_date"].dt.month
    rows = []
    for year, g in d.groupby(d["issuance_date"].dt.year):
        months = sorted(g["_m"].unique())
        n = len(months)
        rows.append({
            "year": int(year),
            "months_present": n,
            "first_month": MONTH_ABBR[months[0] - 1],
            "last_month": MONTH_ABBR[months[-1] - 1],
            "is_partial": n < 12,
            "coverage_label": (
                f"{n}/12 months ({MONTH_ABBR[months[0] - 1]}–"
                f"{MONTH_ABBR[months[-1] - 1]})" if n < 12 else "full year"
            ),
        })
    return pd.DataFrame(rows).sort_values("year").reset_index(drop=True)


def partial_years(df: pd.DataFrame, years: list[int] | None = None) -> pd.DataFrame:
    """Just the partial years, optionally restricted to a selection."""
    cov = year_coverage(df)
    if cov.empty:
        return cov
    out = cov[cov["is_partial"]]
    if years is not None:
        out = out[out["year"].isin([int(y) for y in years])]
    return out


def coverage_warning(df: pd.DataFrame, years: list[int] | None = None) -> str | None:
    """A ready-to-display sentence, or None when every year in scope is full.

    The wording deliberately names the consequence, not just the fact — a bare
    "2019 is partial" invites the reader to nod and carry on comparing it.
    """
    part = partial_years(df, years)
    if part.empty:
        return None

    bits = [f"<b>{int(r.year)}</b> has only {r.months_present} of 12 months "
            f"({r.first_month}–{r.last_month})" for r in part.itertuples()]
    listed = "; ".join(bits)

    cov = year_coverage(df)
    in_scope = cov if years is None else cov[cov["year"].isin([int(y) for y in years])]
    has_full = bool((~in_scope["is_partial"]).any())

    tail = (
        " Totals, growth rates and rankings for these years are <b>not "
        "comparable</b> with the full years alongside them."
        if has_full else
        " Totals for these years cover only part of the year."
    )
    return f"Partial year data — {listed}.{tail}"


def annotate_years(table: pd.DataFrame, df: pd.DataFrame,
                   year_col: str = "year") -> pd.DataFrame:
    """Add a `coverage` column to a per-year table, for tables that show one
    row per year and can carry the flag inline rather than in a banner."""
    cov = year_coverage(df)[["year", "coverage_label"]]
    out = table.copy()
    out[year_col] = out[year_col].astype(int)
    return out.merge(cov.rename(columns={"year": year_col,
                                         "coverage_label": "coverage"}),
                     on=year_col, how="left")
