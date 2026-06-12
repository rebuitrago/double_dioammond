"""
Ingest job: pull active automated (Track A) indicators into `observation`.

Covers WDI/WGI via wbgapi (the bulk of the catalog). data360 and UNCTAD have
their own fetchers in connectors.py; wire them in here the same way once you've
confirmed their codes. Manual sources use load_manual_csv separately.

Requires server-side credentials (secret key):
    SUPABASE_URL, SUPABASE_SECRET_KEY
Country list comes from the `country` table; seed it first (see SETUP.md).

Usage:
    python -m ddd.ingest --start 2010 --end 2023
"""

from __future__ import annotations
import os
import argparse
import pandas as pd

from ddd.connectors import fetch_wdi, attach_indicator_ids, upsert_observations


def _client():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"],
                         os.environ["SUPABASE_SECRET_KEY"])


def _read_all(client, table, select="*"):
    rows, start, page = [], 0, 1000
    while True:
        resp = client.table(table).select(select).range(start, start + page - 1).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page
    return pd.DataFrame(rows)


def ingest(start: int, end: int, vintage: str | None = None) -> int:
    client = _client()

    indicators = _read_all(client, "indicator", "id,source,source_code,active")
    indicators = indicators[(indicators["active"]) &
                            (indicators["source"].isin(["WDI", "WGI"])) &
                            (indicators["source_code"].notna())]
    countries = _read_all(client, "country", "iso3")["iso3"].tolist()
    if not countries:
        raise RuntimeError("No countries in `country` table — seed it first (SETUP.md).")
    if indicators.empty:
        raise RuntimeError("No active WDI/WGI indicators found.")

    codes = indicators["source_code"].tolist()
    code_to_id = dict(zip(indicators["source_code"], indicators["id"]))
    vintage = vintage or f"WDI {pd.Timestamp.today():%Y-%m}"

    print(f"Fetching {len(codes)} indicators x {len(countries)} countries, {start}-{end}...")
    long = fetch_wdi(codes, countries, start, end)
    rows = attach_indicator_ids(long, code_to_id, vintage)
    n = upsert_observations(rows)
    print(f"Upserted {n} observations (vintage: {vintage}).")
    return n


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="DDD ingest job (WDI/WGI)")
    p.add_argument("--start", type=int, default=2010)
    p.add_argument("--end", type=int, default=pd.Timestamp.today().year - 1)
    p.add_argument("--vintage")
    a = p.parse_args()
    ingest(a.start, a.end, a.vintage)
