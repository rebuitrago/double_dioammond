"""
Dual Double Diamond - scoring engine.

Pure functions, no I/O. Given a tidy table of (country, factor, context,
determinant, indicator, raw_value, polarity, method), it produces the
competitiveness indices and the diamond coordinates.

The default normalization ('ratio_max') reproduces Moon, Rugman & Verbeke
(1998): the top country on an indicator scores 100, the rest get their
proportion. Ties at the top both score 100.

'minmax' is provided for indicators that can be negative or have no
meaningful zero (e.g. World Bank Governance estimates ~ -2.5..+2.5), where
the ratio method is undefined.
"""

from __future__ import annotations
import pandas as pd

# Canonical order of the four physical-diamond corners (axis order for plots).
PHYSICAL_DETERMINANTS = [
    "Factor Conditions",
    "Demand Conditions",
    "Related & Supporting Industries",
    "Firm Strategy, Structure & Rivalry",
]
HUMAN_DETERMINANTS = [
    "Workers",
    "Politicians & Bureaucrats",
    "Entrepreneurs",
    "Professionals",
]


def normalize_indicator(values: dict[str, float], polarity: str = "+",
                        method: str = "ratio_max") -> dict[str, float]:
    """Normalize one indicator across the country set to a 0-100 scale.

    values   : {country_iso3: raw_value}
    polarity : '+' higher-is-better, '-' lower-is-better
    method   : 'ratio_max' (paper) or 'minmax'
    """
    vals = {c: v for c, v in values.items() if v is not None}
    if not vals:
        return {}

    if method == "minmax":
        lo, hi = min(vals.values()), max(vals.values())
        span = hi - lo
        if span == 0:
            return {c: 100.0 for c in vals}
        scored = {c: (v - lo) / span * 100 for c, v in vals.items()}
        if polarity == "-":
            scored = {c: 100 - s for c, s in scored.items()}
        return scored

    if method == "percentile":
        # rank among the country set: 100 = best, ~0 = worst, 50 = median.
        # handles negatives naturally and spreads scores evenly.
        s = pd.Series(vals, dtype=float)
        if polarity == "-":
            s = -s
        return (s.rank(pct=True) * 100.0).to_dict()

    # ratio_max (paper's method)
    if polarity == "-":
        # best = smallest; best scores 100, others = best/value * 100
        best = min(vals.values())
        return {c: (best / v * 100 if v != 0 else 100.0) for c, v in vals.items()}
    mx = max(vals.values())
    if mx == 0:
        return {c: 0.0 for c in vals}
    return {c: v / mx * 100 for c, v in vals.items()}


def compute_scores(df: pd.DataFrame,
                   normalization: str = "within_year",
                   method_override: str | None = None) -> pd.DataFrame:
    """Compute determinant-level competitiveness indices.

    Expected columns:
        country, factor (physical|human), context (domestic|international),
        determinant, indicator, raw_value, polarity, method
    Optional:
        year  -- if present, scores are produced per country-year.

    normalization (only relevant when `year` is present):
        'within_year' -- each year normalized independently (top country that
                         year = 100). Good for rankings; the frontier moves.
        'pooled'      -- normalized across all country-years together (best
                         value anywhere in the panel = 100). Good for trends;
                         scores are comparable across years.

    `polarity` and `method` are optional (default '+' / 'ratio_max').

    Returns one row per (country, [year,] factor, context, determinant) with the
    averaged index and the number of indicators that fed it.
    """
    d = df.copy()
    if "polarity" not in d.columns:
        d["polarity"] = "+"
    if "method" not in d.columns:
        d["method"] = "ratio_max"
    d["polarity"] = d["polarity"].fillna("+")
    d["method"] = d["method"].fillna("ratio_max")
    if method_override:                       # force one method for the whole run
        d["method"] = method_override

    has_year = "year" in d.columns

    # 1) normalize each indicator across countries.
    #    within_year -> the per-year country set; pooled -> all country-years.
    norm_keys = ["factor", "context", "determinant", "indicator"]
    if has_year and normalization == "within_year":
        norm_keys = norm_keys + ["year"]

    rows = []
    for key_vals, g in d.groupby(norm_keys):
        polarity = g["polarity"].iloc[0]
        method = g["method"].iloc[0]
        # in pooled mode, a country competes across all its years at once
        if has_year and normalization == "pooled":
            keys = list(zip(g["country"], g["year"]))
        else:
            keys = list(g["country"]) if not has_year else list(zip(g["country"], g["year"]))
        values = dict(zip(keys, g["raw_value"]))
        scored = normalize_indicator(values, polarity, method)
        gkey = dict(zip(norm_keys, key_vals if isinstance(key_vals, tuple) else (key_vals,)))
        for k, s in scored.items():
            if has_year:
                country, year = k
            else:
                country, year = k, None
            rows.append((country, year, gkey["factor"], gkey["context"],
                         gkey["determinant"], gkey["indicator"], s))

    norm = pd.DataFrame(rows, columns=["country", "year", "factor", "context",
                                       "determinant", "indicator", "index"])
    if not has_year:
        norm = norm.drop(columns=["year"])

    # 2) average indicators -> determinant score (equal weight per indicator)
    grp = ["country", "factor", "context", "determinant"]
    if has_year:
        grp = ["country", "year", "factor", "context", "determinant"]
    scores = (norm.groupby(grp)
                  .agg(index=("index", "mean"), n_indicators=("indicator", "nunique"))
                  .reset_index())
    return scores


def diamond_coordinates(scores: pd.DataFrame, country: str,
                        factor: str = "physical") -> pd.DataFrame:
    """Return the two diamonds for one country/factor.

    domestic_coord     = domestic index
    international_coord = domestic index + international index
                         (the paper's construction; the gap is the
                         multinational contribution)
    """
    order = PHYSICAL_DETERMINANTS if factor == "physical" else HUMAN_DETERMINANTS
    sub = scores[(scores.country == country) & (scores.factor == factor)]
    piv = sub.pivot_table(index="determinant", columns="context",
                          values="index").reindex(order)
    piv = piv.rename(columns={"domestic": "dom", "international": "intl"})
    piv["dom"] = piv["dom"].fillna(0.0)
    piv["intl"] = piv["intl"].fillna(0.0)
    out = pd.DataFrame({
        "determinant": piv.index,
        "domestic_coord": piv["dom"],
        "international_coord": piv["dom"] + piv["intl"],
    }).reset_index(drop=True)
    return out
