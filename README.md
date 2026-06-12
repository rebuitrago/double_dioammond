# DDD Platform

Competitiveness analysis for emerging economies, built on the **Dual Double
Diamond** model (Cho, Moon & Kim 2008), extending Rugman & D'Cruz (1993) and
Moon, Rugman & Verbeke (1998).

```
ddd-platform/
├── db/
│   └── schema.sql                     # Supabase/Postgres schema + seed
├── ddd/
│   ├── scoring.py                     # normalization, weighting, diamond coords (pure, offline)
│   └── connectors.py                  # WDI + UNCTAD fetchers -> observation rows
├── validation/
│   └── korea_singapore_1998.py        # replicates the published Table 4 + diamonds
└── requirements.txt
```

## Architecture (precompute → store → read)

1. **GitHub Actions** runs `connectors.py` on a schedule → writes raw values to
   Supabase `observation` (with provenance).
2. A scoring job runs `scoring.py` over a chosen country/indicator/vintage set →
   writes a versioned `run` + `score` rows.
3. **Streamlit** only *reads* `score` / `diamond_coords` and draws the diamonds.

Keeping compute out of the app keeps it fast and keeps every score reproducible.

## Run the scoring job
Turns stored `observation` rows into a versioned run + scores:
```bash
export SUPABASE_URL=...  SUPABASE_SERVICE_KEY=...
python -m ddd.score_run --label "EM 2010-2022 pooled" \
    --normalization pooled --year-from 2010 --year-to 2022 \
    --vintage "WDI 2025-03"
# add --dry-run to compute + print the coverage report without writing
```
- `--normalization within_year` (each year's leader = 100; for rankings) or
  `pooled` (best value across the whole panel = 100; for trends).
- Prints a coverage report: indicators defined vs. actually used per cell.

## Set up the database
Paste `db/schema.sql` into the Supabase SQL editor. It creates the framework
(8 determinants × 2 contexts), provenance-tracked `observation`, versioned
`run`/`score`, and a `diamond_coords` view. The seed loads a starter indicator
catalog — **add a criterion later = one `INSERT` into `indicator`.**

## Validate the engine (offline, no network)
```bash
pip install pandas
python validation/korea_singapore_1998.py
```
Expected: `PASS - engine reproduces all 16 published indices.` The script also
writes `korea_singapore_diamonds.png`, which matches Figs 3–4 of the 1998 paper
(Korea's larger domestic diamond, Singapore's larger international diamond).

## Pull real data
```bash
pip install -r requirements.txt
export SUPABASE_URL=...  SUPABASE_SERVICE_KEY=...
python -m ddd.connectors          # demo WDI pull for KOR/SGP
```

Sources available to the ingestion layer:
- **WDI / WGI** via `fetch_wdi` (wbgapi) — the bulk of the open catalog.
- **Data360** via `fetch_data360` — World Bank's unified gateway to partner
  datasets (e.g. `WEF_GCI` historical 2007-2019, IMF, OECD, UN). Mostly CC BY
  4.0, so generally redistributable with attribution — a cheaper, open route to
  the historical WEF GCI than a WEF subscription.
- **UNCTAD FDI stock** via `fetch_unctad_fdi_stock` (template — confirm dataset id).
- **Anything else (Track B)** via `load_manual_csv` — point it at a downloaded
  UNCTAD bulk file or an IMD/WEF subscription export. ⚠️ Licensed sources
  (IMD/WEF subscriptions) are typically NOT redistributable; check terms before
  exposing raw values in a public deployment.

## Methodology notes
- **Normalization** defaults to `ratio_max` (top country = 100), reproducing the
  papers. Indicators that can be negative (e.g. WGI governance estimates) use
  `minmax` instead — set per indicator in the `indicator` table.
- **Polarity** `-` means lower-is-better (tariffs, export concentration, brain
  drain); the engine inverts these before normalizing.
- **Relativity**: scores are only meaningful within a single
  `{country set × indicator basket × vintage}` — that's what `run` versions.
```
