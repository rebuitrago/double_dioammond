"""
WTO probe #4 — commercial services trade: does it exist, reach 2025, cover the panel?

The merchandise seam check showed goods-share of trade ranges 0.56-0.95 across
countries, so a fixed rescale would lie. The honest fix is goods + SERVICES. This
probe (1) finds WTO's commercial-services exports/imports indicator codes from the
live /indicators list, (2) pulls a country spread for 2022-2025, (3) reports whether
2025 is present and how complete the panel coverage looks.

Read-only. Run:
    export WTO_API_KEY="your-key"
    python ddd/wto_probe4.py
"""
import os, sys, requests
KEY = os.environ.get("WTO_API_KEY")
if not KEY:
    sys.exit('Set WTO_API_KEY first:  export WTO_API_KEY="your-key"')

BASE = "https://api.wto.org/timeseries/v1"

def get(path, **p):
    p["subscription-key"] = KEY
    return requests.get(f"{BASE}/{path}", params=p, timeout=60)

print("="*70)
print("STEP 1 — find commercial-services trade indicator codes")
print("="*70)
r = get("indicators", i="all", t="all", pc="all", tp="all", frq="all", lang="1")
inds = r.json()
# commercial services trade value, annual: name contains 'commercial services' + value/annual
svc = [d for d in inds if "commercial services" in str(d.get("name","")).lower()
       and "annual" in str(d.get("name","")).lower()]
print(f"  commercial-services annual indicators ({len(svc)} found):")
for d in svc:
    print(f"    {d.get('code')!s:16} {str(d.get('name'))[:62]}")
# best guesses for exports / imports value codes
exp_code = next((d['code'] for d in svc if "export" in str(d.get('name','')).lower()
                 and "value" in str(d.get('name','')).lower()), None)
imp_code = next((d['code'] for d in svc if "import" in str(d.get('name','')).lower()
                 and "value" in str(d.get('name','')).lower()), None)
print(f"\n  -> services EXPORT value code: {exp_code}")
print(f"  -> services IMPORT value code: {imp_code}")

if not exp_code:
    print("\n  Could not auto-pick a services export code. Full list above —")
    print("  tell me which code is 'commercial services exports, annual, value'.")
    sys.exit(0)

print("\n" + "="*70)
print("STEP 2 — pull services exports+imports for a country spread, 2022-2025")
print("="*70)
TEST = {"076":"Brazil","356":"India","840":"USA","702":"Singapore",
        "276":"Germany","710":"South Africa","484":"Mexico"}
def pull(code, rcode):
    rr = get("data", i=code, r=rcode, ps="2022-2025", fmt="json",
             mode="full", max="200", lang="1", meta="false")
    out = {}
    for row in rr.json().get("Dataset", []):
        # services total: keep the aggregate row if a product/sector field exists
        pc = row.get("ProductOrSectorCode")
        if pc in (None, "", "TO", "S", "SOX", "200"):   # tolerate various 'total' codes
            out[int(row["Year"])] = row["Value"]
    return out

print(f"{'country':12} {'year':5} {'svc exp($M)':>13} {'svc imp($M)':>13}")
print("-"*46)
any2025 = False
for code, name in TEST.items():
    e = pull(exp_code, code)
    i = pull(imp_code, code) if imp_code else {}
    for y in (2022,2023,2024,2025):
        ev, iv = e.get(y), i.get(y)
        if y == 2025 and (ev is not None or iv is not None): any2025 = True
        print(f"{name:12} {y:5} {('' if ev is None else f'{ev:,.0f}'):>13} "
              f"{('' if iv is None else f'{iv:,.0f}'):>13}")
    print()

print("="*70)
print(f"2025 services data present for at least one country? {'YES' if any2025 else 'NO'}")
print("If YES -> we build goods+services (option a, the clean relay).")
print("If NO / sparse -> services lag; fall back to a labeled merchandise-only criterion.")
print("="*70)
