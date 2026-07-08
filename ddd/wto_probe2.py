"""
WTO probe #2 — tiny. Step 1 already confirmed the key, the indicator code
(ITS_MTV_AX), and the ISO3 mapping (reporters table has an `iso3A` field).

The only open question: the /data rows came back as all-None, which means the
JSON nests the datapoints under a key my parser didn't read. This dumps the RAW
structure of one small response so we can see exactly where the rows live.

Run:
    export WTO_API_KEY="your-key"          # same window
    python ddd/wto_probe2.py               # or wherever you saved it
"""
import os, sys, json, requests

KEY = os.environ.get("WTO_API_KEY")
if not KEY:
    sys.exit('Set WTO_API_KEY first:  export WTO_API_KEY="your-key"')

# small pull: one country (Brazil = 076), recent years, total merchandise
url = "https://api.wto.org/timeseries/v1/data"
params = {
    "i": "ITS_MTV_AX", "r": "076", "ps": "2022-2025",
    "fmt": "json", "mode": "full", "max": "20", "off": "0",
    "head": "H", "lang": "1", "meta": "false", "subscription-key": KEY,
}
r = requests.get(url, params=params, timeout=60)
print("HTTP", r.status_code)
data = r.json()

print("\nTOP-LEVEL TYPE:", type(data).__name__)
if isinstance(data, dict):
    print("TOP-LEVEL KEYS:", list(data.keys()))
    for k, v in data.items():
        kind = type(v).__name__
        n = len(v) if isinstance(v, (list, dict)) else ""
        print(f"  {k!r}: {kind} {n}")
        # if this value is a list of rows, show the first row verbatim
        if isinstance(v, list) and v and isinstance(v[0], dict):
            print(f"    -> FIRST ROW of {k!r}:")
            print("      ", json.dumps(v[0], ensure_ascii=False))
elif isinstance(data, list):
    print("IT'S A LIST. len:", len(data))
    if data:
        print("FIRST ROW:")
        print("  ", json.dumps(data[0], ensure_ascii=False))

# also dump the first 600 chars raw, so nothing is hidden
print("\nRAW (first 600 chars):")
print(r.text[:600])
