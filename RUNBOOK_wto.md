# Runbook — WTO 2025 trade relay

This adds genuine **2025 international data** (Exports %GDP and Trade %GDP) to your
platform, pulled live from the WTO Timeseries API and attached onto your existing
WDI trade criteria. After this, the 2025 international (red) diamond fills in for
the countries that have all the needed inputs.

**What changed:** one file — `ddd/load_datasets.py`. A new `load_wto_trade()` step
runs inside your normal load, right after the relays.

**Time:** ~5 minutes. **Writes to DB:** only on the real run (step 4), not the dry run.

---

## Before you start — two prerequisites

1. **Your WTO key must be set in the terminal.** Check (this prints yes/no without
   showing the key):
   ```
   [ -n "$WTO_API_KEY" ] && echo "key is set" || echo "key NOT set"
   ```
   If it says NOT set:
   ```
   export WTO_API_KEY="your-key"
   ```
   (Use the regenerated key. `export` lasts only for this terminal window.)

2. **Your environment must be active** (same as every load):
   ```
   source venv/bin/activate
   export SUPABASE_URL="...your url..."
   export SUPABASE_SECRET_KEY="sb_secret_...your secret key..."
   export SUPABASE_SERVICE_KEY="sb_secret_...same secret key..."
   ```

---

## Step 1 — back up the file you're about to replace

```
cp ddd/load_datasets.py ddd/load_datasets_BEFORE_wto.py
```
(If anything looks wrong later, restore with
`cp ddd/load_datasets_BEFORE_wto.py ddd/load_datasets.py`.)

## Step 2 — put the new file in place

Download `load_datasets.py` (presented in chat) to your Downloads, then:
```
cp ~/Downloads/load_datasets.py ddd/load_datasets.py
```

## Step 3 — DRY RUN (writes nothing — this is the real test)

```
python -m ddd.load_datasets --dry-run
```

This now fetches WTO live, reads your GDP/growth/inflation, computes the 2025
ratios, and prints what it *would* write — without touching the database.

**What you should see** (numbers will vary, shape is what matters):

```
*** DRY RUN — reading and parsing only, no writes ***
Loading Track-B files into Supabase (60 countries in panel)...
  ... (the usual V-Dem / Euromonitor / EIU / relay lines) ...
    WTO 2024 check: exports%GDP vs WDI actual — median |Δ| 0.3X pp over ~45 countries (small = construction matches WDI)
  + WTO trade relay: 9X rows  [2025 Exports%GDP + Trade%GDP]  ~45 countries with full inputs; X dropped (missing 2024 GDP / 2025 growth / 2025 inflation)
Done. Would upsert NNNNN observations.
```

**The two lines that matter:**
- **`WTO 2024 check ... median |Δ| 0.3-something pp`** — this is the built-in
  honesty test. It rebuilds 2024 from WTO and compares to WDI's *actual* 2024
  figure. A small gap (under ~1pp) means the construction is faithful. If this
  number is large (say >3pp), stop and tell me — something's off.
- **`WTO trade relay: ~90 rows, ~45 countries`** — roughly two rows per country
  (exports + trade). ~45 countries is expected (not all 60 — only those with WTO
  trade *and* 2024 GDP *and* 2025 growth *and* 2025 inflation). The "dropped"
  count is the countries missing one of those pieces.

**If you instead see** `! WTO: WTO_API_KEY not set` → do prerequisite 1 and re-run.
**If you see** `! WTO: fetch failed ...` → it prints the reason (usually network
or key); the rest of the load still completes. Tell me the message.

## Step 4 — REAL RUN (writes to the database)

Only once the dry run looks right:
```
python -m ddd.load_datasets
```
Same output, but the last line says **`Upserted NNNNN observations.`** and the WTO
line writes for real. This is **safe to re-run** — the relay only fills 2025
(beyond WDI's 2024 frontier) and overwrites its own prior 2025 rows, so running it
twice changes nothing.

## Step 5 — re-score so the new 2025 data flows into the diamonds

```
python -m ddd.score_run --scoring-method percentile --label "wave2 + WTO 2025 trade"
```
(Your existing re-score command — this recomputes scores including the new 2025
international values.)

## Step 6 — look at it

```
streamlit run app.py
```
Set the year to **2025** and pick a country with full inputs (Brazil, Germany,
India, USA, Mexico are safe bets). The red international diamond should now show
the Exports and Trade corners for 2025 instead of collapsing. Countries without
WTO/GDP inputs will still be thin for 2025 — that's expected and honest.

---

## What this did, in one paragraph (for your notes)

For 2025, where WDI trade data doesn't exist yet, the platform now pulls total
**goods + services** exports and imports from the WTO Timeseries API, divides by a
**2025 nominal GDP** derived from 2024 GDP grown by the (already-loaded) 2025 real
growth and inflation, and writes the resulting Exports %GDP and Trade %GDP as a
gap-fill **relay** onto the WDI criteria — tagged `estimate`, vintage
"WTO 2026 + derived GDP (relay)". The construction is validated each run against
WDI's actual 2024 figures (the "WTO 2024 check" line). Coverage is partial by
design; the coverage flag marks which countries have it.
