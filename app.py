"""
DDD Platform - Streamlit app.

Reads pre-computed scores from Supabase (publishable key, read-only) and turns
them into an analysis a non-specialist can read: benchmarked diamonds, a
plain-language insights panel, and rankings across all countries.

Honesty layer (this version):
  * Missing data is drawn as a GAP, never as a zero. A corner with no
    international data shows an open grey circle at its domestic level.
  * Thin corners (engine-suppressed, or resting on a single criterion) carry
    an open orange diamond marker; hover shows the coverage counts.
  * The insights panel states international coverage explicitly and refuses
    to tell an "international linkages" story from a partial picture.
  * Years beyond MAX_DISPLAY_YEAR (forecast-only territory) are hidden.

Secrets (Streamlit Cloud -> app Settings -> Secrets, TOML):
    SUPABASE_URL = "https://xxxx.supabase.co"
    SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
"""

import os
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from supabase import create_client

st.set_page_config(page_title="DDD Competitiveness", layout="wide")

PHYS_ORDER = ["Factor Conditions", "Demand Conditions",
              "Related & Supporting Industries", "Firm Strategy, Structure & Rivalry"]
HUMAN_ORDER = ["Workers", "Politicians & Bureaucrats", "Entrepreneurs", "Professionals"]
BLUE, RED, GREY = "#1a5276", "#c0392b", "#7f8c8d"
AMBER = "#e67e22"          # thin-coverage marker

HONESTY_LAYER_VERSION = "1.1"   # bump on every change; used to verify deploys

# Scores exist out to 2031 in some runs, but a competitiveness "score" several
# forecast years out is not defensible for a policy/academic reader. Hide them.
MAX_DISPLAY_YEAR = 2026

# Full select includes the coverage columns score_run.py writes; the basic
# select is the fallback if those columns are unreadable for any reason.
SCORE_COLS_FULL = ("run_id,country_iso3,year,determinant_id,context,index,"
                   "n_indicators,n_sub_factors_present,n_sub_factors_expected,"
                   "coverage_suppressed")
SCORE_COLS_BASIC = "run_id,country_iso3,year,determinant_id,context,index,n_indicators"


@st.cache_resource
def _client():
    url = st.secrets.get("SUPABASE_URL", os.environ.get("SUPABASE_URL"))
    key = st.secrets.get("SUPABASE_PUBLISHABLE_KEY",
                         os.environ.get("SUPABASE_PUBLISHABLE_KEY"))
    if not url or not key:
        st.error("Missing SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY in secrets.")
        st.stop()
    return create_client(url, key)


@st.cache_data(ttl=600)
def _read(table: str, select: str = "*") -> pd.DataFrame:
    rows, start, page = [], 0, 1000
    cli = _client()
    while True:
        resp = cli.table(table).select(select).range(start, start + page - 1).execute()
        batch = resp.data or []
        rows.extend(batch)
        if len(batch) < page:
            break
        start += page
    return pd.DataFrame(rows)


def _read_scores() -> pd.DataFrame:
    """Read scores with coverage columns; degrade gracefully if absent."""
    try:
        df = _read("score", SCORE_COLS_FULL)
        if not df.empty and "coverage_suppressed" in df.columns:
            return df
    except Exception:
        pass
    df = _read("score", SCORE_COLS_BASIC)
    df["n_sub_factors_present"] = pd.NA
    df["n_sub_factors_expected"] = pd.NA
    df["coverage_suppressed"] = False
    return df


# ---------- pure helpers (no streamlit calls) ----------
def _order(factor_name):
    return PHYS_ORDER if factor_name == "physical" else HUMAN_ORDER


def _cov_text(row) -> str:
    """Human-readable coverage for one score row."""
    parts = []
    sp, se = row.get("n_sub_factors_present"), row.get("n_sub_factors_expected")
    if pd.notna(sp) and pd.notna(se):
        parts.append(f"{int(sp)} of {int(se)} sub-factors")
    n = row.get("n_indicators")
    if pd.notna(n):
        n = int(n)
        parts.append(f"{n} " + ("criterion" if n == 1 else "criteria"))
    return " · ".join(parts) if parts else "coverage unknown"


def _is_thin(row) -> bool:
    """Thin = flagged by the engine's coverage rule, or a single criterion."""
    supp = row.get("coverage_suppressed")
    if pd.notna(supp) and bool(supp):
        return True
    n = row.get("n_indicators")
    return pd.notna(n) and int(n) <= 1


def diamond_df(scores, determinants, factors, run_id, country, year, factor_name):
    """One country's diamond with coverage metadata.

    Missing corners stay NaN (gap), never 0. Columns per corner:
      dom, intl, intl_coord, dom_cov, intl_cov, dom_thin, intl_thin
    """
    fid = factors.loc[factors.name == factor_name, "id"].iloc[0]
    det = determinants[determinants.factor_id == fid][["id", "name"]]
    s = scores[(scores.run_id == run_id) & (scores.country_iso3 == country) &
               (scores.year == year)].merge(det, left_on="determinant_id", right_on="id")
    if s.empty:
        return None
    recs = []
    for name in _order(factor_name):
        rec = {"name": name}
        for ctx, pre in (("domestic", "dom"), ("international", "intl")):
            r = s[(s["name"] == name) & (s["context"] == ctx)]
            if r.empty:
                rec[pre] = float("nan")
                rec[pre + "_cov"] = "no data this year"
                rec[pre + "_thin"] = False
            else:
                row = r.iloc[0]
                rec[pre] = float(row["index"])
                rec[pre + "_cov"] = _cov_text(row)
                rec[pre + "_thin"] = _is_thin(row)
        recs.append(rec)
    piv = pd.DataFrame(recs).set_index("name")
    # NaN propagates on purpose: no international data -> no international
    # coordinate. A gap is a gap, not a zero.
    piv["intl_coord"] = piv["dom"] + piv["intl"]
    return piv


def benchmark_df(scores, determinants, factors, run_id, peers, year, factor_name):
    """Average diamond across a peer group. Peer means skip missing values
    per corner (a country without data does not drag the average to zero)."""
    fid = factors.loc[factors.name == factor_name, "id"].iloc[0]
    det = determinants[determinants.factor_id == fid][["id", "name"]]
    s = scores[(scores.run_id == run_id) & (scores.country_iso3.isin(peers)) &
               (scores.year == year)].merge(det, left_on="determinant_id", right_on="id")
    if s.empty:
        return None
    piv = (s.groupby(["name", "context"])["index"].mean().unstack("context")
            .reindex(_order(factor_name)))
    for col in ("domestic", "international"):
        if col not in piv.columns:
            piv[col] = float("nan")
    piv = piv.rename(columns={"domestic": "dom", "international": "intl"})
    piv["intl_coord"] = piv["dom"] + piv["intl"]
    return piv


def make_insights(piv, bench, country_name, peer_label):
    """Plain-language reading of one country's diamond vs its peer average,
    with the coverage picture stated up front."""
    lines = []
    dom = piv["dom"].dropna()
    if not dom.empty:
        strongest, weakest = dom.idxmax(), dom.idxmin()
        lines.append(f"**Strongest domestic determinant:** {strongest} "
                     f"({dom.max():.0f}). **Weakest:** {weakest} ({dom.min():.0f}).")

    n_corners = len(piv)
    covered = int(piv["intl"].notna().sum())
    if covered == 0:
        lines.append("**International coverage: none this year.** The chart shows "
                     "the domestic diamond only.")
    elif covered < n_corners:
        missing = ", ".join(piv.index[piv["intl"].isna()])
        lines.append(f"**International coverage: {covered} of {n_corners} corners.** "
                     f"No international data this year for: {missing}. Those corners "
                     f"are gaps, not zeros; the international shape is incomplete "
                     f"and should not be read as a full diamond.")

    # Only tell an "international linkages" story from a complete picture; on a
    # partial year the corner with data would win by default, an artifact of
    # coverage, not of economics.
    if covered == n_corners:
        gap = (piv["intl_coord"] - piv["dom"]).dropna()
        if not gap.empty and gap.max() > 0:
            intl_driver = gap.idxmax()
            lines.append(f"**Most reliant on international linkages:** {intl_driver}: "
                         f"its competitiveness here leans on foreign capital, trade, or "
                         f"global networks rather than the domestic base alone.")

    thin_bits = []
    for name in piv.index:
        if piv.loc[name, "dom_thin"]:
            thin_bits.append(f"{name} (domestic, {piv.loc[name, 'dom_cov']})")
        if piv.loc[name, "intl_thin"]:
            thin_bits.append(f"{name} (international, {piv.loc[name, 'intl_cov']})")
    if thin_bits:
        lines.append("**Thin corners, interpret with caution:** " +
                     "; ".join(thin_bits) + ".")

    if bench is not None:
        full = (covered == n_corners and piv["intl_coord"].notna().all()
                and bench["intl_coord"].notna().all())
        if full:
            c_avg, b_avg = piv["intl_coord"].mean(), bench["intl_coord"].mean()
            scope = "overall (domestic + international)"
        else:
            c_avg, b_avg = piv["dom"].mean(), bench["dom"].mean()
            scope = "domestic"
        if pd.notna(c_avg) and pd.notna(b_avg) and b_avg > 0:
            diff = (c_avg - b_avg) / b_avg * 100
            verb = "above" if diff >= 0 else "below"
            lines.append(f"**Versus the {peer_label} average:** {country_name} sits "
                         f"{abs(diff):.0f}% {verb} on {scope} competitiveness this year.")

    return "\n\n".join(lines) if lines else "_No data for this selection._"


def ranking_df(scores, determinants, names, run_id, year, determinant_name, context):
    did = determinants.loc[determinants.name == determinant_name, "id"].iloc[0]
    s = scores[(scores.run_id == run_id) & (scores.year == year) &
               (scores.determinant_id == did) & (scores.context == context)].copy()
    if s.empty:
        return None
    s = s.merge(names, left_on="country_iso3", right_on="iso3", how="left")
    s = s.sort_values("index", ascending=False).reset_index(drop=True)
    s["rank"] = s.index + 1
    s["coverage"] = s.apply(
        lambda r: "suppressed" if (pd.notna(r.get("coverage_suppressed"))
                                   and bool(r["coverage_suppressed"]))
        else ("single criterion" if pd.notna(r.get("n_indicators"))
              and int(r["n_indicators"]) <= 1 else "ok"), axis=1)
    return s[["rank", "country_iso3", "name", "index", "n_indicators", "coverage"]].rename(
        columns={"name": "country", "index": "score"})


def draw(piv, title, bench=None, bench_label="peer avg"):
    labels = list(piv.index)

    def _seq(frame, col):
        return [None if pd.isna(v) else float(v) for v in frame[col]]

    dom = _seq(piv, "dom")
    intl = _seq(piv, "intl_coord")
    dom_cov = list(piv["dom_cov"])
    intl_cov = list(piv["intl_cov"])
    n_intl = sum(v is not None for v in intl)

    vals = [v for v in dom + intl if v is not None]
    fig = go.Figure()

    if bench is not None:
        b = _seq(bench, "intl_coord")
        if all(v is None for v in b):          # peer group has no intl data
            b = _seq(bench, "dom")
        vals += [v for v in b if v is not None]
        b_gaps = any(v is None for v in b)
        fig.add_trace(go.Scatterpolar(
            r=b + [b[0]], theta=labels + [labels[0]], name=bench_label,
            line=dict(color=GREY, dash="dash"), fill=None, opacity=0.8,
            mode="lines+markers" if b_gaps else "lines",
            marker=dict(size=7, color=GREY),
            connectgaps=False,
            hovertemplate="%{theta}<br>" + bench_label + ": %{r:.0f}<extra></extra>"))

    if n_intl > 0:
        full = (n_intl == len(labels))
        fig.add_trace(go.Scatterpolar(
            r=intl + [intl[0]], theta=labels + [labels[0]],
            # a partial international shape gets no fill: it must not read as
            # a complete diamond. It also gets point markers: with gaps on both
            # sides, an isolated value has no line segments and would otherwise
            # be invisible.
            fill="toself" if full else None,
            mode="lines" if full else "lines+markers",
            marker=dict(size=8, color=RED),
            name=("International (dom+intl)" if full else
                  f"International (partial: {n_intl} of {len(labels)} corners)"),
            line=dict(color=RED, dash="dot"), connectgaps=False,
            customdata=intl_cov + [intl_cov[0]],
            hovertemplate="%{theta}<br>International: %{r:.0f}<br>%{customdata}<extra></extra>"))

    fig.add_trace(go.Scatterpolar(
        r=dom + [dom[0]], theta=labels + [labels[0]], fill="toself",
        name="Domestic", line=dict(color=BLUE), connectgaps=False,
        customdata=dom_cov + [dom_cov[0]],
        hovertemplate="%{theta}<br>Domestic: %{r:.0f}<br>%{customdata}<extra></extra>"))

    # explicit "no international data" markers, drawn at the domestic level so
    # the absence is visible instead of silently collapsing to zero
    if 0 < n_intl < len(labels):
        miss_t = [lab for lab, v, d in zip(labels, intl, dom)
                  if v is None and d is not None]
        miss_r = [d for v, d in zip(intl, dom) if v is None and d is not None]
        if miss_t:
            fig.add_trace(go.Scatterpolar(
                r=miss_r, theta=miss_t, mode="markers",
                name="no international data",
                # drawn larger than the thin marker so that when both flags
                # land on the same point they show as concentric rings
                marker=dict(symbol="circle-open", size=18, color=GREY,
                            line=dict(width=2)),
                hovertemplate="%{theta}<br>No international data this year, "
                              "a gap, not a zero.<extra></extra>"))

    # thin-coverage markers: engine-suppressed or single-criterion corners
    thin_t, thin_r, thin_txt = [], [], []
    for lab, d, is_thin, cov in zip(labels, dom, piv["dom_thin"], dom_cov):
        if is_thin and d is not None:
            thin_t.append(lab); thin_r.append(d)
            thin_txt.append("Domestic, thin coverage: " + cov)
    for lab, v, is_thin, cov in zip(labels, intl, piv["intl_thin"], intl_cov):
        if is_thin and v is not None:
            thin_t.append(lab); thin_r.append(v)
            thin_txt.append("International, thin coverage: " + cov)
    if thin_t:
        fig.add_trace(go.Scatterpolar(
            r=thin_r, theta=thin_t, mode="markers", name="thin coverage",
            marker=dict(symbol="diamond-open", size=11, color=AMBER,
                        line=dict(width=2)),
            customdata=thin_txt,
            hovertemplate="%{theta}<br>%{customdata}<extra></extra>"))

    rmax = max(vals + [1])
    fig.update_layout(title=title, height=470, margin=dict(t=60, b=20),
                      polar=dict(radialaxis=dict(visible=True, range=[0, rmax * 1.15])),
                      legend=dict(orientation="h", y=-0.12))
    return fig


# ---------------- data ----------------
runs = _read("run", "id,label,data_vintage,created_at")
if runs.empty:
    st.warning("No scoring runs found yet. Run `python -m ddd.score_run` to create one.")
    st.stop()
runs = runs.sort_values("created_at", ascending=False)
factors = _read("factor", "id,name")
determinants = _read("determinant", "id,factor_id,name")
scores = _read_scores()
scores = scores[scores["year"] <= MAX_DISPLAY_YEAR]
cmeta = _read("country", "iso3,name,region,is_emerging")
if cmeta.empty:
    cmeta = pd.DataFrame({"iso3": scores["country_iso3"].unique()})
    cmeta["name"] = cmeta["iso3"]; cmeta["region"] = "—"; cmeta["is_emerging"] = True
name_of = dict(zip(cmeta["iso3"], cmeta["name"]))

st.title("Dual Double Diamond Competitiveness")

# ---------------- sidebar ----------------
with st.sidebar:
    st.header("Selection")
    run_label = st.selectbox("Methodology run", runs["label"])
    run_id = int(runs.loc[runs.label == run_label, "id"].iloc[0])
    rs = scores[scores.run_id == run_id]
    # Default to the latest year whose INTERNATIONAL coverage is healthy, so the
    # dual diamond is meaningful. Frontier years (e.g. 2025) are thin on the
    # international side until sources publish.
    intl_counts = rs[rs.context == "international"].groupby("year").size()
    if not intl_counts.empty:
        well = intl_counts[intl_counts >= 0.5 * intl_counts.max()].index
    else:                                       # no international scores at all
        yc = rs.groupby("year").size()
        well = yc[yc >= 0.5 * yc.max()].index
    default_year = int(max(well)) if len(well) else int(rs["year"].max())
    years = sorted(rs["year"].unique())
    year = st.selectbox("Year", years, index=years.index(default_year))
    factor_name = st.radio("Diamond", ["physical", "human"], horizontal=True)
    avail = sorted(rs[rs.year == year]["country_iso3"].unique())
    fmt = lambda i: f"{name_of.get(i, i)} ({i})"
    c1 = st.selectbox("Country", avail, format_func=fmt)
    c2 = st.selectbox("Compare with (optional)", ["(none)"] + avail, format_func=lambda i: "(none)" if i == "(none)" else fmt(i))
    peer_choice = st.selectbox("Benchmark against",
                               ["Region", "All emerging", "All developed", "All countries"])

# resolve peer set
def peers_for(iso):
    row = cmeta[cmeta.iso3 == iso]
    if peer_choice == "Region" and not row.empty:
        reg = row["region"].iloc[0]
        return cmeta[cmeta.region == reg]["iso3"].tolist(), f"{reg} region"
    if peer_choice == "All emerging":
        return cmeta[cmeta.is_emerging]["iso3"].tolist(), "emerging-economy"
    if peer_choice == "All developed":
        return cmeta[~cmeta.is_emerging]["iso3"].tolist(), "developed-economy"
    return cmeta["iso3"].tolist(), "all-country"

tab1, tab2 = st.tabs(["Country profile", "Rankings"])

with tab1:
    peers, peer_label = peers_for(c1)
    bench = benchmark_df(scores, determinants, factors, run_id, peers, year, factor_name)
    year_intl = scores[(scores.run_id == run_id) & (scores.year == year) &
                       (scores.context == "international")]
    if year_intl.empty:
        st.info(f"**{year} is domestic-only.** International determinants (trade, FDI, "
                f"exports, migration, knowledge flows) come from sources that currently "
                f"publish through 2024, so {year} shows the domestic diamond alone. "
                f"Select 2024 or earlier for the full dual diamond.")
    col1, col2 = st.columns(2)
    with col1:
        piv1 = diamond_df(scores, determinants, factors, run_id, c1, year, factor_name)
        if piv1 is None:
            st.info(f"No {factor_name} scores for {name_of.get(c1,c1)} in {year}.")
        else:
            st.plotly_chart(draw(piv1, f"{name_of.get(c1,c1)}, {year}", bench, f"{peer_label} avg"),
                            use_container_width=True)
    with col2:
        if c2 != "(none)":
            piv2 = diamond_df(scores, determinants, factors, run_id, c2, year, factor_name)
            if piv2 is None:
                st.info(f"No {factor_name} scores for {name_of.get(c2,c2)} in {year}.")
            else:
                p2, l2 = peers_for(c2)
                b2 = benchmark_df(scores, determinants, factors, run_id, p2, year, factor_name)
                st.plotly_chart(draw(piv2, f"{name_of.get(c2,c2)}, {year}", b2, f"{l2} avg"),
                                use_container_width=True)
        else:
            st.caption("Pick a second country in the sidebar to compare side by side.")

    st.subheader("What this shows")
    if piv1 is not None:
        st.markdown(make_insights(piv1, bench, name_of.get(c1, c1), peer_label))
    st.caption("Solid = domestic determinants · dotted = adding international linkages · "
               "dashed grey = peer-group average · open grey circle = no international "
               "data (a gap, not a zero) · open orange diamond = thin coverage (single "
               "criterion or below the sub-factor threshold). Higher = more competitive "
               "relative to the country set.")

with tab2:
    st.subheader("Rankings across all countries")
    rcol1, rcol2 = st.columns(2)
    det_names = (PHYS_ORDER if factor_name == "physical" else HUMAN_ORDER)
    rdet = rcol1.selectbox("Determinant", det_names)
    rctx = rcol2.selectbox("Context", ["domestic", "international"])
    rk = ranking_df(scores, determinants, cmeta[["iso3", "name"]], run_id, year, rdet, rctx)
    if rk is None:
        st.info("No data for this selection.")
    else:
        n_flagged = int((rk["coverage"] != "ok").sum())
        if n_flagged:
            st.caption(f"⚠️ {n_flagged} of {len(rk)} countries in this ranking rest on "
                       f"thin coverage (see the coverage column). Ranks built on a "
                       f"single criterion are fragile.")
        top = rk.head(15)
        fig = go.Figure(go.Bar(x=top["score"], y=top["country"], orientation="h",
                               marker_color=BLUE, text=top["score"].round(0)))
        fig.update_layout(height=460, yaxis=dict(autorange="reversed"),
                          margin=dict(t=20, b=20), xaxis_title="score")
        st.plotly_chart(fig, use_container_width=True)
        if c1 in rk["country_iso3"].values:
            r = rk[rk.country_iso3 == c1]["rank"].iloc[0]
            st.markdown(f"**{name_of.get(c1,c1)}** ranks **#{int(r)} of {len(rk)}** "
                        f"on {rdet} ({rctx}) in {year}.")
        st.dataframe(rk, use_container_width=True, hide_index=True)
