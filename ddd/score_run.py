"""
Scoring job: stored observations -> versioned run + scores.

Pipeline:
    1. read framework (factor, determinant, indicator) + observations from Supabase
    2. assemble the long scoring frame
    3. run the engine (within_year or pooled normalization)
    4. map determinant names back to ids
    5. write a `run` row + its `score` rows
    6. print a coverage report

The pure functions (build_scoring_frame, attach_determinant_ids,
coverage_report) take plain DataFrames and do no I/O, so they can be tested
offline. Only score_run() touches Supabase.

Usage:
    export SUPABASE_URL=...  SUPABASE_SECRET_KEY=...
    python -m ddd.score_run --label "EM 2010-2022 pooled" \
        --normalization pooled --vintage "WDI 2025-03"
"""

from __future__ import annotations
import os
import argparse
import pandas as pd

from ddd.scoring import compute_scores


# ---------------------------------------------------------------------------
# pure transforms (no I/O)
# ---------------------------------------------------------------------------
def build_scoring_frame(observations: pd.DataFrame,
                        indicators: pd.DataFrame,
                        determinants: pd.DataFrame,
                        factors: pd.DataFrame) -> pd.DataFrame:
    """Join raw observations to the framework into the engine's long format.

    observations : indicator_id, country_iso3, year, raw_value
    indicators   : id, determinant_id, context, polarity, method, active
    determinants : id, factor_id, name
    factors      : id, name
    """
    det = determinants.rename(columns={"id": "determinant_id", "name": "determinant"})
    fac = factors.rename(columns={"id": "factor_id", "name": "factor"})
    det = det.merge(fac[["factor_id", "factor"]], on="factor_id")

    ind = indicators.rename(columns={"id": "indicator_id"})
    ind = ind.merge(det[["determinant_id", "determinant", "factor"]],
                    on="determinant_id")

    long = observations.merge(ind, on="indicator_id")
    long = long.rename(columns={"country_iso3": "country",
                                "indicator_id": "indicator"})
    cols = ["country", "year", "factor", "context", "determinant",
            "determinant_id", "indicator", "raw_value", "polarity", "method"]
    return long[cols]


def attach_determinant_ids(scores: pd.DataFrame,
                           frame: pd.DataFrame) -> pd.DataFrame:
    """Map (factor, determinant) back to determinant_id after scoring."""
    key = (frame[["factor", "determinant", "determinant_id"]]
           .drop_duplicates())
    return scores.merge(key, on=["factor", "determinant"], how="left")


def coverage_report(frame: pd.DataFrame,
                    scores: pd.DataFrame) -> pd.DataFrame:
    """Per (factor, context, determinant): indicators available and how many
    actually carried data into the scores (min/mean across country-years)."""
    avail = (frame.groupby(["factor", "context", "determinant"])["indicator"]
                  .nunique().rename("indicators_defined"))
    used = (scores.groupby(["factor", "context", "determinant"])["n_indicators"]
                  .agg(min_used="min", mean_used="mean"))
    rep = pd.concat([avail, used], axis=1).reset_index()
    rep["mean_used"] = rep["mean_used"].round(2)
    return rep.sort_values(["factor", "context", "determinant"])


# ---------------------------------------------------------------------------
# Supabase I/O
# ---------------------------------------------------------------------------
def _client():
    from supabase import create_client
    return create_client(os.environ["SUPABASE_URL"],
                         os.environ["SUPABASE_SECRET_KEY"])


def _read_all(client, table: str, select: str = "*",
              filters: dict | None = None) -> pd.DataFrame:
    """Read a whole table with pagination (Supabase caps at 1000 rows/page)."""
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
    return pd.DataFrame(rows)


def score_run(label: str,
              normalization: str = "within_year",
              scoring_method: str | None = None,
              countries: list[str] | None = None,
              indicator_ids: list[int] | None = None,
              year_from: int | None = None,
              year_to: int | None = None,
              vintage: str | None = None,
              dry_run: bool = False) -> dict:
    """Compute and (unless dry_run) persist a scoring run. Returns a summary."""
    client = _client()

    factors = _read_all(client, "factor", "id,name")
    determinants = _read_all(client, "determinant", "id,factor_id,name")
    ind_filter = {"id": indicator_ids} if indicator_ids else None
    indicators = _read_all(client, "indicator",
                           "id,determinant_id,context,polarity,method,active",
                           ind_filter)
    indicators = indicators[indicators["active"]]

    obs_filter = {"indicator_id": indicators["id"].tolist()}
    if countries:
        obs_filter["country_iso3"] = countries
    observations = _read_all(client, "observation",
                             "indicator_id,country_iso3,year,raw_value", obs_filter)
    if year_from is not None:
        observations = observations[observations["year"] >= year_from]
    if year_to is not None:
        observations = observations[observations["year"] <= year_to]
    observations = observations.dropna(subset=["raw_value"])

    if observations.empty:
        raise RuntimeError("No observations matched the filters; nothing to score.")

    frame = build_scoring_frame(observations, indicators, determinants, factors)
    scores = compute_scores(frame, normalization=normalization,
                            method_override=scoring_method)
    scores = attach_determinant_ids(scores, frame)
    cov = coverage_report(frame, scores)

    summary = {
        "label": label,
        "normalization": normalization,
        "countries": sorted(frame["country"].unique().tolist()),
        "indicator_ids": sorted(indicators["id"].tolist()),
        "years": [int(frame["year"].min()), int(frame["year"].max())],
        "n_scores": int(len(scores)),
        "coverage": cov,
    }
    if dry_run:
        summary["run_id"] = None
        return summary

    run = client.table("run").insert({
        "label": label,
        "country_set": summary["countries"],
        "indicator_set": summary["indicator_ids"],
        "data_vintage": vintage,
    }).execute()
    run_id = run.data[0]["id"]

    payload = [{
        "run_id": run_id,
        "country_iso3": r.country,
        "year": int(r.year),
        "determinant_id": int(r.determinant_id),
        "context": r.context,
        "index": float(r["index"]),
        "n_indicators": int(r.n_indicators),
    } for _, r in scores.iterrows()]

    for i in range(0, len(payload), 500):
        client.table("score").insert(payload[i:i + 500]).execute()

    summary["run_id"] = run_id
    return summary


def _print_summary(s: dict) -> None:
    print(f"\nRun: {s['label']}  ({s['normalization']})")
    print(f"  countries : {len(s['countries'])}   years: {s['years'][0]}-{s['years'][1]}")
    print(f"  scores    : {s['n_scores']}   run_id: {s.get('run_id')}")
    print("\nCoverage (indicators defined vs. actually used per cell):")
    print(s["coverage"].to_string(index=False))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="DDD scoring job")
    p.add_argument("--label", required=True)
    p.add_argument("--normalization", choices=["within_year", "pooled"],
                   default="within_year")
    p.add_argument("--scoring-method",
                   choices=["ratio_max", "minmax", "percentile"],
                   help="override per-indicator method for the whole run "
                        "(percentile = fair ranks, recommended for many countries)")
    p.add_argument("--countries", nargs="*", help="ISO3 codes (default: all)")
    p.add_argument("--year-from", type=int)
    p.add_argument("--year-to", type=int)
    p.add_argument("--vintage")
    p.add_argument("--dry-run", action="store_true",
                   help="compute + report but do not write to Supabase")
    a = p.parse_args()
    _print_summary(score_run(
        label=a.label, normalization=a.normalization,
        scoring_method=a.scoring_method, countries=a.countries,
        year_from=a.year_from, year_to=a.year_to, vintage=a.vintage,
        dry_run=a.dry_run))
