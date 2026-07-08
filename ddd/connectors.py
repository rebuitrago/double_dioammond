"""
Data connectors for the DDD platform.

Track A (automated) sources:
  * World Bank WDI / WGI  -> via the `wbgapi` package (clean, reliable)
  * World Bank Data360    -> unified gateway to many partner datasets
                             (WEF GCI historical, IMF, OECD, UN, ...). Mostly
                             CC BY 4.0, so generally redistributable.
  * UNCTAD FDI stock      -> via UNCTAD's data API (needed for the
                             international-connectivity grouping variable)

Track B (manual/curated):
  * load_manual_csv       -> any downloaded export (UNCTAD bulk, IMD/WEF
                             subscription files, hand-built CSVs).

Each fetcher returns a tidy long DataFrame with columns:
    source_code, country_iso3, year, raw_value
which maps 1:1 onto the `observation` table once you attach indicator_id.

Live network calls are intentionally isolated in the fetch_* functions so the
scoring engine and tests stay fully offline and deterministic.

Install:  pip install wbgapi requests pandas supabase
"""

from __future__ import annotations
import os
import pandas as pd

# ---------------------------------------------------------------------------
# World Bank WDI / WGI
# ---------------------------------------------------------------------------
def fetch_wdi(source_codes: list[str],
              countries: list[str],
              start: int,
              end: int) -> pd.DataFrame:
    """Pull WDI/WGI series into a tidy long frame.

    source_codes : e.g. ['NY.GDP.MKTP.CD', 'GE.EST']
    countries    : ISO3 codes, e.g. ['KOR', 'SGP']
    Returns columns: source_code, country_iso3, year, raw_value
    """
    import wbgapi as wb  # imported lazily so offline tests don't need it

    # wb.data.DataFrame returns a multi-index frame; we melt it to long form.
    raw = wb.data.DataFrame(
        source_codes, countries, time=range(start, end + 1),
        labels=False, skipBlanks=False, columns="series",
    )
    raw = raw.reset_index()  # economy, time, <one column per series>
    long = raw.melt(id_vars=["economy", "time"],
                    var_name="source_code", value_name="raw_value")
    long = long.rename(columns={"economy": "country_iso3"})
    # wbgapi yields time like 'YR2020'; normalize to int year
    long["year"] = (long["time"].astype(str)
                    .str.replace("YR", "", regex=False).astype(int))
    long = long.drop(columns=["time"])
    long["raw_value"] = pd.to_numeric(long["raw_value"], errors="coerce")
    return long[["source_code", "country_iso3", "year", "raw_value"]]


# ---------------------------------------------------------------------------
# World Bank Data360  (unified gateway: WEF GCI historical, IMF, OECD, UN, ...)
# ---------------------------------------------------------------------------
DATA360_BASE = "https://data360api.worldbank.org"

def fetch_data360(database_id: str,
                  indicator_id: str,
                  countries: list[str],
                  start: int,
                  end: int,
                  base_url: str = DATA360_BASE) -> pd.DataFrame:
    """Pull one indicator from a Data360 database into a tidy long frame.

    database_id  : e.g. 'WEF_GCI' (WEF Global Competitiveness Index, 2007-2019),
                   'WB_WDI', 'IMF_WEO', etc. See the `data360://databases` list.
    indicator_id : the indicator code within that database.
    countries    : ISO3 codes (Data360 calls this REF_AREA).

    Returns columns: source_code, country_iso3, year, raw_value
    where source_code = '{database_id}:{indicator_id}'.

    NOTE: Data360 is in beta. The data path and parameter names below follow the
    documented search -> get-data pattern (DATABASE_ID / INDICATOR / REF_AREA /
    time filters), but confirm them against https://data360.worldbank.org/en/api
    or the reference client at github.com/worldbank/data360-mcp. The response
    parser is deliberately tolerant of field-name variants so a minor schema
    change won't break ingestion.
    """
    import requests

    rows = []
    for iso in countries:
        params = {
            "DATABASE_ID": database_id,
            "INDICATOR": indicator_id,
            "REF_AREA": iso,
            "timePeriodFrom": start,
            "timePeriodTo": end,
        }
        try:
            resp = requests.get(f"{base_url}/data360/data",
                                params=params, timeout=60)
            resp.raise_for_status()
            payload = resp.json()
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(
                f"Data360 fetch failed for {database_id}:{indicator_id}/{iso} "
                f"({e}). Verify endpoint/params at "
                "https://data360.worldbank.org/en/api"
            )

        # observations live under 'value' or 'data' depending on the release
        records = payload.get("value") or payload.get("data") or []
        for rec in records:
            low = {k.lower(): v for k, v in rec.items()}
            val = low.get("obs_value", low.get("value"))
            yr = low.get("time_period", low.get("year"))
            ref = low.get("ref_area", iso)
            if val is None or yr is None:
                continue
            rows.append((f"{database_id}:{indicator_id}", ref,
                         int(str(yr)[:4]), pd.to_numeric(val, errors="coerce")))

    out = pd.DataFrame(rows, columns=["source_code", "country_iso3",
                                      "year", "raw_value"])
    return out


# ---------------------------------------------------------------------------
# UNCTAD FDI stock  (inward + outward, used for the connectivity grouping)
# ---------------------------------------------------------------------------
UNCTAD_FDI_DATASET = "US_FdiFlowsStock"   # verify dataset id at unctadstat.unctad.org

def fetch_unctad_fdi_stock(countries: list[str],
                           start: int,
                           end: int,
                           dataset: str = UNCTAD_FDI_DATASET) -> pd.DataFrame:
    """Best-effort UNCTAD FDI *stock* fetch.

    UNCTAD's API is less uniform than the World Bank's; dataset identifiers and
    dimension names change between releases, so treat this as a template:
    confirm the dataset code and the inward/outward dimension labels against
    the current UNCTADstat portal, then adjust the parsing below.

    Returns columns: source_code, country_iso3, year, raw_value
    where source_code is 'UNCTAD.FDI.STOCK.IN' / '...OUT'.
    """
    import requests

    base = "https://unctadstat-api.unctad.org/bulk/v1"
    url = f"{base}/{dataset}/csv"  # bulk CSV; some releases use /data
    try:
        df = pd.read_csv(url)
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"UNCTAD fetch failed ({e}). Verify dataset id '{dataset}' and "
            "endpoint at https://unctadstat.unctad.org. As a fallback, load "
            "the FDI-stock CSV manually (Track B) into `observation`."
        )

    # The exact column names depend on the release; map the common ones.
    colmap = {c.lower(): c for c in df.columns}
    iso = colmap.get("economy_iso3") or colmap.get("iso3") or "Economy"
    yr  = colmap.get("year") or colmap.get("period")
    direction = colmap.get("direction") or colmap.get("flow")
    value = colmap.get("value") or colmap.get("us_dollars_at_current_prices")

    df = df[df[iso].isin(countries) & df[yr].between(start, end)]
    df = df.assign(
        source_code=df[direction].astype(str).str.lower().map(
            lambda d: "UNCTAD.FDI.STOCK.IN" if "in" in d else "UNCTAD.FDI.STOCK.OUT"),
        country_iso3=df[iso], year=df[yr].astype(int),
        raw_value=pd.to_numeric(df[value], errors="coerce"),
    )
    return df[["source_code", "country_iso3", "year", "raw_value"]]


# ---------------------------------------------------------------------------
# Track B: manual / curated CSV loader
# ---------------------------------------------------------------------------
def load_manual_csv(path: str,
                    indicator_id: int,
                    country_col: str,
                    year_col: str,
                    value_col: str,
                    vintage: str,
                    iso3_map: dict[str, str] | None = None) -> list[dict]:
    """Turn a downloaded export (UNCTAD bulk, IMD/WEF subscription file, or a
    hand-built CSV) directly into observation rows for ONE indicator.

    indicator_id : the target row's id from the `indicator` table.
    *_col        : column names in the source CSV.
    vintage      : provenance label, e.g. 'IMD WCY 2025' or 'UNCTAD 2025 bulk'.
    iso3_map     : optional {source_country_label -> ISO3} if the file doesn't
                   already use ISO3 codes (e.g. {'Korea, Rep.': 'KOR'}).

    Returns rows ready for upsert_observations(). Rows with missing values are
    skipped. Licensed data (IMD/WEF): check redistribution terms before exposing
    raw values in a public deployment.
    """
    df = pd.read_csv(path)
    rows = []
    for r in df.itertuples(index=False):
        rec = r._asdict()
        country = rec[country_col]
        iso3 = (iso3_map or {}).get(country, country)
        value = rec[value_col]
        if pd.isna(value):
            continue
        rows.append({
            "indicator_id": indicator_id,
            "country_iso3": str(iso3),
            "year": int(rec[year_col]),
            "raw_value": float(value),
            "source_vintage": vintage,
        })
    return rows


# ---------------------------------------------------------------------------
# Map fetched rows -> observation rows -> Supabase upsert
# ---------------------------------------------------------------------------
def attach_indicator_ids(long: pd.DataFrame,
                         code_to_indicator_id: dict[str, int],
                         vintage: str) -> list[dict]:
    """Turn a tidy frame into observation-table dicts ready for upsert.

    code_to_indicator_id : {'NY.GDP.MKTP.CD': 12, ...}  (read once from the
                            `indicator` table: select id, source_code)
    Rows whose source_code isn't in the map are dropped (indicator not active).

    If the frame has a `value_type` column ('actual'/'estimate'/'forecast'),
    it is carried through to the observation row; otherwise the database default
    ('actual') applies. This keeps WDI/V-Dem frames (no value_type) unchanged
    while letting forecast-bearing sources (Euromonitor, EIU, WEO) set the flag.
    """
    has_value_type = "value_type" in long.columns
    rows = []
    for r in long.itertuples(index=False):
        ind_id = code_to_indicator_id.get(r.source_code)
        if ind_id is None or pd.isna(r.raw_value):
            continue
        row = {
            "indicator_id": ind_id,
            "country_iso3": r.country_iso3,
            "year": int(r.year),
            "raw_value": float(r.raw_value),
            "source_vintage": vintage,
        }
        if has_value_type and pd.notna(r.value_type):
            row["value_type"] = r.value_type
        rows.append(row)
    return rows


def upsert_observations(rows: list[dict], batch: int = 500) -> int:
    """Upsert observation rows into Supabase. Requires env:
        SUPABASE_URL  and  the server-side secret key.
    The secret key may be named either SUPABASE_SERVICE_KEY or
    SUPABASE_SECRET_KEY — both are accepted so the two scripts stay consistent.
    Uses the unique (indicator_id, country_iso3, year) constraint.
    """
    from supabase import create_client
    secret = os.environ.get("SUPABASE_SERVICE_KEY") or os.environ.get("SUPABASE_SECRET_KEY")
    if not secret:
        raise RuntimeError(
            "Set the server-side secret key: SUPABASE_SERVICE_KEY "
            "(or SUPABASE_SECRET_KEY)."
        )
    client = create_client(os.environ["SUPABASE_URL"], secret)
    n = 0
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        client.table("observation").upsert(
            chunk, on_conflict="indicator_id,country_iso3,year").execute()
        n += len(chunk)
    return n


if __name__ == "__main__":
    # Demo: pull a handful of WDI series for two countries and print the shape.
    # (Runs only where the World Bank API is reachable.)
    codes = ["NY.GDP.MKTP.CD", "NE.EXP.GNFS.ZS", "BX.KLT.DINV.WD.GD.ZS"]
    df = fetch_wdi(codes, ["KOR", "SGP"], 2018, 2022)
    print(df.head(12).to_string(index=False))
    print(f"\n{len(df)} rows across {df.source_code.nunique()} indicators.")
