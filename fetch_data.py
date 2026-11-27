"""
Fetch USDA NASS Agricultural Prices index data via the Quick Stats API.

Pulls the four national monthly index series behind the cost/price squeeze
chart — prices received and prices paid, for the crop and animal sectors.

Run directly to refresh the local parquet cache:
    python fetch_data.py
"""

import os
import pathlib
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://quickstats.nass.usda.gov/api/api_GET/"
CACHE_PATH = pathlib.Path("data/ag_prices.parquet")

# NASS publishes these on a 2011 = 100 base. The dashboard rebases them to a
# user-chosen year (see BASE_YEAR in app.py), so the cache keeps the raw index.
#
# Note the asymmetry in NASS's own naming: the prices-received indexes are
# keyed on "TOTALS" commodities, the prices-paid indexes on "SECTOR" ones.
# (panel, series) -> short_desc
SERIES = {
    ("Crop farms", "Prices"): "CROP TOTALS - INDEX FOR PRICE RECEIVED, 2011",
    ("Crop farms", "Costs"): "CROP SECTOR - INDEX FOR PRICE PAID, 2011",
    ("Livestock farms", "Prices"): "ANIMAL TOTALS, INCL PRODUCTS - INDEX FOR PRICE RECEIVED, 2011",
    ("Livestock farms", "Costs"): "ANIMAL SECTOR - INDEX FOR PRICE PAID, 2011",
}


def _api_key() -> str:
    """Deferred lookup — only fetching needs the key, not the app reading the cache."""
    key = os.environ.get("NASS_API_KEY")
    if not key:
        raise RuntimeError(
            "NASS_API_KEY not set — required to fetch data "
            "(not needed to run the app against an existing data/ag_prices.parquet)"
        )
    return key


def fetch_short_desc(short_desc: str) -> pd.DataFrame:
    params = {
        "key": _api_key(),
        "short_desc": short_desc,
        "freq_desc": "MONTHLY",
        "agg_level_desc": "NATIONAL",
        "format": "JSON",
    }
    resp = requests.get(BASE_URL, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()
    if "error" in payload:
        raise ValueError(f"API error for '{short_desc}': {payload['error']}")
    return pd.DataFrame(payload.get("data", []))


def fetch_all() -> pd.DataFrame:
    frames = []
    for (panel, series), short_desc in SERIES.items():
        print(f"Fetching {panel} / {series}: {short_desc}")
        df = fetch_short_desc(short_desc)
        print(f"  -> {len(df):,} rows")
        if df.empty:
            raise ValueError(f"No rows returned for '{short_desc}'")
        df["panel"] = panel
        df["series"] = series
        frames.append(df)
    return pd.concat(frames, ignore_index=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df["Value"] = pd.to_numeric(df["Value"].str.replace(",", ""), errors="coerce")
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    # For MONTHLY rows begin_code is the month number ("01".."12")
    df["month"] = pd.to_numeric(df["begin_code"], errors="coerce")

    df["date"] = pd.to_datetime(
        {"year": df["year"], "month": df["month"], "day": 1}, errors="coerce"
    )

    df = df.rename(columns={"Value": "value"})
    df = df[["date", "year", "month", "panel", "series", "short_desc", "unit_desc", "value"]]
    df = df.dropna(subset=["date", "value"])
    df = df.sort_values(["panel", "series", "date"])
    return df.reset_index(drop=True)


def main():
    CACHE_PATH.parent.mkdir(exist_ok=True)
    cleaned = clean(fetch_all())

    # Write-then-rename so a restart mid-write never sees a partial file
    tmp = CACHE_PATH.with_suffix(".tmp")
    cleaned.to_parquet(tmp, index=False)
    tmp.replace(CACHE_PATH)

    print(f"\nSaved {len(cleaned):,} rows -> {CACHE_PATH}")
    for (panel, series), g in cleaned.groupby(["panel", "series"]):
        print(
            f"  {panel:16s} {series:7s} "
            f"{g['date'].min().date()} -> {g['date'].max().date()}  ({len(g):,} months)"
        )


def load_cache() -> pd.DataFrame:
    if not CACHE_PATH.exists():
        raise FileNotFoundError(
            f"{CACHE_PATH} not found. Run `python fetch_data.py` first."
        )
    return pd.read_parquet(CACHE_PATH)


if __name__ == "__main__":
    main()
