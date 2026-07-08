"""
WTO probe #3 — the goods-vs-(goods+services) seam check.

Your WDI history is exports/imports of goods AND services (% GDP). WTO ITS_MTV_AX
/ ITS_MTV_AM are merchandise (goods) ONLY. Before we relay WTO onto the WDI
criteria, we need to know how big the services share is, and whether it's stable
enough to rescale — otherwise splicing goods-only 2025 onto a goods+services
history creates a fake dip.

This pulls, for a spread of your panel countries, WTO merchandise exports+imports
for 2022-2025 and prints them so we can compare against the WDI levels you already
have. It writes NOTHING. Read-only.

Run:
    export WTO_API_KEY="your-key"
    python ddd/wto_probe3.py
"""
import os, sys, requests
KEY = os.environ.get("WTO_API_KEY")
if not KEY:
    sys.exit('Set WTO_API_KEY first:  export WTO_API_KEY="your-key"')

BASE = "https://api.wto.org/timeseries/v1/data"

# a spread: big trader, services-heavy, commodity, small open, emerging
# WTO numeric reporter codes: Brazil 076, India 356, USA 840, Singapore 702,
# Germany 276, Nigeria 566, South Africa 710, Mexico 484
TEST = {"076": "Brazil", "356": "India", "840": "USA", "702": "Singapore",
        "276": "Germany", "710": "South Africa", "484": "Mexico"}

def pull(indicator, rcode):
    r = requests.get(BASE, params={
        "i": indicator, "r": rcode, "ps": "2022-2025", "pc": "TO",
        "fmt": "json", "mode": "full", "max": "100", "subscription-key": KEY}, timeout=60)
    out = {}
    for row in r.json().get("Dataset", []):
        if row.get("ProductOrSectorCode") == "TO":
            out[int(row["Year"])] = row["Value"]
    return out

print(f"{'country':12} {'year':5} {'exports($M)':>14} {'imports($M)':>14} {'trade($M)':>14}")
print("-"*64)
for code, name in TEST.items():
    exp = pull("ITS_MTV_AX", code)   # merchandise exports
    imp = pull("ITS_MTV_AM", code)   # merchandise imports
    for y in (2022, 2023, 2024, 2025):
        e, i = exp.get(y), imp.get(y)
        t = (e + i) if (e is not None and i is not None) else None
        print(f"{name:12} {y:5} {('' if e is None else f'{e:,.0f}'):>14} "
              f"{('' if i is None else f'{i:,.0f}'):>14} "
              f"{('' if t is None else f'{t:,.0f}'):>14}")
    print()

print("NEXT: compare the 2022-2024 WTO merchandise trade above against your WDI")
print("trade %GDP for the same years (run the SQL below in Supabase) to size the")
print("goods-only vs goods+services gap.")
print("""
-- WDI exports & trade %GDP for the overlap years (run in Supabase):
select i.source_code, o.country_iso3, o.year, o.raw_value
from observation o join indicator i on i.id = o.indicator_id
where i.source_code in ('NE.EXP.GNFS.ZS','NE.TRD.GNFS.ZS')   -- exports %GDP, trade %GDP
  and o.country_iso3 in ('BRA','IND','USA','SGP','DEU','ZAF','MEX')
  and o.year between 2022 and 2024
order by i.source_code, o.country_iso3, o.year;
""")
