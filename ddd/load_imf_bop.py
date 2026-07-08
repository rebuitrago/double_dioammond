"""
IMF BOP loader (contract: PROJECT_KNOWLEDGE §9C + §14 IP-receipts criterion).

PART 1 — 2025 relay (run 8, unchanged):

    criterion                                   WDI source_code           corner
    ICT service exports (% of service exports)  BX.GSR.CCIS.ZS            R&S / connectivity
    Personal remittances received (% GDP)       BX.TRF.PWKR.DT.GD.ZS      Workers / intl labor
    FDI net inflows (% GDP)                     BX.KLT.DINV.WD.GD.ZS      Factor Conditions
    FDI net outflows (% GDP)                    BM.KLT.DINV.WD.GD.ZS      Factor Conditions

PART 2 — BOP-direct criterion #60 (v2.0, new):

    Charges for use of intellectual property, receipts (% service exports)
    source_code IMFBOP.IP_RECEIPTS_PCT_SVC, sub_factor 22
    (International entrepreneurship), sibling of #14 high-tech exports.

    numerator   = CD_T.SH.USD   (IP charges n.i.e., credit)
    denominator = CD_T.S.USD    (total services, credit — same as ICT)

    History 1996–2024 from finalized annual data -> value_type "actual",
    vintage "IMF BOP (direct)". 2025 via the §9C waterfall ->
    value_type "estimate", vintage "IMF BOP (direct, 2025 tier N)".
    Single source end to end: no relay seam, no derived-GDP dependency.

    Ground-truth gate (new construct, no DB comparator): the loader fetches
    WDI BX.GSR.ROYL.CD (IP receipts, US$) and BX.GSR.NFSV.CD (service
    exports, US$) from the World Bank v2 API for 2019–2024, computes the
    WDI-implied share, and compares it with the BOP-derived share on the
    same country-years. Median |delta| must be <= 1.0pp or nothing is
    written. A wrongly selected series cannot pass this quietly.

Series selection is by SERIES_CODE tokens ({ISO3}.{ENTRY}.{ITEM}.{UNIT}.{FREQ}),
pinned from probes of the actual export:

    remittances = CD_T.D752_S1W.USD (personal transfers, credit)
                + CD_T.D1.USD       (compensation of employees, credit)
    ICT         = CD_T.SI.USD  (telecom/computer/information services, credit)
    services    = CD_T.S.USD   (total services, credit; shared denominator)
    FDI in      = L_NIL_T.D_F.USD (direct investment TOTAL, net incurrence)
    FDI out     = A_NFA_T.D_F.USD (direct investment TOTAL, net acquisition)
    IP receipts = CD_T.SH.USD  (charges for use of intellectual property
                                n.i.e., credit — probed 2026-07-07)

Annualization waterfall (§9C, per country x series):
    tier 1: finalized annual 2025 -> use it
    tier 2: four quarters present -> sum
    tier 3: exactly three quarters -> 2024_annual x (sum 2025 Qs / same 2024 Qs)
    tier 4: fewer -> no 2025 value (country holds at 2024; nothing written)

GDP denominator (§9B, relay criteria only — IP uses no GDP):
    GDP2025 = GDP2024(NY.GDP.MKTP.CD)
    x (1 + growth2025/100)   [NY.GDP.MKTP.KD.ZG relay]
    x (1 + inflation2025/100)[EUROMONITOR.INFLATION]

Usage:
    export SUPABASE_URL=... SUPABASE_SECRET_KEY=...
    python -m ddd.load_imf_bop --csv "/path/to/bop.csv" --only ip --dry-run
    python -m ddd.load_imf_bop --csv "/path/to/bop.csv" --only ip
    python -m ddd.load_imf_bop --csv "/path/to/bop.csv"            # everything
"""
from __future__ import annotations
import argparse
import csv
import os
import statistics
import sys
from collections import defaultdict

BOP_RELAY_VERSION = "2.0"

# (ENTRY, ITEM, UNIT) -> internal series key
SERIES = {
    ("CD_T", "D752_S1W", "USD"): "remit_pt",
    ("CD_T", "D1", "USD"): "remit_coe",
    ("CD_T", "SI", "USD"): "ict_num",
    ("CD_T", "S", "USD"): "svc_total",
    ("L_NIL_T", "D_F", "USD"): "fdi_in",
    ("A_NFA_T", "D_F", "USD"): "fdi_out",
    ("CD_T", "SH", "USD"): "ip_num",
}

# series for which the full annual history is retained (BOP-direct criterion)
HIST_KEYS = {"ip_num", "svc_total"}
HIST_YEARS = list(range(1996, 2025))   # 2025 handled by the waterfall

TARGET_CODES = {
    "ict": "BX.GSR.CCIS.ZS",
    "remit": "BX.TRF.PWKR.DT.GD.ZS",
    "fdi_in": "BX.KLT.DINV.WD.GD.ZS",
    "fdi_out": "BM.KLT.DINV.WD.GD.ZS",
}
IP_CODE = "IMFBOP.IP_RECEIPTS_PCT_SVC"

GDP_CODE, GROWTH_CODE, INFL_CODE = ("NY.GDP.MKTP.CD",
                                    "NY.GDP.MKTP.KD.ZG",
                                    "EUROMONITOR.INFLATION")

# WDI comparator series for the IP ground-truth gate (verified 2026-07-07)
WDI_IP_CODE = "BX.GSR.ROYL.CD"      # IP receipts, current US$
WDI_SVC_CODE = "BX.GSR.NFSV.CD"     # service exports, current US$
GATE_YEARS = (2019, 2024)           # inclusive overlap window
GATE_TOL_PP = 1.0                   # median |delta| tolerance

QCOLS = {y: [f"{y}-Q{q}" for q in (1, 2, 3, 4)] for y in (2024, 2025)}


# ---------------------------------------------------------------------------
# pure parts (no I/O beyond the CSV stream) -- offline-testable
# ---------------------------------------------------------------------------
def _num(raw):
    if raw is None or raw in ("", ".", "..", "NA"):
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_bop(path: str, panel_iso3: set[str]):
    """Stream the wide CSV once; keep only the pinned series for panel
    countries. Returns (data, labels):
        data[series_key][iso3] = {"A2024","A2025","Q2024":[4],"Q2025":[4],
                                  "A_hist": {year: value}   (HIST_KEYS only)}
        labels[series_key] = INDICATOR text actually found (for the report)
    """
    data: dict = defaultdict(dict)
    labels: dict = {}
    with open(path, newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            parts = (row.get("SERIES_CODE") or "").split(".")
            if len(parts) != 5:
                continue
            iso3, entry, item, unit, freq = parts
            key = SERIES.get((entry, item, unit))
            if key is None or iso3 not in panel_iso3:
                continue
            if (row.get("SCALE") or "") != "Millions":
                continue
            slot = data[key].setdefault(iso3, {})
            if freq == "A":
                slot["A2024"] = _num(row.get("2024"))
                slot["A2025"] = _num(row.get("2025"))
                if key in HIST_KEYS:
                    slot["A_hist"] = {y: _num(row.get(str(y)))
                                      for y in HIST_YEARS}
            elif freq == "Q":
                slot["Q2024"] = [_num(row.get(c)) for c in QCOLS[2024]]
                slot["Q2025"] = [_num(row.get(c)) for c in QCOLS[2025]]
            labels.setdefault(key, row.get("INDICATOR") or "")
    return data, labels


def annualize(slot: dict):
    """§9C waterfall -> (value_millions_usd_2025, tier). tier 4 -> (None, 4)."""
    if slot.get("A2025") is not None:
        return slot["A2025"], 1
    q25 = slot.get("Q2025") or []
    present = [v for v in q25 if v is not None]
    if len(present) == 4:
        return sum(present), 2
    if len(present) == 3:
        a24 = slot.get("A2024")
        q24 = slot.get("Q2024") or [None] * 4
        idx = [i for i, v in enumerate(q25) if v is not None]
        base = [q24[i] for i in idx]
        if a24 is not None and all(b is not None for b in base) and sum(base) != 0:
            return a24 * (sum(present) / sum(base)), 3
    return None, 4


def build_2025(data: dict, gdp2025: dict):
    """Combine series -> per-criterion 2025 values (relay criteria).
    Returns rows: {criterion, iso3, value, tier}. gdp2025: iso3 -> USD."""
    rows = []
    countries = set()
    for key in ("ict_num", "svc_total", "remit_pt", "remit_coe",
                "fdi_in", "fdi_out"):
        countries |= set(data.get(key, {}).keys())
    for iso3 in sorted(countries):
        # ICT share: numerator and denominator each annualized; both required
        n, tn = annualize(data["ict_num"].get(iso3, {}))
        d, td = annualize(data["svc_total"].get(iso3, {}))
        if n is not None and d not in (None, 0):
            rows.append(dict(criterion="ict", iso3=iso3,
                             value=n / d * 100.0, tier=max(tn, td)))
        # remittances: personal transfers + compensation of employees
        pt, t1 = annualize(data["remit_pt"].get(iso3, {}))
        coe, t2 = annualize(data["remit_coe"].get(iso3, {}))
        g = gdp2025.get(iso3)
        if pt is not None and coe is not None and g:
            rows.append(dict(criterion="remit", iso3=iso3,
                             value=(pt + coe) * 1e6 / g * 100.0,
                             tier=max(t1, t2)))
        # FDI, full direct-investment category, per direction
        for key in ("fdi_in", "fdi_out"):
            v, t = annualize(data[key].get(iso3, {}))
            if v is not None and g:
                rows.append(dict(criterion=key, iso3=iso3,
                                 value=v * 1e6 / g * 100.0, tier=t))
    return rows


def build_2024_ground_truth(data: dict, gdp2024: dict):
    """Same constructs from BOP ANNUAL 2024 only, for the WDI comparison."""
    rows = []
    countries = set()
    for key in ("ict_num", "svc_total", "remit_pt", "remit_coe",
                "fdi_in", "fdi_out"):
        countries |= set(data.get(key, {}).keys())
    for iso3 in sorted(countries):
        g = gdp2024.get(iso3)
        n = data["ict_num"].get(iso3, {}).get("A2024")
        d = data["svc_total"].get(iso3, {}).get("A2024")
        if n is not None and d not in (None, 0):
            rows.append(("ict", iso3, n / d * 100.0))
        pt = data["remit_pt"].get(iso3, {}).get("A2024")
        coe = data["remit_coe"].get(iso3, {}).get("A2024")
        if pt is not None and coe is not None and g:
            rows.append(("remit", iso3, (pt + coe) * 1e6 / g * 100.0))
        for key in ("fdi_in", "fdi_out"):
            v = data[key].get(iso3, {}).get("A2024")
            if v is not None and g:
                rows.append((key, iso3, v * 1e6 / g * 100.0))
    return rows


def build_ip_rows(data: dict):
    """BOP-direct IP-receipts share, full panel history + 2025 waterfall.
    Returns rows: {iso3, year, value, tier} — tier None for history."""
    rows = []
    ip = data.get("ip_num", {})
    svc = data.get("svc_total", {})
    for iso3 in sorted(set(ip) & set(svc)):
        h_n = ip[iso3].get("A_hist", {})
        h_d = svc[iso3].get("A_hist", {})
        for y in HIST_YEARS:
            n, d = h_n.get(y), h_d.get(y)
            if n is not None and d not in (None, 0):
                rows.append(dict(iso3=iso3, year=y,
                                 value=n / d * 100.0, tier=None))
        n25, tn = annualize(ip[iso3])
        d25, td = annualize(svc[iso3])
        if n25 is not None and d25 not in (None, 0):
            rows.append(dict(iso3=iso3, year=2025,
                             value=n25 / d25 * 100.0, tier=max(tn, td)))
    return rows


# ---------------------------------------------------------------------------
# WDI comparator fetch (IP ground-truth gate)
# ---------------------------------------------------------------------------
def _fetch_wdi_series(code: str, y0: int, y1: int):
    """World Bank v2 API -> {(iso3, year): value}. Loud failure, no retries."""
    import httpx
    url = (f"https://api.worldbank.org/v2/country/all/indicator/{code}"
           f"?format=json&date={y0}:{y1}&per_page=20000")
    resp = httpx.get(url, timeout=120)
    resp.raise_for_status()
    body = resp.json()
    if not isinstance(body, list) or len(body) < 2 or body[1] is None:
        sys.exit(f"ABORT: WDI fetch for {code} returned no data block: "
                 f"{str(body)[:200]}")
    out = {}
    for r in body[1]:
        iso = (r.get("countryiso3code") or "").strip()
        val = r.get("value")
        try:
            yr = int(r.get("date"))
        except (TypeError, ValueError):
            continue
        if iso and val is not None:
            out[(iso, yr)] = float(val)
    return out


def ip_ground_truth_gate(data: dict, panel: set[str]):
    """Compare BOP-derived IP share with WDI-derived share, 2019-2024.
    Aborts on failure; returns (n, median, p90) on success."""
    y0, y1 = GATE_YEARS
    print(f"\nIP ground-truth gate (BOP share vs WDI "
          f"{WDI_IP_CODE}/{WDI_SVC_CODE}, {y0}-{y1}):")
    wdi_ip = _fetch_wdi_series(WDI_IP_CODE, y0, y1)
    wdi_svc = _fetch_wdi_series(WDI_SVC_CODE, y0, y1)
    print(f"  WDI fetched: {len(wdi_ip)} IP points, {len(wdi_svc)} svc points")

    deltas = []
    ip = data.get("ip_num", {})
    svc = data.get("svc_total", {})
    for iso3 in sorted(set(ip) & set(svc) & panel):
        h_n = ip[iso3].get("A_hist", {})
        h_d = svc[iso3].get("A_hist", {})
        for y in range(y0, y1 + 1):
            n, d = h_n.get(y), h_d.get(y)
            wn, wd = wdi_ip.get((iso3, y)), wdi_svc.get((iso3, y))
            if None in (n, wn, wd) or d in (None, 0) or wd == 0:
                continue
            bop_share = n / d * 100.0
            wdi_share = wn / wd * 100.0
            deltas.append(abs(bop_share - wdi_share))
    if len(deltas) < 50:
        sys.exit(f"ABORT: only {len(deltas)} overlap points for the IP gate; "
                 f"too few to validate. Paste this output back for review.")
    med = statistics.median(deltas)
    p90 = statistics.quantiles(deltas, n=10)[8]
    flag = "OK " if med <= GATE_TOL_PP else "FAIL"
    print(f"  {len(deltas)} country-years, median |delta| = {med:.2f}pp, "
          f"p90 = {p90:.2f}pp  [{flag}]")
    if med > GATE_TOL_PP:
        sys.exit("ABORT: IP ground-truth gate failed; nothing written. "
                 "Paste this output back for review.")
    return len(deltas), med, p90


# ---------------------------------------------------------------------------
# Supabase I/O
# ---------------------------------------------------------------------------
def _client():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"],
                         os.environ["SUPABASE_SECRET_KEY"])


def _read_all(client, table, select, filters=None):
    rows, start, page = [], 0, 1000
    while True:
        q = client.table(table).select(select).range(start, start + page - 1)
        for col, vals in (filters or {}).items():
            q = q.in_(col, vals)
        resp = q.execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page
    return rows


def _obs_map(client, indicator_id, year):
    """iso3 -> raw_value for one indicator-year."""
    rows = _read_all(client, "observation",
                     "country_iso3,year,raw_value",
                     {"indicator_id": [indicator_id], "year": [year]})
    return {r["country_iso3"]: r["raw_value"] for r in rows
            if r.get("raw_value") is not None}


# ---------------------------------------------------------------------------
# run parts
# ---------------------------------------------------------------------------
def run_relay(client, data, labels, id_of, gdp24, gdp25, dry_run):
    """PART 1 — the run-8 relay, byte-identical logic to v1.0."""
    svc_label = labels.get("svc_total", "").lower()
    if "servic" not in svc_label:
        sys.exit(f"ABORT: total-services denominator label looks wrong: "
                 f"'{labels.get('svc_total')}'")

    print("\nGround-truth gate (BOP-derived 2024 vs WDI 2024 in DB):")
    gt = build_2024_ground_truth(data, gdp24)
    ok = True
    for crit, code in TARGET_CODES.items():
        wdi = _obs_map(client, id_of[code], 2024)
        deltas = [abs(v - wdi[iso]) for c, iso, v in gt
                  if c == crit and iso in wdi]
        if not deltas:
            print(f"  {crit:8s} no overlap with WDI 2024 -- cannot validate")
            ok = False
            continue
        med = statistics.median(deltas)
        tol = 2.0 if crit == "ict" else 1.5   # pp tolerance, generous but honest
        flag = "OK " if med <= tol else "FAIL"
        if med > tol:
            ok = False
        print(f"  {crit:8s} {len(deltas):3d} countries, median |delta| = "
              f"{med:.2f}pp  [{flag}]")
    if not ok:
        sys.exit("ABORT: ground-truth gate failed; nothing written. "
                 "Paste this output back for review.")

    rows = build_2025(data, gdp25)
    print("\n2025 relay preview:")
    for crit, code in TARGET_CODES.items():
        sub = [r for r in rows if r["criterion"] == crit]
        tiers = {t: sum(1 for r in sub if r["tier"] == t) for t in (1, 2, 3)}
        print(f"  {crit:8s} {len(sub):3d} countries "
              f"(tier1 {tiers[1]}, tier2 {tiers[2]}, tier3 {tiers[3]})")
        sample = sorted(sub, key=lambda r: r["iso3"])[:3]
        for r in sample:
            print(f"           {r['iso3']}  {r['value']:.2f}  (tier {r['tier']})")

    payload = []
    for crit, code in TARGET_CODES.items():
        iid = id_of[code]
        existing = _read_all(client, "observation",
                             "country_iso3,source_vintage",
                             {"indicator_id": [iid], "year": [2025]})
        foreign = {r["country_iso3"] for r in existing
                   if "IMF BOP" not in (r.get("source_vintage") or "")}
        for r in rows:
            if r["criterion"] != crit or r["iso3"] in foreign:
                continue
            payload.append({
                "indicator_id": iid,
                "country_iso3": r["iso3"],
                "year": 2025,
                "raw_value": round(float(r["value"]), 6),
                "value_type": "estimate",
                "source_vintage": f"IMF BOP 2025 (relay tier {r['tier']})",
            })

    print(f"\nrelay rows to write: {len(payload)}")
    if dry_run:
        print("DRY RUN: relay writes skipped.")
        return
    for i in range(0, len(payload), 500):
        client.table("observation").upsert(
            payload[i:i + 500],
            on_conflict="indicator_id,country_iso3,year").execute()
    print(f"WROTE {len(payload)} relay observations.")


def run_ip(client, data, labels, panel, dry_run):
    """PART 2 — BOP-direct criterion #60, history + 2025."""
    ip_label = labels.get("ip_num", "")
    n_found = len(data.get("ip_num", {}))
    print(f"\nIP-receipts series: {n_found} panel countries | "
          f"{ip_label or 'NOT FOUND'}")
    if n_found == 0:
        sys.exit("ABORT: IP-receipts series (CD_T.SH.USD) not found; "
                 "selection tokens need review.")
    if "intellectual property" not in ip_label.lower():
        sys.exit(f"ABORT: IP numerator label looks wrong: '{ip_label}'")

    ind = _read_all(client, "indicator", "id,source_code,sub_factor_id",
                    {"source_code": [IP_CODE]})
    if not ind:
        sys.exit(f"ABORT: indicator '{IP_CODE}' not in DB. "
                 "Run db/migration_03_ip_receipts.sql first.")
    iid = ind[0]["id"]
    print(f"criterion row found: id {iid}, sub_factor {ind[0]['sub_factor_id']}")

    ip_ground_truth_gate(data, panel)

    rows = build_ip_rows(data)
    hist = [r for r in rows if r["year"] < 2025]
    y25 = [r for r in rows if r["year"] == 2025]
    tiers = {t: sum(1 for r in y25 if r["tier"] == t) for t in (1, 2, 3)}
    print(f"\nIP-receipts build: {len(hist)} history rows "
          f"({len({r['iso3'] for r in hist})} countries, "
          f"{min((r['year'] for r in hist), default='-')}-"
          f"{max((r['year'] for r in hist), default='-')}), "
          f"{len(y25)} rows for 2025 "
          f"(tier1 {tiers[1]}, tier2 {tiers[2]}, tier3 {tiers[3]})")
    top = sorted(y25, key=lambda r: -r["value"])[:5]
    print("  top-5 2025 (expect IP-domicile and innovation economies):")
    for r in top:
        print(f"    {r['iso3']}  {r['value']:.2f}%  (tier {r['tier']})")

    existing = _read_all(client, "observation", "country_iso3,year,source_vintage",
                         {"indicator_id": [iid]})
    foreign = {(r["country_iso3"], r["year"]) for r in existing
               if "IMF BOP" not in (r.get("source_vintage") or "")}
    if foreign:
        print(f"  guard: {len(foreign)} non-BOP rows on this indicator "
              "will not be touched")

    payload = []
    for r in rows:
        if (r["iso3"], r["year"]) in foreign:
            continue
        if r["year"] < 2025:
            vt, vin = "actual", "IMF BOP (direct)"
        else:
            vt, vin = "estimate", f"IMF BOP (direct, 2025 tier {r['tier']})"
        payload.append({
            "indicator_id": iid,
            "country_iso3": r["iso3"],
            "year": r["year"],
            "raw_value": round(float(r["value"]), 6),
            "value_type": vt,
            "source_vintage": vin,
        })

    print(f"\nIP rows to write: {len(payload)}")
    if dry_run:
        print("DRY RUN: IP writes skipped.")
        return
    for i in range(0, len(payload), 500):
        client.table("observation").upsert(
            payload[i:i + 500],
            on_conflict="indicator_id,country_iso3,year").execute()
    print(f"WROTE {len(payload)} IP-receipts observations.")


def main():
    p = argparse.ArgumentParser(description="IMF BOP loader (relay + direct)")
    p.add_argument("--csv", required=True, help="path to the IMF BOP wide CSV")
    p.add_argument("--only", choices=("all", "relay", "ip"), default="all",
                   help="which part to run (default: all)")
    p.add_argument("--dry-run", action="store_true",
                   help="compute + report; write nothing")
    a = p.parse_args()

    client = _client()

    codes = list(TARGET_CODES.values()) + [GDP_CODE, GROWTH_CODE, INFL_CODE]
    ind = _read_all(client, "indicator", "id,source_code",
                    {"source_code": codes})
    id_of = {r["source_code"]: r["id"] for r in ind}
    missing = [c for c in codes if c not in id_of]
    if missing:
        sys.exit(f"ABORT: indicator codes not found in DB: {missing}")

    panel = {r["iso3"] for r in _read_all(client, "country", "iso3")}
    print(f"panel: {len(panel)} countries")

    gdp24 = _obs_map(client, id_of[GDP_CODE], 2024)
    gdp25 = {}
    if a.only in ("all", "relay"):
        growth25 = _obs_map(client, id_of[GROWTH_CODE], 2025)
        infl25 = _obs_map(client, id_of[INFL_CODE], 2025)
        gdp25 = {c: gdp24[c] * (1 + growth25[c] / 100) * (1 + infl25[c] / 100)
                 for c in gdp24 if c in growth25 and c in infl25}
        print(f"GDP denominator: 2024 GDP for {len(gdp24)}, "
              f"derived 2025 for {len(gdp25)}")

    print("streaming BOP CSV ...")
    data, labels = parse_bop(a.csv, panel)
    print("series found (exact INDICATOR labels):")
    keys = ("remit_pt", "remit_coe", "ict_num", "svc_total",
            "fdi_in", "fdi_out", "ip_num")
    for key in keys:
        n = len(data.get(key, {}))
        print(f"  {key:10s} {n:3d} panel countries | {labels.get(key, 'NOT FOUND')}")
        needed = (a.only in ("all", "relay")) or key in HIST_KEYS
        if n == 0 and needed:
            sys.exit(f"ABORT: series {key} not found; selection tokens need review.")

    if a.only in ("all", "relay"):
        run_relay(client, data, labels, id_of, gdp24, gdp25, a.dry_run)
    if a.only in ("all", "ip"):
        run_ip(client, data, labels, panel, a.dry_run)


if __name__ == "__main__":
    main()
