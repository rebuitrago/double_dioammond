"""Probe the IMF BOP wide CSV: list the exact series definitions relevant to
the four DDD criteria, plus country labels. Streams the file, writes results
to probe_bop_results.txt next to this script. Read-only, touches nothing.

Usage:
    python probe_bop.py "/full/path/to/the/BOP/file.csv"
"""
import csv
import re
import sys

if len(sys.argv) != 2:
    sys.exit("Usage: python probe_bop.py \"/path/to/bop.csv\"")
path = sys.argv[1]

# columns that define a series (besides country)
KEY = ["INDICATOR", "BOP_ACCOUNTING_ENTRY", "ACCOUNTING_ENTRY", "FUNCTIONAL_CAT",
       "INT_ACC_ITEM", "INSTR_ASSET", "UNIT", "FREQUENCY", "SCALE"]

# anything plausibly related to the four criteria
pat = re.compile(r"personal transfer|compensation of employ|remittanc|"
                 r"telecommunic|computer|information serv|"
                 r"direct invest|"
                 r"^services$|total services|services.*credit",
                 re.IGNORECASE)

seen = {}          # series definition -> (example SERIES_CODE, row count)
countries = set()
n_rows = 0

with open(path, newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    for row in reader:
        n_rows += 1
        countries.add(row.get("COUNTRY", ""))
        blob = " | ".join([row.get("INDICATOR", "") or "",
                           row.get("SERIES_NAME", "") or "",
                           row.get("INT_ACC_ITEM", "") or "",
                           row.get("FUNCTIONAL_CAT", "") or ""])
        if pat.search(blob):
            k = tuple((row.get(c, "") or "") for c in KEY)
            if k in seen:
                seen[k][1] += 1
            else:
                seen[k] = [row.get("SERIES_CODE", ""), 1]

with open("probe_bop_results.txt", "w", encoding="utf-8") as out:
    out.write(f"total rows scanned: {n_rows}\n")
    out.write(f"distinct countries: {len(countries)}\n")
    out.write("country sample: " + "; ".join(sorted(c for c in countries if c)[:15]) + "\n")
    out.write(f"\ncandidate series definitions: {len(seen)}\n")
    out.write("columns: " + " | ".join(KEY) + " || example SERIES_CODE || n_countries\n")
    out.write("-" * 100 + "\n")
    for k, (code, n) in sorted(seen.items()):
        out.write(" | ".join(x if x else "." for x in k) + f" || {code} || {n}\n")

print(f"done: {n_rows} rows scanned, {len(seen)} candidate series definitions")
print("results written to probe_bop_results.txt (send that file back)")
