"""
DDD Platform - Streamlit app (MVP).

Reads pre-computed scores from Supabase (publishable key, read-only) and draws
the overlaid domestic/international diamonds. No scoring happens here — the app
only reads `run`, `score`, `determinant`, `factor`. Compute lives in the
scheduled job (ddd/score_run.py).

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


def diamond_df(scores, determinants, factors, run_id, country, year, factor_name):
    order = PHYS_ORDER if factor_name == "physical" else HUMAN_ORDER
    fid = factors.loc[factors.name == factor_name, "id"].iloc[0]
    det = determinants[determinants.factor_id == fid][["id", "name"]]
    s = scores[(scores.run_id == run_id) & (scores.country_iso3 == country) &
               (scores.year == year)].merge(det, left_on="determinant_id", right_on="id")
    piv = s.pivot_table(index="name", columns="context", values="index").reindex(order)
    piv = piv.rename(columns={"domestic": "dom", "international": "intl"}).fillna(0.0)
    piv["intl_coord"] = piv["dom"] + piv.get("intl", 0.0)
    return piv


def draw(piv, title):
    labels = list(piv.index)
    dom = list(piv["dom"])
    intl = list(piv["intl_coord"])
    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(r=intl + [intl[0]], theta=labels + [labels[0]],
                  fill="toself", name="International (dom+intl)",
                  line=dict(color="#c0392b", dash="dot")))
    fig.add_trace(go.Scatterpolar(r=dom + [dom[0]], theta=labels + [labels[0]],
                  fill="toself", name="Domestic", line=dict(color="#1a5276")))
    fig.update_layout(title=title, polar=dict(radialaxis=dict(visible=True, range=[0, 200])),
                      showlegend=True, height=480, margin=dict(t=60, b=20))
    return fig


# ---------------- UI ----------------
st.title("Dual Double Diamond — Competitiveness")

runs = _read("run", "id,label,data_vintage,created_at")
if runs.empty:
    st.warning("No scoring runs found yet. Run `python -m ddd.score_run` to create one.")
    st.stop()

runs = runs.sort_values("created_at", ascending=False)
factors = _read("factor", "id,name")
determinants = _read("determinant", "id,factor_id,name")
scores = _read("score", "run_id,country_iso3,year,determinant_id,context,index,n_indicators")

with st.sidebar:
    st.header("Selection")
    run_label = st.selectbox("Methodology run", runs["label"])
    run_id = int(runs.loc[runs.label == run_label, "id"].iloc[0])
    rs = scores[scores.run_id == run_id]
    years = sorted(rs["year"].unique())
    year = st.selectbox("Year", years, index=len(years) - 1)
    factor_name = st.radio("Diamond", ["physical", "human"], horizontal=True)
    countries = sorted(rs[rs.year == year]["country_iso3"].unique())
    c1 = st.selectbox("Country", countries, index=0)
    c2 = st.selectbox("Compare with (optional)", ["(none)"] + countries, index=0)

col1, col2 = st.columns(2)
with col1:
    piv1 = diamond_df(scores, determinants, factors, run_id, c1, year, factor_name)
    st.plotly_chart(draw(piv1, f"{c1} — {year}"), use_container_width=True)
    st.caption(f"Indicators feeding each corner — domestic vs. international. "
               f"Vintage: {runs.loc[runs.id==run_id,'data_vintage'].iloc[0]}")
if c2 != "(none)":
    with col2:
        piv2 = diamond_df(scores, determinants, factors, run_id, c2, year, factor_name)
        st.plotly_chart(draw(piv2, f"{c2} — {year}"), use_container_width=True)

st.subheader("Scores")
view = (scores[(scores.run_id == run_id) & (scores.year == year) &
        (scores.country_iso3.isin([c1] + ([c2] if c2 != "(none)" else [])))]
        .merge(determinants[["id", "name"]], left_on="determinant_id", right_on="id"))
st.dataframe(view[["country_iso3", "name", "context", "index", "n_indicators"]]
             .rename(columns={"name": "determinant"}), use_container_width=True, hide_index=True)
