"""
DDD Platform - Streamlit app.

Reads pre-computed scores from Supabase (publishable key, read-only) and turns
them into an analysis a non-specialist can read: benchmarked diamonds, a
plain-language insights panel, and rankings across all countries.

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


# ---------- pure helpers (no streamlit calls) ----------
def _order(factor_name):
    return PHYS_ORDER if factor_name == "physical" else HUMAN_ORDER


def diamond_df(scores, determinants, factors, run_id, country, year, factor_name):
    fid = factors.loc[factors.name == factor_name, "id"].iloc[0]
    det = determinants[determinants.factor_id == fid][["id", "name"]]
    s = scores[(scores.run_id == run_id) & (scores.country_iso3 == country) &
               (scores.year == year)].merge(det, left_on="determinant_id", right_on="id")
    if s.empty:
        return None
    piv = s.pivot_table(index="name", columns="context", values="index").reindex(_order(factor_name))
    piv = piv.rename(columns={"domestic": "dom", "international": "intl"})
    for col in ("dom", "intl"):
        if col not in piv.columns:
            piv[col] = 0.0
    piv = piv.fillna(0.0)
    piv["intl_coord"] = piv["dom"] + piv["intl"]
    return piv


def benchmark_df(scores, determinants, factors, run_id, peers, year, factor_name):
    """Average diamond across a peer group (list of iso3)."""
    fid = factors.loc[factors.name == factor_name, "id"].iloc[0]
    det = determinants[determinants.factor_id == fid][["id", "name"]]
    s = scores[(scores.run_id == run_id) & (scores.country_iso3.isin(peers)) &
               (scores.year == year)].merge(det, left_on="determinant_id", right_on="id")
    if s.empty:
        return None
    piv = (s.groupby(["name", "context"])["index"].mean().unstack("context")
            .reindex(_order(factor_name)))
    piv = piv.rename(columns={"domestic": "dom", "international": "intl"})
    for col in ("dom", "intl"):
        if col not in piv.columns:
            piv[col] = 0.0
    piv = piv.fillna(0.0)
    piv["intl_coord"] = piv["dom"] + piv["intl"]
    return piv


def make_insights(piv, bench, country_name, peer_label):
    """Plain-language reading of one country's diamond vs its peer average."""
    dom = piv["dom"][piv["dom"] > 0]
    lines = []
    if not dom.empty:
        strongest = dom.idxmax()
        weakest = dom.idxmin()
        lines.append(f"**Strongest domestic determinant:** {strongest} "
                     f"({dom.max():.0f}). **Weakest:** {weakest} ({dom.min():.0f}).")
    gap = (piv["intl_coord"] - piv["dom"])
    if gap.max() > 0:
        intl_driver = gap.idxmax()
        lines.append(f"**Most reliant on international linkages:** {intl_driver} — "
                     f"its competitiveness here leans on foreign capital, trade, or "
                     f"global networks rather than the domestic base alone.")
    if bench is not None:
        c_avg = piv["intl_coord"].mean()
        b_avg = bench["intl_coord"].mean()
        if b_avg > 0:
            diff = (c_avg - b_avg) / b_avg * 100
            verb = "above" if diff >= 0 else "below"
            lines.append(f"**Versus the {peer_label} average:** {country_name} sits "
                         f"{abs(diff):.0f}% {verb} on overall (domestic + international) "
                         f"competitiveness this year.")
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
    return s[["rank", "country_iso3", "name", "index", "n_indicators"]].rename(
        columns={"name": "country", "index": "score"})


def draw(piv, title, bench=None, bench_label="peer avg"):
    labels = list(piv.index)
    dom, intl = list(piv["dom"]), list(piv["intl_coord"])
    fig = go.Figure()
    rmax = max(intl + [1])
    if bench is not None:
        b = list(bench["intl_coord"])
        rmax = max(rmax, max(b + [1]))
        fig.add_trace(go.Scatterpolar(r=b + [b[0]], theta=labels + [labels[0]],
                      name=f"{bench_label}", line=dict(color=GREY, dash="dash"),
                      fill=None, opacity=0.8))
    fig.add_trace(go.Scatterpolar(r=intl + [intl[0]], theta=labels + [labels[0]],
                  fill="toself", name="International (dom+intl)",
                  line=dict(color=RED, dash="dot")))
    fig.add_trace(go.Scatterpolar(r=dom + [dom[0]], theta=labels + [labels[0]],
                  fill="toself", name="Domestic", line=dict(color=BLUE)))
    fig.update_layout(title=title, height=460, margin=dict(t=60, b=20),
                      polar=dict(radialaxis=dict(visible=True, range=[0, rmax * 1.15])),
                      legend=dict(orientation="h", y=-0.1))
    return fig


# ---------------- data ----------------
runs = _read("run", "id,label,data_vintage,created_at")
if runs.empty:
    st.warning("No scoring runs found yet. Run `python -m ddd.score_run` to create one.")
    st.stop()
runs = runs.sort_values("created_at", ascending=False)
factors = _read("factor", "id,name")
determinants = _read("determinant", "id,factor_id,name")
scores = _read("score", "run_id,country_iso3,year,determinant_id,context,index,n_indicators")
cmeta = _read("country", "iso3,name,region,is_emerging")
if cmeta.empty:
    cmeta = pd.DataFrame({"iso3": scores["country_iso3"].unique()})
    cmeta["name"] = cmeta["iso3"]; cmeta["region"] = "—"; cmeta["is_emerging"] = True
name_of = dict(zip(cmeta["iso3"], cmeta["name"]))

st.title("Dual Double Diamond — Competitiveness")

# ---------------- sidebar ----------------
with st.sidebar:
    st.header("Selection")
    run_label = st.selectbox("Methodology run", runs["label"])
    run_id = int(runs.loc[runs.label == run_label, "id"].iloc[0])
    rs = scores[scores.run_id == run_id]
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
    col1, col2 = st.columns(2)
    with col1:
        piv1 = diamond_df(scores, determinants, factors, run_id, c1, year, factor_name)
        if piv1 is None:
            st.info(f"No {factor_name} scores for {name_of.get(c1,c1)} in {year}.")
        else:
            st.plotly_chart(draw(piv1, f"{name_of.get(c1,c1)} — {year}", bench, f"{peer_label} avg"),
                            use_container_width=True)
    with col2:
        if c2 != "(none)":
            piv2 = diamond_df(scores, determinants, factors, run_id, c2, year, factor_name)
            if piv2 is None:
                st.info(f"No {factor_name} scores for {name_of.get(c2,c2)} in {year}.")
            else:
                p2, l2 = peers_for(c2)
                b2 = benchmark_df(scores, determinants, factors, run_id, p2, year, factor_name)
                st.plotly_chart(draw(piv2, f"{name_of.get(c2,c2)} — {year}", b2, f"{l2} avg"),
                                use_container_width=True)
        else:
            st.caption("Pick a second country in the sidebar to compare side by side.")

    st.subheader("What this shows")
    if piv1 is not None:
        st.markdown(make_insights(piv1, bench, name_of.get(c1, c1), peer_label))
    st.caption("Solid = domestic determinants · dotted = adding international linkages · "
               "dashed grey = peer-group average. Higher = more competitive relative to "
               "the country set.")

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
