# USDA Price-Cost Margins Dashboard

An interactive dashboard comparing the prices farmers **pay** for inputs against the prices they **receive** for what they sell, split between crop farms and livestock farms, monthly since 2019.

Built with Plotly Dash.

> This is an independent project built on publicly available data. It is not
> affiliated with or endorsed by the U.S. Department of Agriculture.

## Status

**Phase 1 — replication.** The app currently renders a single static two-panel chart
showing prices paid against prices received for each sector. Phase 2 will add interactivity and
additional data sources.

## Credits

Claude Opus 5 was used in the development of this tool.

## Data Source

[USDA NASS Quick Stats API](https://quickstats.nass.usda.gov/api) — the monthly index
series published in the *Agricultural Prices* report. Requires a free API key.

Four national monthly series are pulled, all on NASS's 2011 = 100 base:

| Panel | Series | NASS `short_desc` |
|---|---|---|
| Crop farms | Prices received | `CROP TOTALS - INDEX FOR PRICE RECEIVED, 2011` |
| Crop farms | Prices paid | `CROP SECTOR - INDEX FOR PRICE PAID, 2011` |
| Livestock farms | Prices received | `ANIMAL TOTALS, INCL PRODUCTS - INDEX FOR PRICE RECEIVED, 2011` |
| Livestock farms | Prices paid | `ANIMAL SECTOR - INDEX FOR PRICE PAID, 2011` |

Note NASS's own naming asymmetry: prices *received* indexes are keyed on `... TOTALS`
commodities, prices *paid* indexes on `... SECTOR` ones.

The cache keeps the raw 2011 = 100 values; `app.py` rebases them so the `BASE_YEAR`
calendar year averages 100. Prices-paid data is monthly from 1995 onward (quarterly
1990–1994), which is well before the 2019 start of the current view.

## Chart Construction

- Each panel shades the gap between the two lines: **green** where prices exceed
  costs, **red** where costs exceed prices.
- The shaded band inserts interpolated points at each crossover, so the colour
  changes exactly where the lines cross rather than at the next month's grid point.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env      # then add your NASS API key
```

## Usage

```bash
.venv/bin/python fetch_data.py    # refresh data/ag_prices.parquet
.venv/bin/python app.py           # serve on http://127.0.0.1:8053
```

Or both at once with `./run.sh` (expects the venv to be active).

The API key is only needed to fetch. The app runs fine against an existing
`data/ag_prices.parquet`.

## Configuration

Constants at the top of `app.py`:

| Constant | Purpose |
|---|---|
| `BASE_YEAR` | Year whose monthly average is rebased to 100 (also sets the chart's start) |
| `TITLE` / `SUBTITLE` | Headline text |
| `BETA` | Shows or hides the "Beta" tag next to the title |

## Requirements

Python 3.9+ (developed on 3.9; the container image uses 3.12). See `requirements.txt`.

## License

MIT
