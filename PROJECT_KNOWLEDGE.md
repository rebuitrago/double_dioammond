# DDD Competitiveness Platform — Project Knowledge

*A living reference for the Dual Double Diamond (DDD) competitiveness platform.
Add this file to the Claude Project's knowledge base so every future
conversation starts with the full picture.*

---

## 1. What this project is

A web platform that analyzes the **competitiveness of emerging economies** using
the **Dual Double Diamond (DDD)** model, built for a **research and policy**
audience. The goal is not to display historical data but to **generate insights**
— readable diamonds and rankings that a non-specialist (a policymaker, a
discussant) can interpret at a glance.

The owner is an academic domain expert but **non-technical on tooling**, so all
operational steps must be plain, explicit, and copy-paste-able. Instructions
should never assume coding knowledge.

---

## 2. The model

**Theory lineage:** Porter's single diamond → Rugman & D'Cruz (1993) double
diamond → Moon, Rugman & Verbeke (1998) generalized double diamond → Cho, Moon &
Kim (2006–2009) **Dual Double Diamond**. The source papers are in the project
knowledge.

**Structure:** two factors × two contexts, each a four-cornered diamond:

- **Physical determinants:** Factor Conditions; Demand Conditions; Related &
  Supporting Industries; Firm Strategy, Structure & Rivalry.
- **Human determinants:** Workers; Politicians & Bureaucrats; Entrepreneurs;
  Professionals.
- Each of the 8 determinants exists in a **domestic** and an **international**
  context → 16 cells. The international diamond is drawn as domestic + international.

**Two-level (IPS) hierarchy** adopted for academic fidelity, mirroring the IPS
National Competitiveness Research structure Cho et al. used:

```
factor → determinant → sub-factor → criterion (indicator)
```

Criteria are averaged **within a sub-factor**, then sub-factors are averaged
**within a determinant** — equal weight per sub-factor. This prevents a
data-rich sub-factor from dominating a sparse one, which is the defensible
weighting reviewers expect. (The published IPS model used 275 criteria → 23
sub-factors → 8 factors; ~138 of those were proprietary KOTRA survey data we
cannot replicate, so we target a credible open-data subset instead.)

---

## 3. Scoring methodology

- **Normalization = percentile-within-year.** Each criterion is ranked across the
  country set *within each year*; 100 = best, ~50 = median, ~0 = worst. Chosen
  because ratio-to-the-single-leader compressed 60 countries into tiny blobs, and
  because percentile makes "50 = the median country" instantly interpretable.
- **Why within-year matters:** it sidesteps cross-edition non-comparability
  (e.g. GII re-baselines methodology yearly; WGI revises history). We never
  compare a 2015 score to a 2020 score directly.
- **Polarity:** criteria where lower is better (FSI fragility, tariffs, bribery,
  informal competition) carry polarity `−` and are inverted before ranking.
- **Other methods available** in the engine: `ratio_max` (top country = 100, used
  in the published validation) and `minmax`. A run can force one method via
  `--scoring-method`.
- **Validation:** the engine reproduces Moon, Rugman & Verbeke (1998) Table 4
  (Korea vs Singapore) exactly — all 16 indices match. This test must keep
  passing after any engine change (`validation/korea_singapore_1998.py`).

---

## 4. Architecture & stack

All free-tier, chosen for a non-technical owner:

| Layer | Tool | Role |
|---|---|---|
| Code host | **GitHub** (`rebuitrago/ddd-platform`, public) | source of truth; triggers deploys |
| Database | **Supabase** (Postgres) | framework + observations + runs + scores |
| App | **Streamlit Community Cloud** | the live diamond app |
| Engine | Python (`ddd/` package) | connectors, ingest, scoring, loaders |

**Key files:**

- `db/schema.sql` — base schema (factor, determinant, indicator, country,
  observation, run, score, `diamond_coords` view).
- `db/migration_01_subfactors.sql` — adds the `sub_factor` layer + backfills
  existing indicators into a "General" sub-factor. Safe on a live DB.
- `db/migration_02_expanded_catalog.sql` — creates 22 sub-factors, inserts new
  criteria, reassigns the original 18 indicators. Idempotent.
- `ddd/scoring.py` — pure engine: normalize (ratio_max/minmax/percentile),
  two-level aggregation, diamond coordinates.
- `ddd/connectors.py` — `fetch_wdi` (wbgapi), `fetch_wgi` (WGI via classic v2
  REST — see §6), `load_manual_csv`, `upsert_observations`.
- `ddd/ingest.py` — auto-pulls active Track-A (WDI/WGI) indicators; splits WGI
  codes (`.EST`) to the WGI fetch.
- `ddd/load_datasets.py` — loads Track-B files (GII, PCI, FSI, UNCTAD, WGI Excel
  export) with name/M49 → ISO3 resolution and the UNCTAD pivot/÷GDP prep.
- `ddd/score_run.py` — reads framework + observations, scores, writes a run.
- `app.py` — Streamlit app: benchmarked auto-scaled diamonds, "What this shows"
  insights panel, Rankings tab.
- `CATALOG.md` — human-readable catalog of all 53 criteria.

**Credentials / key types (Supabase):**

- `sb_publishable_…` → app reads (low-priv, RLS applies). Goes in Streamlit secrets
  as `SUPABASE_PUBLISHABLE_KEY`.
- `sb_secret_…` → server writes (bypasses RLS). Goes in local shell / GitHub
  Actions as `SUPABASE_SECRET_KEY`. **Never commit it** (Supabase auto-revokes
  secret keys found in public repos).
- Read access (RLS public-read policy) is enabled on run, score, determinant,
  factor, country, sub_factor.

---

## 5. Data catalog (current: 53 criteria, 22 sub-factors; +6 enrichment criteria pending — see §5a)

**Two delivery tracks:**

- **Track A (automatic)** — pulled by `ingest.py` from the World Bank. Includes
  WDI economic series, **WGI governance**, and the **WBES** firm indicators
  (mirrored in WDI under `IC.FRM.*`).
- **Track B (file load)** — GII, PCI, FSI, UNCTAD, and the WGI Excel export, via
  `load_datasets.py`.

**Sources and where they map:**

| Source | What we use | Feeds |
|---|---|---|
| **World Bank WDI** | GDP, growth, R&D, FDI, mobile, credit, trade, tariffs, enrollment, migration, remittances, hi-tech exports, researchers, journal articles, air freight, ICT exports, new-business density | spread across all determinants |
| **WGI** (governance) | Government Effectiveness, Regulatory Quality, Rule of Law, Control of Corruption (`GE/RQ/RL/CC.EST`) | Politicians & Bureaucrats |
| **WBES** via WDI `IC.FRM.*` | bank loan/credit (`BNKL`), bribery (`BRIB`), informal competition (`CMPU`), formal training (`TRNG`), new product (`NPRD`) | Firm Strategy, Finance, Workers, Entrepreneurs |
| **GII** (WIPO) | 6 pillar/sub-pillar scores: Human capital & research, Infrastructure, Market sophistication, Business sophistication, Knowledge & tech outputs, Knowledge diffusion | Factor Conditions, R&S, Entrepreneurs, Firm Strategy, Professionals |
| **PCI** (UNCTAD) | 7 components: Human capital, Natural capital, Energy, Transport, ICT, Institutions, Private sector | Factor Conditions, R&S, Workers, Politicians & B., Firm Strategy |
| **FSI** (Fund for Peace) | 6 of 12 components: C1 Security, P2 Public Services (→ state capacity); P1 Legitimacy, P3 Human Rights, C2 Elites (→ legitimacy); **E3 Brain Drain (→ Professionals, international)** | Politicians & Bureaucrats, Professionals |
| **UNCTAD FDI** | inward + outward **stock**, computed as **% of GDP** | Factor Conditions, international |
| **EIU** (Business Environment) *(run 4)* | 3 sub-components: Policy toward private enterprise & competition, Labour market & skills, Financing — **forecast-bearing**, proprietary, never redisplayed raw | Firm Strategy, Workers, R&S Finance |
| **Euromonitor** (Passport) *(run 4)* | Unemployment, Inflation (new criteria); real GDP growth (relay only) — point-in-time actuals + forecast | Workers, Demand |
| **V-Dem** *(run 4)* | Electoral Democracy Index (`v2x_polyarchy`) — fills the Voice-&-Accountability axis WGI omits | Politicians & Bureaucrats |

**Anti-double-counting rules (deliberate, defensible):** each criterion lives in
exactly one cell. PCI Human capital → Workers (not Factor Conditions, which GII
Human capital covers). PCI Private sector → Firm Strategy (not Entrepreneurs).
GII Infrastructure → R&S (not Factor Conditions). FDI in/out → International
Factor Conditions only.

**Dropped on purpose:** **QoG** (Quality of Governance) — it repackages WGI and
ICRG, which we already use directly, so it would have double-counted the
governance signal. GII *Institutions* and *Creative outputs* pillars excluded
(governance already rich; creative has no clean DDD home). PCI `pci_total`
(headline composite) and `pci_str_chg` excluded.

**Key principle:** always decompose a composite into its relevant
**pillars/components** — never drop a headline index (GII overall, PCI total)
into a cell, which would bury a black box inside the composite and double-count.

---

## 5a. Enrichment criteria to add (run 4 → 5) — insert-ready

**PROVISIONAL on the three design calls in §9D — confirm before scoring.**

**Two new sub-factors first** (then the 6 criteria reference them):

| new sub_factor | under determinant | determinant_id | suggested sub_factor_id |
|---|---|---|---|
| Macroeconomic stability | Demand Conditions | 3 | 31 |
| Democratic accountability | Politicians & Bureaucrats | 7 | 32 |

**Six new criteria:**

| context | name | source | source_code | polarity | track | sub_factor (id) | provenance |
|---|---|---|---|---|---|---|---|
| domestic | EIU: Policy toward private enterprise & competition | EIU | `EIU.BE.PRIV_ENTERPRISE` | + | B | Firm Strategy → Business env & rivalry (10) | forecast-blended; 5-yr window |
| domestic | EIU: Labour market & skills | EIU | `EIU.BE.LABOUR_SKILLS` | + | B | Workers → Labor quality (29) | forecast-blended; 5-yr window |
| domestic | EIU: Financing | EIU | `EIU.BE.FINANCING` | + | B | R&S → Finance (12) | forecast-blended; 5-yr window |
| domestic | Unemployment rate (%) | Euromonitor | `EUROMONITOR.UNEMPLOYMENT` | − | B | Workers → Labor quantity (30) | actual + forecast |
| domestic | Inflation (annual %) | Euromonitor | `EUROMONITOR.INFLATION` | − | B | Demand → Macroeconomic stability (**31, new**) | actual + forecast |
| domestic | Democratic accountability (V-Dem polyarchy) | V-Dem | `VDEM.V2X_POLYARCHY` | + | B | Politicians & Bureaucrats → Democratic accountability (**32, new**) | actual |

*`method` per row is just a default — the run forces `percentile` via `--scoring-method`. EIU "scored 1–10, 10 = best" → polarity `+`. Unemployment/inflation lower-is-better → `−` (inverted before ranking, same as FSI/tariffs/bribery). V-Dem polyarchy is a bounded 0–1 index → mirrors the WGI `minmax` precedent, irrelevant under forced percentile.*

**Documented alternatives for the V-Dem criterion (sensitivity comparators only — never add alongside V-Dem):** if `v2x_polyarchy` is ever judged too academic for the policy audience, the recognizable swap-ins are **Freedom House** *Freedom in the World* Electoral Process subcategory, or **EIU** Democracy Index Electoral Process pillar. Both reach 2025 but are coarser (heavy percentile ties) and more contested; FH/EIU measure individual freedoms, not government performance, so neither fills the state-capacity / bureaucratic-quality gap — they are democracy-axis replacements, one-for-one, not additions. (See §9 partial-coverage rule.)


---

## 6. Hard-won technical learnings (read before touching the pipeline)

These are the non-obvious things that cost real debugging time. Preserve them.

1. **WGI is NOT reachable through the normal World Bank API.** The v2 endpoints
   (`/sources/3/series/…` and `/country/all/indicator/…?source=3`) return either
   empty/JSON-decode errors or `Invalid value` (error 120) for `GE.EST` etc. The
   codes and source (3) are correct; the live API simply won't serve them that
   way. **Solution adopted:** download the official WGI Excel
   (`wgidataset_with_sourcedata-YYYY.xlsx`) and load it as a Track-B file. The
   file has one sheet per dimension (`va, pv, ge, rq, rl, cc`); the value column
   is **"Governance estimate (approx. -2.5 to +2.5)"**; `Economy (code)` is ISO3.
   A small prep step builds `data/wgi.csv` (iso3, year, GE.EST, RQ.EST, RL.EST,
   CC.EST) from the four sheets we need. *(`fetch_wgi` via REST exists in
   connectors but does not currently return data — the Excel path is the working
   one.)*

2. **WBES** — don't aggregate the firm-level `.dta` microdata yourself. Use the
   WDI `IC.FRM.*` mirror (Track A). It's a curated subset, uses *unweighted*
   aggregation (vs the ES portal's weighted), and is sparse (survey years only) —
   all acceptable, footnote it.

3. **UNCTAD FDI** arrives in **long format** (rows per Flow/Direction) with **UN
   M49 numeric** economy codes and includes **regional aggregates** (World,
   Africa…). The loader: keeps stock rows only, maps M49 → ISO3 (via `pycountry`,
   which auto-drops aggregates since they don't resolve), pivots to inward/outward,
   and divides by WDI GDP to get **% of GDP**. Coverage = intersection of UNCTAD
   and WDI-GDP years.

4. **Country identifiers vary by file:** GII = country names; PCI/FSI = country
   names; UNCTAD = M49 numeric; WGI = ISO3. The loader resolves names via
   `pycountry` fuzzy + an `OVERRIDES` dict for tricky spellings (Korea, Türkiye,
   Russia, Viet Nam, Iran, Egypt, Bolivia, Czechia, Côte d'Ivoire, etc.).

5. **Stata `.` missing markers** appear when data is exported from `.dta`/Excel.
   The loader skips cells equal to `.`, ``, `..`, `NA`. Without this, float
   conversion crashes.

6. **De-duplicate before upsert.** Supabase/Postgres `ON CONFLICT … DO UPDATE`
   errors (`21000`) if one batch contains two rows with the same
   `(indicator_id, country_iso3, year)`. The loader collapses duplicates
   (last-wins) before upserting.

7. **Transient `RemoteProtocolError` / `StreamReset`** on large upserts is a
   network hiccup, not a data error. Re-running is safe (upserts are idempotent).

8. **Operational hygiene for the owner:** the real project must be the folder that
   contains `app.py`, `ddd/`, `db/`. Beware nested/duplicate `ddd-platform`
   folders from unzipping, and a stale `venv` left in a different folder (rebuild
   `venv` *inside* the project). `pip install openpyxl` is needed to read `.xlsx`.

9. **Trailing-character traps in headers:** PCI uses `year_` (trailing underscore)
   and `pci_Institutions` (capital I); FSI value columns carry `C1: ` style
   prefixes; GII headers must match exactly incl. capitalization. A silent `0`
   load or "column not found" is almost always an exact-header mismatch.

---

## 7. Deployment runbook (one-pass)

1. Put the four/five data files in `data/` (gii.csv, pci.csv, fsi.csv,
   unctad_fdi.csv, wgi.csv). Build `wgi.csv` from the WGI Excel first.
2. GitHub: update `ddd/*.py`, `requirements.txt` (incl. `pycountry`, `openpyxl`),
   `app.py`.
3. Supabase SQL editor: run `migration_01_subfactors.sql`, then
   `migration_02_expanded_catalog.sql`.
4. Local terminal (inside the project, venv active, secrets exported):
   ```
   pip install -r requirements.txt
   export SUPABASE_URL=...   export SUPABASE_SECRET_KEY=...
   python -m ddd.ingest --start 2010          # Track A incl. WBES IC.FRM.* + WGI
   python -m ddd.load_datasets                 # GII, PCI, FSI, UNCTAD, WGI
   python -m ddd.score_run --label "DDD v2 expanded" --scoring-method percentile --vintage "multi-source 2025"
   ```
5. App: switch the **Methodology run** selector to the new run.

---

## 8. Current state (as of this writing)

- **Live and working.** Latest run: **"wave2 + WTO + IMF BOP 2025" (run_id 8)**,
  60 countries, years **1996–2026** (runs are now capped with `--year-to 2026`;
  2027–2031 forecast-only percentiles are no longer manufactured), percentile
  within-year, two-level sub-factor aggregation, **coverage rule v2.0**.
  Supersedes run 7 ("wave2 + WTO trade + coverage floor") and run 6
  ("wave2 + WTO 2025 trade").
- **App honesty layer v1.1 is deployed** (doublediammond.streamlit.app). Missing
  data renders as a GAP (grey open ring), never as zero; thin corners
  (engine-flagged or single-criterion) carry an open orange diamond with
  coverage counts on hover; a partial international shape loses its fill and is
  labeled "partial (n of 4 corners)"; the insights panel states coverage,
  names dead corners, refuses the international-linkages narrative on partial
  years, and falls back to domestic-scope peer comparison; rankings show a
  coverage column; the year selector is capped at `MAX_DISPLAY_YEAR = 2026`.
  File carries `HONESTY_LAYER_VERSION` for deploy verification.
- **Coverage rule v2.0 (engine).** Two-part rule in `ddd/scoring.py`
  (`COVERAGE_RULE_VERSION = "2.0"`): sub-factor ratio (< 0.5 of expected)
  **OR absolute criterion floor** (`--coverage-min-criteria`, default 2).
  Closes the §11 1-of-1 loophole. Decision: **flag-and-show** (score visible,
  marked), floor = 2. Flags only; index values byte-identical (verified old vs
  new engine on identical data). Run 8: 5,845 flagged (533 ratio, 5,782 floor).
- **IMF BOP 2025 relay executed** (§9C below): 180 observations written,
  re-scored as run 8. The 2025 international diamond is now **6 of 7
  determinants** (physical 4 of 4). Only Entrepreneurs international
  (high-tech exports → Comtrade) remains dead at 2025.
- **Validation:** Korea–Singapore (1998) reproduction passes after the v2.0
  engine change (re-run and confirmed).
- **New finding (run 7/8 flag detail):** 2026 domestic Firm Strategy and R&S
  are carried by a single EIU criterion each (57 countries flagged) — the
  forecast-fresh 2026 corners were single-source shapes, now measured. §9A's
  partial-freshness trap, quantified.

---

## 9. Source enrichment & freshness design (decided at run 4)

**A. Freshness ceiling — empirically confirmed at 2024 (one exception).** Across the
*entire* open-data ecosystem — World Bank/WDI and its upstream providers — actual
observations top out at **2024**. Checked directly at source: **ILO, UNESCO, ITU
all end 2024; IMF WEO actuals also end 2024.** The **one exception is V-Dem, which
reaches 2025 actual** (verified) — so democratic accountability is the only
genuinely-observed 2025 value in the panel, and the only 2025 cell that carries *no*
forecast flag. Otherwise **2025–2031 is forecast-only territory**, reachable solely
through modeled sources (EIU, Euromonitor, IMF WEO). Past 2024, outside V-Dem,
"current" in this tool *always means forecast* and must be flagged as such.

**Partial-freshness trap (sharpened by the V-Dem exception):** V-Dem at 2025 does
*not* make the Politicians & Bureaucrats corner 2025-current. That determinant
averages four sub-factors; the other three (FSI/WGI/PCI-fed) still stop at 2024. A
2025 governance score would therefore rest on V-Dem *alone* — one fresh sub-factor
silently standing in for the whole cell, which is *more* misleading than a clean
2024 corner. **Suppress or explicitly mark single-sub-factor determinants** rather
than let partial freshness distort a corner. This is why the app defaults to a
well-covered year.

Consequence for the diamond (the thinnest-determinant problem, made concrete):

- **Can show forecast-fresh (2025–26):** Firm Strategy, Workers, R&S Finance,
  Demand (growth + new inflation) — wherever EIU or Euromonitor lands.
- **Frozen at 2024-actual, no forecast rescue:** Factor Conditions, Professionals,
  and the GII/FSI/WGI/PCI-fed corners. Nothing covers these constructs forward.

A 2025 diamond is therefore *necessarily* mixed actual/forecast. The app must mark
this, or a partially-forecast diamond misleads a policy reader.

**B. Three enrichment mechanisms — kept strictly separate.**

1. **Freshness relay** — *same construct*, fresher/forecast source, handed off at
   the **year boundary** onto an existing criterion (whole column at once, never
   per-country — mixing two sources inside one criterion-year pool breaks the
   within-year homogeneity the method depends on). Lives in the live panel.
2. **New construct** — measures something not in the basket; joins a sub-factor as
   a new criterion. Used sparingly.
3. **Sensitivity / robustness check** — block-swap a source, re-score, confirm
   rankings hold. Lives in a **separate analysis layer for the manuscript**, never
   in the live composite.

**Guard:** more sources in the *same* composite ≠ more robustness. Piling
correlated datasets into one cell makes it an echo chamber whose score reflects
*how many such datasets exist*. Robustness is **demonstrated** in a sensitivity
appendix, not **wired** into the basket. (Same logic that dropped QoG.)

**Overlap-correlation guardrail:** a relay or new criterion is only honest once the
overlap years confirm the new source lands a country near the *same percentile* the
cell's existing members do. The overlap years you'd otherwise "skip as duplicate"
are precisely the calibration set. (Exception: an upstream re-source — same series,
correlation ≈ 1 — needs no check, but see §9 dropped list: none survived.)

**C. Final included set (run-4 enrichment).** Insert-ready rows in **§5a**.

- **New criteria (6):** EIU ×3 (Policy toward private enterprise → Firm Strategy;
  Labour market & skills → Workers/Labor quality; Financing → R&S/Finance),
  Euromonitor ×2 (Unemployment → Workers/Labor quantity; Inflation → new Macro
  stability sub-factor), V-Dem ×1 (Electoral Democracy → new Democratic
  accountability sub-factor).
- **Relays (no new rows):** GDP growth (#6) — **IMF WEO primary**, Euromonitor
  cross-check (WEO chosen primary for its per-country provenance, see E). FDI
  ratios (#8, #9) — WEO relay/cross-check. All need the overlap-correlation check
  (WEO/Euromonitor are independent of World Bank).
- **Dropped — upstream re-source (UIS/ITU/ILOSTAT): REMOVED.** Premise falsified:
  their actuals also end 2024, so they recover *no* hidden fresh year over WDI. The
  "secretly stale" rows (R&D 10, researchers 13, enrollment 30/51, ICT 24) stay on
  WDI.
- **Dropped — EIU:** all political sub-components (dup WGI/FSI), Infrastructure
  (GII/PCI), FDI-policy & foreign-trade (UNCTAD/WDI), Macro (GDP/growth), Tax
  Regime (no home), any Overall/headline score (black box).
- **Dropped — Euromonitor Interest Rate:** parked — no clean home, ambiguous
  polarity (high rate = cost-of-capital drag *or* monetary credibility).
- **Sensitivity comparators only (never panel rows):** CPI, Polity V, WGI's own
  source feeds, third-party GII scrapes, OECD.Stat (sparse for the emerging panel),
  Enterprise-Survey microdata (already decided via the `IC.FRM` mirror).
- **Optional gap-fill:** IMF CDIS / OECD FDI for UNCTAD's missing FDI-stock years
  (#31/#32). Wire only if the gaps bite.

**Entrepreneurs stays fragile — flagged, not solved.** Only 4 criteria (3, 14, 40,
41), three patchy/survey-stale; only GII market sophistication (40) is solid. EIU
doesn't cleanly cover this cell without overlapping GII (40), so no forced mapping.
A weakest-link risk to watch.

**D. Provenance — required on every new/relayed value.** Each value carries:
**source, published-date/vintage, and an `actual / estimate / forecast` flag.**

- **EIU:** flag from `.xlsx` **fill colour** (openpyxl — same dependency as WGI).
  Also note EIU Business Environment is a **centred 5-year rolling average**, not
  point-in-time → footnote the cell. Because the window reaches ±2 yrs, EIU's
  freshness contribution is *inherently forecast-blended* — accepted, flagged.
- **Euromonitor:** flag from the **Historic/Forecast column band** (boundary year
  is per-export — capture it, don't hardcode). Pin to the **"Euromonitor Baseline"
  scenario**.
- **IMF WEO:** flag from the **per-country "Estimates start after" column** — the
  cleanest provenance of any source (country-specific actual/forecast seam).
- **App marker:** any current-year diamond leaning on a forecast year shows a
  visible "includes forecast" badge. **That marker is the entire honesty basis for
  the post-2024 contribution.** Standing licensing guard: no view ever lets a user
  read a raw EIU value back out.

**E. Resolved design calls — CONFIRMED (run 4).**

1. **Inflation home →** new **"Macroeconomic stability"** sub-factor under Demand
   Conditions (not "Demand quality", which is buyer sophistication).
2. **Unemployment placement →** *same* sub-factor as labour-force participation
   (Labor quantity, sf 30), read as a combined "labour mobilisation" signal (low
   participation offsets low unemployment — the discouraged-worker reading, the
   correct composite).
3. **V-Dem component →** **Electoral Democracy Index (`v2x_polyarchy`)** —
   continuous 0–1, fills the Voice-&-Accountability axis WGI omits with minimal
   overlap with our effectiveness/integrity constructs. **Frontier verified to
   2025.** (Freedom House / EIU Democracy = recognizable but coarser swap-ins,
   sensitivity only — see §5a.)
4. **Partial-determinant coverage rule →** when a determinant's sub-factors have
   ragged end-years (e.g. governance 2025: V-Dem present, FSI/WGI/PCI absent),
   **score from the sub-factors present and attach a coverage flag** ("n of N
   sub-factors"), suppressing the determinant-year only below a coverage threshold
   (default: < half of sub-factors present). The app surfaces the coverage count so
   a thin cell reads as thin, not confident. **Ruled out:** (a) averaging silently
   (mislabels one fresh sub-factor as the whole cell); (b) last-observation-carried-
   forward to fake a full cell (manufactures false freshness — the exact thing the
   forecast flag exists to prevent). **Cross-construct fill is never allowed:** a
   missing sub-factor is *never* stood in for by a present one — democratic
   accountability is not rule of law. The only legitimate fill is a *same-construct
   relay*, and none exists for state capacity / bureaucratic quality past 2024, so
   that corner genuinely cannot reach 2025.

**F. Smaller items (deferred, optional):**

- Default the app to the most recent *well-covered* year automatically (instead of
  the latest year with any data). **Now coupled to the forecast marker** (E above).
- Sub-factor **drill-down** in the app (foundation built; UI not yet) — lets a
  policy reader see *why* a determinant scores as it does. This is the feature that
  most increases briefing value.
- Tune the "What this shows" wording to the owner's policy-audience **voice**
  (less jargon: "determinant", "international linkages").
- Per-capita / intensity variants for size-dominated indicators (optional; needs
  re-ingest).
- Store **sub-factor-level scores** for drill-down without recompute.
- **Fix criterion #3 (new business density):** its `determinant_id` still reads `1`
  (Firm Strategy) while its `sub_factor_id` (24) sits under Entrepreneurs — lone
  mismatch, vestigial from the sub-factor migration. Confirm the scorer aggregates
  via `sub_factor_id` (it does), then null/fix `determinant_id` so it can't bite.
- **Wire criterion #12** (international students inbound) — its `source_code` is
  `null`; the pipeline isn't connected.

---

## 10. Decisions log (quick reference)

- Stack: GitHub + Streamlit Cloud + Supabase, all free tier.
- Scoring: **percentile within-year** (interpretability + cross-edition safety).
- Hierarchy: **two-level sub-factor** (IPS fidelity + defensible weighting). Chosen
  over a flat model for policy/academic use.
- WBES: **Track A via WDI `IC.FRM.*`**, not microdata aggregation.
- WGI: **Excel file load**, because the API won't serve source 3.
- QoG: **dropped** (redundant with WGI/ICRG).
- UNCTAD: **inward+outward stock ÷ GDP**, computed at load.
- Composites: use **pillars/components**, never headline indices.
- Forecasts (EIU): allowed as a freshness input but must be **flagged**, never
  silently mixed; no raw-value redisplay.
- **Freshness ceiling (run 4): actual data ends 2024 ecosystem-wide** (WDI + ILO +
  UNESCO + ITU + WEO all checked), **except V-Dem, verified to 2025**. Post-2024 is
  otherwise **forecast-only** (EIU, Euromonitor, WEO), always flagged; V-Dem 2025 is
  the lone actual past the ceiling and carries no forecast flag.
- **Enrichment mechanisms kept separate:** relay / new construct / sensitivity-only.
  Robustness is *demonstrated in an appendix*, not *wired into the basket*. Clean
  primary panel + targeted enrichment is the chosen architecture.
- **Upstream re-source (UIS/ITU/ILOSTAT): dropped** — their actuals also end 2024,
  so no freshness gain over WDI.
- **EIU (run 4):** 3 Business-Environment sub-components added as new criteria
  (forecast-blended, 5-yr window, flagged); political/infra/trade/macro/tax/headline
  EIU dropped (double-count or no home).
- **Euromonitor (run 4):** Unemployment + Inflation as new criteria; GDP growth as a
  relay/cross-check; Interest Rate parked.
- **IMF WEO (run 4):** forecast relay + cross-check (growth, FDI); actuals end 2024
  (no actual-side freshness); per-country **"Estimates start after"** used as the
  actual/forecast flag — primary growth relay for that reason.
- **V-Dem (run 4):** `v2x_polyarchy` added as **Democratic accountability**,
  filling the WGI Voice-&-Accountability gap.
- **Provenance flag (`actual/estimate/forecast`) now mandatory per value;** app
  marks any forecast-leaning diamond.
- **Partial-determinant coverage (run 4): score-from-present + coverage flag**, with
  a threshold (default < half sub-factors → suppress the year). LOCF and silent
  averaging ruled out. Cross-construct fill never allowed — only same-construct
- **Coverage rule v2.0 (run 7):** absolute criterion floor added (default 2,
  `--coverage-min-criteria`); **flag-and-show** chosen over hide-as-gap; flags
  never alter index values (verified byte-identical).
- **Honesty layer v1.1 (app, deployed):** gaps never render as zeros
  (`fillna(0)` removed); thin/suppressed corners visibly marked; partial
  international unfilled + labeled; peer means skip missing (no zero
  pollution); insights coverage-aware; long dashes removed from UI copy.
- **Display/run year cap:** app `MAX_DISPLAY_YEAR = 2026`; runs use
  `--year-to 2026`. A competitiveness score 5+ forecast years out is not
  defensible; 2027–2031 no longer produced or shown.
- **IMF BOP relay (run 8):** executed per §9C; 180 rows, value_type
  `estimate`, tiered vintages; ground-truth gate 0.00pp ×4.

---

## 12. Roadmap (post-run 8) and operating discipline

**Ordered next steps:**
1. **Comtrade / WITS — high-tech exports** for Entrepreneurs international,
   the last dead 2025 corner.
2. **Hygiene trio:** criterion #3 determinant_id mismatch; criterion #12
   null source_code; International professional mobility null source_code.
3. **Insights panel v2:** caveated narration on partial years ("among
   observable corners…"), sub-factor attribution of corner scores, peer and
   trajectory positioning — the analyst-usable text layer.
4. **Sub-factor drill-down UI** (foundation built) — highest briefing value.
5. **Visual identity pass** (Plotly theme, typography, small multiples), then
   **exportable PDF country briefs** reusing the same components.
6. **Sensitivity appendix for the manuscript** (ratio_max vs percentile
   re-score, V-Dem↔Freedom House swap, block-swaps) — exists as principle
   only; must be produced before submission.
7. **Criterion enrichment for permanently thin international cells** (Demand
   intl and Entrepreneurs intl have ONE criterion defined — they can never
   pass the floor until a second construct is added; that is a framework gap,
   not a data gap).

**Operating discipline (hard-won this session, keep):**
- **Sentinel greps on every file hand-off.** Every delivered file carries a
  version constant (`HONESTY_LAYER_VERSION`, `COVERAGE_RULE_VERSION`,
  `BOP_RELAY_VERSION`); verify with `grep -c` in Downloads AND in the project
  destination before running anything. Two incidents this session: an old
  Downloads `app.py` masked the new one; validation+dry-run were executed
  before the engine files were actually copied.
- **Expected outputs must be executed, not recalled.** A stated expected grep
  count was wrong because it came from memory; all expectations are now
  produced by running the check first.
- **The project folder lives inside `Downloads/Setup DD/`** (and the BOP CSV
  in iCloud Drive, subject to eviction — `ls -lh` before use). Relocating the
  project is desirable but must be planned (venv breaks on move).
- Owner working pattern unchanged: probe → dry run with pre-stated expected
  output → real run → app verification → update this file.
  relays, which don't exist for state capacity / bureaucratic quality past 2024.
- **Freedom House** *Freedom in the World*: **out of the panel** — measures
  individual freedoms not government performance (doesn't fill the capacity gap),
  overlaps V-Dem/WGI, and is coarse. Kept as a sensitivity comparator / recognizable
  swap-in for V-Dem only.

- **WTO trade relay (post-run 5):** 2025 international trade pulled live from the WTO
  Timeseries API (goods `ITS_MTV_AX/AM` total `TO` + services `ITS_CS_QAX/QAM` total `S`),
  combined goods+services, gap-filled onto WDI `NE.EXP.GNFS.ZS` / `NE.TRD.GNFS.ZS` for
  2025+, tagged `estimate`. See §9B for the full contract.
- **2025 GDP denominator: nominal, self-contained** — 2024 GDP × (1+real growth) ×
  (1+inflation), both pieces already in the DB (Euromonitor). Real-growth-only and external
  WEO GDP rejected.
- **Services were required, not optional** — goods-share of total trade ranges 0.56–0.95
  across the panel, so a fixed goods-only rescale would misrepresent services-heavy
  economies; total services (`S`, incl. government) added to match the WDI BPM6 construct.
- **2025 international coverage finding (open):** only 3 of 7 international determinants reach
  2025, each on a single criterion; the sub-factor coverage rule cannot detect this. Decision
  on extend (A) / tighten-suppression (B) / accept-partial (C) pending source exploration. §11.

---

## 9B. WTO trade relay — 2025 international data (built after run 5)

**Goal.** The 2025 *international* diamond was collapsing: WDI trade data ends 2024,
so the international corners had no current year. This relay pulls genuine 2025 trade
from the WTO Timeseries API and gap-fills it onto the existing WDI trade criteria.

**Verified API contract** (locked via the OpenAPI spec `version1.json` + 4 probes the
owner ran; the build sandbox cannot reach `api.wto.org`, so every fact below was
confirmed on the owner's machine):
- **Endpoint** `https://api.wto.org/timeseries/v1/data`; auth via `subscription-key`
  query param. Subscription "standard_wto", **Standard product covers Timeseries**.
  The key is a private credential — keep it out of chat/screenshots; it was exposed
  once and **regenerated**.
- **Rows** live under `data["Dataset"]`; fields are **PascalCase**:
  `ReportingEconomyCode`, `ReportingEconomy`, `Year`, `Value`, `ValueFlagCode`,
  `ProductOrSectorCode`.
- **Country → ISO3**: `GET /reporters` carries an **`iso3A`** field directly.
  Aggregates (World, regions) have `iso3A = null` and self-filter. No fuzzy matching.
- **Indicators** (annual, value, Million US$):
  - Goods exports `ITS_MTV_AX` / imports `ITS_MTV_AM`, filter `ProductOrSectorCode == "TO"` (total merchandise).
  - Services exports `ITS_CS_QAX` / imports `ITS_CS_QAM` ("preliminary annual" — the series that reaches 2025), filter `ProductOrSectorCode == "S"` (**"Memo item: Total services"**, the BPM6-matching total incl. government services — **not** `SOX` "Commercial services", which excludes them).
- **2025 confirmed present** for goods *and* services across the panel. WTO does **not**
  flag 2025 as provisional (`ValueFlagCode = null` even for 2025).

**Construction** (matches the WDI goods+services %GDP construct):
```
Exports %GDP = (goods_exp + services_exp) × 1e6 / GDP_2025 × 100
Trade   %GDP = (goods_exp + services_exp + goods_imp + services_imp) × 1e6 / GDP_2025 × 100
```
Validated against WDI actuals on the 2022–24 overlap (Brazil): exports within **±0.27pp**,
trade within **±0.41pp**. A built-in 2024 ground-truth check runs every load and prints
the median |Δ| (live run: **1.17pp across 53 countries** — well within tolerance).

**2025 GDP denominator — nominal, self-contained** (decision). WDI GDP ends 2024 and
WTO trade is nominal current US$, so the denominator must be nominal 2025 US$:
```
GDP_2025 = GDP_2024 (NY.GDP.MKTP.CD)
           × (1 + real_growth_2025/100)     ← relayed Euromonitor NY.GDP.MKTP.KD.ZG
           × (1 + inflation_2025/100)        ← Euromonitor EUROMONITOR.INFLATION
```
Uses only data already in the DB. Documented as a **proxy** ((1+real)(1+infl) ≈ nominal
growth; the exact factor is the GDP deflator, not CPI) — acceptable, and the result is
tagged `estimate`. Rejected: real-growth-only (units mismatch → overstates trade%GDP for
high-inflation countries); external WEO GDP (another untestable dependency).

**Attachment — gap-fill relay** (decision). Onto WDI `NE.EXP.GNFS.ZS` (Demand Conditions /
International demand) and `NE.TRD.GNFS.ZS` (Firm Strategy / Market openness), 2025+ only
(years > the non-relay frontier of 2024), vintage **"WTO 2026 + derived GDP (relay)"**,
tagged `estimate`. Idempotent (relay rows excluded from frontier calc; re-runs overwrite
their own 2025). Rejected: **fixed rescale of goods-only** — the seam check showed the
goods-share of total trade ranges **0.56 (Singapore) → 0.95 (Mexico)**, far too variable
for a constant factor, which is *why* services had to be added. Rejected: **new standalone
criterion** — would double-count trade and dilute the corner.

**Implementation.** All in `ddd/load_datasets.py` (consistent with the other integrated
loaders — one file swap). New: WTO config block, `_wto_get` / `_wto_reporters_iso3` /
`_wto_fetch` / `_obs_year` helpers, `load_wto_trade(client, code_to_id, valid)`, called in
`main()` after `load_relays`. Defensive: skips cleanly (prints why, rest of load unaffected)
if `WTO_API_KEY` is unset or the fetch fails. The existing `--dry-run` exercises the live
fetch + computation and writes nothing — that is the verification gate.

**Result (live).** Dry run + real run clean: **94 rows, 47 countries** (2025 Exports%GDP +
Trade%GDP). 47/60 is the intersection of (WTO trade ∧ 2024 GDP ∧ 2025 growth ∧ 2025
inflation); the 13 dropped are mostly the ~12 Euromonitor-uncovered countries. Re-scored as
**"wave2 + WTO 2025 trade"**. Scale verified correct: percentile normalization produces
0–100 as expected (UAE 2025 Demand 97.9, Market openness 95.7 — top of panel, matching its
real export/trade intensity; 2023→2025 continuous, no jump).

---

## 9C. IMF BOP 2025 relay — EXECUTED (run 8)

**Loader:** `ddd/load_imf_bop.py` (`BOP_RELAY_VERSION`), streams the 1.2 GB wide
IMF export (`IMF.STA:BOP`, on the owner's machine in iCloud Downloads). Series
selected by SERIES_CODE tokens `{ISO3}.{ENTRY}.{ITEM}.{UNIT}.{FREQ}` — no name
matching (the code prefix IS the ISO3):

| criterion | numerator token(s) | denominator |
|---|---|---|
| ICT service exports (%svc, `BX.GSR.CCIS.ZS`) | `CD_T.SI.USD` | `CD_T.S.USD` (total services credit; no GDP) |
| Remittances (%GDP, `BX.TRF.PWKR.DT.GD.ZS`) | `CD_T.D752_S1W.USD` + `CD_T.D1.USD` | §9B derived GDP₂₀₂₅ |
| FDI inflows (%GDP, `BX.KLT.DINV.WD.GD.ZS`) | `L_NIL_T.D_F.USD` | §9B derived GDP₂₀₂₅ |
| FDI outflows (%GDP, `BM.KLT.DINV.WD.GD.ZS`) | `A_NFA_T.D_F.USD` | §9B derived GDP₂₀₂₅ |

`D_F` = "Direct investment, Total financial assets/liabilities" — the FULL DI
category (equity + debt + reinvested earnings); the earlier equity-only proxy
caveat is closed. Annualization waterfall per §9C contract (tier 1 annual /
tier 2 sum-4Q / tier 3 seasonality-scaled 3Q / tier 4 hold-at-2024, nothing
written). All rows `value_type = "estimate"`, vintage
`"IMF BOP 2025 (relay tier N)"`. Loader guards: aborts on missing series,
wrong-looking services label, or failed ground-truth gate; never overwrites a
non-BOP 2025 row; idempotent upsert.

**Ground-truth gate (live):** BOP-derived 2024 vs WDI 2024 in DB, median |Δ| =
**0.00pp on all four criteria** — expected, WDI sources these from BOP (same
upstream; buys currency, not corroboration, as the contract stated).

**Result (live):** **180 rows written**, tiers: ICT 52 (44/0/8), remittances
36 (31/0/5), FDI in 46 (40/0/6), FDI out 46 (40/0/6). Tier 2 empty is correct:
annual always accompanies four finalized quarters. Remittances thinner than
the ~45 hoped (denominator intersection with derived GDP, 48 countries).
Non-reporters hold at 2024 (UAE among them — its FDI corner correctly still
shows a coverage gap in 2025).

---

## 11. 2025 international coverage — RESOLVED to 6 of 7 (was: the finding that mattered)

Original finding (pre-run 7): only 3 of 7 international determinants reached
2025, each on a single criterion, and the ratio-only coverage rule could not
see it (1-of-1 always passes). Resolution took both paths **B then A**:

- **(B) done — coverage rule v2.0:** absolute criterion floor (default 2)
  added to the ratio rule; single-criterion determinant-years are now flagged
  by the engine and rendered honestly by the app (flag-and-show decision).
- **(A) largely done — IMF BOP relay (§9C):** Factor Conditions (FDI ×2,
  clears the floor cleanly), R&S (ICT, thin-flagged), Workers (remittances,
  thin-flagged) all reach 2025 with observed data.

**Current 2025 international status:** physical diamond 4 of 4; human 2 of 3.
| determinant | 2025 status |
|---|---|
| Factor Conditions | **2 criteria (FDI in/out), unflagged** |
| Demand Conditions | 1 criterion (WTO exports), flagged thin |
| Firm Strategy | 1 criterion (WTO trade), flagged thin |
| Related & Supporting | 1 criterion (BOP ICT), flagged thin |
| Workers | 1 criterion (BOP remittances), flagged thin |
| Professionals | 1 criterion (GII), flagged thin |
| Entrepreneurs | **dead — high-tech exports; Comtrade is the remaining path** |

**Still open:** International professional mobility has a `null` source_code
row (criterion defined, no indicator attached); criterion #12 (international
students) also unwired; criterion #3 determinant_id mismatch. Cheap hygiene,
repeatedly deferred — do these.

---

## 13. Comtrade high-tech exports relay — PARKED (probed 2026-07-07)

Probe-first verdict: do not build now. Executed availability numbers
(UN Comtrade public getDa, owner's machine, 2026-07-07):
- Annual 2025 (C/A/HS): 82 reporters globally; panel intersection 39/60.
- SITC-converted (S4) mirrors HS exactly: 82 global, same 39 panel. When
  eventually built, the SITC-based high-tech product list has a direct
  path; no HS-to-SITC mapping needed on our side.
- Monthly 2025 recovery for the 21 annual-missing: only FRA, GRC, IND,
  NGA have all 12 months. CHN, RUS, VNM, ARE, KAZ, QAT, TUN, VEN, ZMB,
  BGD, JOR, KEN at 0 months; THA 2, PER 4, BGR/UKR 9, NAM 1.
- Best achievable today: 43/60 with a structurally biased missing set
  (China, Russia, Vietnam, Thailand, UAE, Kazakhstan absent).
Decision: PARK until ~Q4 2026, then rerun the probes (public endpoint
https://comtradeapi.un.org/public/v1/getDa/C/{A|M}/{HS|S4}?period=...,
no key). Rationale: heaviest loader in the project (product-basket
numerator AND denominator, overlap gate vs WDI 2022-24) spent on a
permanently 1-of-1 thin-flagged corner pooling percentiles over a biased
43. Wrong margin. Eventual pull needs a "comtrade - v1" key
(comtradedeveloper.un.org); key never appears in chat or screenshots.

## Hygiene log (2026-07-07)
- Criterion #3 determinant_id FIXED: was 1, set to 6, matching
  sub_factor 24. Full-catalog scan: 0 mismatches remain. No re-score
  needed (scorer aggregates via sub_factor_id). Validation PASS.
- Future migration note: indicator.determinant_id is redundant with
  sub_factor.determinant_id; data that can disagree eventually will.
- Still open: criterion #12 null source_code; International professional
  mobility null source_code. Source decisions, not cleanups.

## 14. Criterion #60 — IP receipts (% service exports) — EXECUTED (run 9, 2026-07-07)

**Framework decision (owner):** Entrepreneurs international gains its
second construct per roadmap item 7. Charges for the use of intellectual
property, receipts, as % of total services exports. Placement rationale:
licensing proprietary technology abroad is the commercialization of
innovation in foreign markets, sibling of #14 high-tech exports
(internationalized innovative production). sub_factor 22 (International
entrepreneurship), indicator id 60, source_code
IMFBOP.IP_RECEIPTS_PCT_SVC, polarity +.

**Design:** BOP-direct end to end (1996-2025), NOT a relay: numerator
CD_T.SH.USD (IP charges n.i.e., credit), denominator CD_T.S.USD (total
services credit, same as ICT #24). No relay seam, no derived-GDP
dependency. History = value_type actual, vintage "IMF BOP (direct)";
2025 via the §9C waterfall = estimate, vintage
"IMF BOP (direct, 2025 tier N)". Caveat (in indicator notes): IP receipts
inflated by tax-driven IP domiciliation (NLD, CHE) — same distortion
class as re-export hubs in #14.

**Gate (new-construct variant):** no DB comparator exists, so the loader
fetches WDI BX.GSR.ROYL.CD and BX.GSR.NFSV.CD live (World Bank v2 API),
computes the WDI-implied share, compares on 2019-2024 overlap. Result:
312 country-years, median |delta| 0.00pp, p90 0.00pp. Tolerance 1.0pp,
abort-on-fail wired in.

**Executed results:** dry run then write, 1,532 rows (1,483 actual
1996-2024, 59 countries; 49 estimates 2025: tier1 42, tier3 7; VNM has
no series). DB readback matched the dry run row-for-row. Top-5 2025:
JPN 22.2, NLD 19.4, CHE 18.0, USA 15.4, DEU 9.7 — the predicted
innovation/IP-domicile profile. Re-scored as run 9 ("wave2 + WTO + IMF
BOP + IP receipts", 18,592 scores). Validation PASS (16/16), run before
and after.

**Honest state of the corner:** Entrepreneurs intl = 2 defined criteria,
mean_used 1.47. Historical years with both present clear the floor
unflagged; 2025 runs on #60 alone (high-tech exports parked per §13), so
2025 renders thin-flagged, not clean. First time this corner has ever
been present at the frontier year.

**Loader:** ddd/load_imf_bop.py, BOP_RELAY_VERSION = "2.0"; run-8 relay
preserved, new work behind --only ip. Migration:
db/migration_03_ip_receipts.sql (MIGRATION_03_IP_RECEIPTS_VERSION = 1.0),
idempotent, sequence-safe.

**Incident log (2026-07-07):** SQL pasted into the bash terminal
(harmless) and a verification query run before its migration; §13
confirmed pasted when it was not; discovery then established that
PROJECT_KNOWLEDGE.md had never existed on disk (only in the Claude
project) and that the local folder is NOT a git repository (no .git
anywhere on the machine; §4's "GitHub source of truth" describes the
deployed app, not the working copy). Discipline added: every runbook
step states its window (Terminal vs Supabase SQL Editor); PK updates
ship as append/merge scripts with verification, never manual pastes;
confirmations count only as command output, never as assertion.

**Open from today:** put the working folder under git and reconcile with
the deployed repo (find the repo name in the Streamlit app settings) —
top priority, the project currently exists in one folder in Downloads;
re-upload this file to the Claude project after every session; hygiene
items #12 and International professional mobility (source decisions);
EIU catalog export pending (Option C, Demand intl); Comtrade parked
per §13; human-diamond app check for the Entrepreneurs 2025 corner
(machinery verified, target corner not yet eyeballed).
