"""
Validation: reproduce Moon, Rugman & Verbeke (1998), Int'l Business Review 7.

We load the published raw inputs (their Tables 2 & 3), run them through our
scoring engine, and assert the output matches their Table 4 (the competitive
indices) within rounding tolerance. Then we render the two diamonds.

If this passes, the engine's math is a faithful implementation of the model.
"""

from __future__ import annotations
import sys, os
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ddd.scoring import compute_scores, diamond_coordinates  # noqa: E402

# --- Published raw inputs: Table 2 (domestic) + Table 3 (international) -------
# columns: factor, context, determinant, indicator, polarity, Korea, Singapore
FIXTURE = [
    # Factor Conditions
    ("physical", "domestic", "Factor Conditions", "Wages in manufacturing (USA=100)", "+", 37.0, 37.0),
    ("physical", "domestic", "Factor Conditions", "Scientists & technicians /1000", "+", 45.9, 22.9),
    ("physical", "international", "Factor Conditions", "Outbound FDI per capita ($)", "+", 56.7, 743.0),
    ("physical", "international", "Factor Conditions", "Inbound FDI per capita ($)", "+", 18.2, 1907.2),
    # Demand Conditions
    ("physical", "domestic", "Demand Conditions", "Avg annual growth (%)", "+", 8.2, 6.1),
    ("physical", "domestic", "Demand Conditions", "Education index", "+", 2.6, 2.1),
    ("physical", "international", "Demand Conditions", "Export dependency (% GNP)", "+", 25.5, 140.5),
    ("physical", "international", "Demand Conditions", "Export diversification (% excl. top 3)", "+", 53.5, 58.6),
    # Related & Supporting Industries
    ("physical", "domestic", "Related & Supporting Industries", "Paved roads (km/mn persons)", "+", 1090.0, 993.0),
    ("physical", "domestic", "Related & Supporting Industries", "Telephones per 100", "+", 41.4, 39.2),
    ("physical", "international", "Related & Supporting Industries", "Good air transport (% agreed)", "+", 70.6, 97.8),
    ("physical", "international", "Related & Supporting Industries", "Intl telex traffic (min/capita)", "+", 0.2, 7.7),
    # Firm Strategy, Structure & Rivalry
    ("physical", "domestic", "Firm Strategy, Structure & Rivalry", "Unequal treatment of foreigners (% agreed)", "+", 43.7, 37.2),
    ("physical", "international", "Firm Strategy, Structure & Rivalry", "Openness to foreign products (% agreed)", "+", 57.5, 87.7),
]

# --- Published expected output: Table 4 --------------------------------------
EXPECTED = {  # (determinant, context): {country: index}
    ("Factor Conditions", "domestic"):                  {"Korea": 100.0, "Singapore": 75.0},
    ("Factor Conditions", "international"):              {"Korea": 4.3,   "Singapore": 100.0},
    ("Demand Conditions", "domestic"):                  {"Korea": 100.0, "Singapore": 77.6},
    ("Demand Conditions", "international"):              {"Korea": 54.7,  "Singapore": 100.0},
    ("Related & Supporting Industries", "domestic"):     {"Korea": 100.0, "Singapore": 92.9},
    ("Related & Supporting Industries", "international"): {"Korea": 37.4,  "Singapore": 100.0},
    ("Firm Strategy, Structure & Rivalry", "domestic"):  {"Korea": 100.0, "Singapore": 85.1},
    ("Firm Strategy, Structure & Rivalry", "international"): {"Korea": 65.6, "Singapore": 100.0},
}


def build_long_df() -> pd.DataFrame:
    rows = []
    for factor, context, det, ind, pol, kr, sg in FIXTURE:
        rows.append((("Korea"), factor, context, det, ind, kr, pol))
        rows.append((("Singapore"), factor, context, det, ind, sg, pol))
    return pd.DataFrame(rows, columns=["country", "factor", "context",
                                       "determinant", "indicator",
                                       "raw_value", "polarity"])


def main() -> int:
    scores = compute_scores(build_long_df())

    print("=" * 64)
    print("VALIDATION: Korea vs Singapore (Moon, Rugman & Verbeke 1998)")
    print("=" * 64)
    print(f"{'Determinant / context':46} {'KR':>6} {'SG':>6}")
    print("-" * 64)

    tol = 0.15  # rounding tolerance vs the paper's 1-decimal table
    failures = 0
    for (det, ctx), exp in EXPECTED.items():
        for country in ("Korea", "Singapore"):
            got = scores[(scores.country == country) &
                         (scores.determinant == det) &
                         (scores.context == ctx)]["index"].iloc[0]
            want = exp[country]
            ok = abs(got - want) <= tol
            failures += 0 if ok else 1
            if country == "Korea":
                kr_got, kr_want, kr_ok = got, want, ok
            else:
                flag = "ok" if (ok and kr_ok) else "FAIL"
                label = f"{det[:30]} [{ctx[:4]}]"
                print(f"{label:46} {kr_got:6.1f} {got:6.1f}   "
                      f"(exp {kr_want:.1f}/{want:.1f}) {flag}")

    print("-" * 64)
    if failures == 0:
        print("PASS - engine reproduces all 16 published indices.")
    else:
        print(f"FAIL - {failures} index/indices off by > {tol}")

    # diamond coordinates (domestic solid / international dotted)
    print("\nDiamond coordinates (international = domestic + international):")
    for country in ("Korea", "Singapore"):
        coords = diamond_coordinates(scores, country, "physical")
        print(f"\n{country}:")
        print(coords.to_string(index=False,
              formatters={"domestic_coord": "{:.1f}".format,
                          "international_coord": "{:.1f}".format}))

    scores.to_csv(os.path.join(os.path.dirname(__file__),
                  "korea_singapore_scores.csv"), index=False)
    return failures


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
