from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from trendwatcher.demo_data import demo_articles
from trendwatcher.pipeline import run_pipeline, save_outputs
from trendwatcher.rss import DEFAULT_RSS_SOURCES, fetch_rss_articles


st.set_page_config(page_title="Fintech TrendWatcher", layout="wide")

st.markdown(
    """
    <style>
    :root {
      --border: #d8dee7;
      --muted: #5f6b7a;
      --panel: #f7f9fb;
      --ink: #18202a;
      --accent: #0b6bcb;
    }
    .block-container { padding-top: 1.4rem; }
    .metric-row [data-testid="stMetric"] {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 14px;
    }
    .signal-card {
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 14px 16px;
      margin: 0 0 12px 0;
      background: #ffffff;
    }
    .signal-card h3 {
      font-size: 1rem;
      margin: 0 0 8px 0;
      color: var(--ink);
      letter-spacing: 0;
    }
    .small-muted { color: var(--muted); font-size: 0.88rem; }
    .chip {
      display: inline-block;
      border: 1px solid var(--border);
      border-radius: 999px;
      padding: 2px 8px;
      margin: 0 4px 4px 0;
      font-size: 0.78rem;
      color: #263241;
      background: #f9fbfd;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_uploaded_csv(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    return pd.read_csv(uploaded_file)


def render_signal_card(signal: dict) -> None:
    components = signal["score_components"]
    tags = "".join(f'<span class="chip">{tag}</span>' for tag in signal.get("tags", [])[:7])
    source_links = "<br>".join(
        f'<a href="{src["url"]}" target="_blank">{src["source"]}</a> · quality {src["quality"]}'
        for src in signal.get("sources", [])[:4]
    )
    st.markdown(
        f"""
        <div class="signal-card">
          <h3>{signal["headline"]}</h3>
          <div class="small-muted">Hotness {signal["hotness"]}/5 · Score {signal["score"]}/100 · {signal["category"]}</div>
          <div style="margin-top:8px;">{tags}</div>
          <p><b>Why now:</b> {signal["why_now"]}</p>
          <p><b>Summary:</b> {signal["summary"]}</p>
          <p><b>Suggested action:</b> {signal["suggested_action"]}</p>
          <p class="small-muted">
            relevance {components["relevance"]} · source quality {components["source_quality"]} ·
            novelty {components["novelty"]} · impact {components["impact"]} ·
            evidence {components["evidence_count"]} · confidence {components["confidence"]}
          </p>
          <p class="small-muted"><b>Sources</b><br>{source_links}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


with st.sidebar:
    st.header("Run settings")
    data_source = st.radio("Input", ["Demo dataset", "Upload CSV", "RSS sample"], index=0)
    uploaded = st.file_uploader("CSV columns: title, url, source, published_at, snippet, text", type=["csv"])
    top_n = st.slider("Signals in digest", 3, 10, 7)
    use_llm = st.toggle("Use OpenRouter enrichment", value=False)
    max_llm_items = st.slider("Max LLM-enriched signals", 1, 12, 6, disabled=not use_llm)
    api_key = st.text_input("OpenRouter API key", type="password", value=os.getenv("OPENROUTER_API_KEY", ""))
    model = st.text_input("Model", value=os.getenv("OPENROUTER_MODEL", "openai/gpt-5-nano"), disabled=not use_llm)
    run_clicked = st.button("Run pipeline", type="primary", width="stretch")

    st.divider()
    st.caption("RSS mode needs internet. Demo mode is deterministic and best for the hackathon defense.")


st.title("Fintech TrendWatcher")
st.caption("Raw fintech publications -> noise filtering -> deduplication -> importance scoring -> digest")

if api_key:
    os.environ["OPENROUTER_API_KEY"] = api_key
if model:
    os.environ["OPENROUTER_MODEL"] = model

if "result" not in st.session_state or run_clicked:
    if data_source == "Upload CSV":
        articles = load_uploaded_csv(uploaded)
        if articles is None:
            st.warning("Upload a CSV or switch back to demo dataset.")
            st.stop()
    elif data_source == "RSS sample":
        with st.spinner("Fetching RSS sources..."):
            articles = pd.DataFrame(fetch_rss_articles(DEFAULT_RSS_SOURCES, limit_per_source=15))
        if articles.empty:
            st.warning("RSS fetch returned no articles. Using demo dataset instead.")
            articles = pd.DataFrame(demo_articles())
    else:
        articles = pd.DataFrame(demo_articles())

    with st.spinner("Running transparent pipeline..."):
        result = run_pipeline(articles=articles, use_llm=use_llm, max_llm_items=max_llm_items, top_n=top_n)
        save_outputs(result, "data")
        st.session_state["result"] = result

result = st.session_state["result"]

st.markdown('<div class="metric-row">', unsafe_allow_html=True)
m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Raw articles", len(result.raw_articles))
m2.metric("Candidates", len(result.candidate_articles))
m3.metric("Rejected noise", len(result.rejected_articles))
m4.metric("Signals", len(result.signals))
avg_score = round(sum(s["score"] for s in result.signals) / max(1, len(result.signals)), 1)
m5.metric("Avg signal score", avg_score)
st.markdown("</div>", unsafe_allow_html=True)

pipeline_tab, signals_tab, digest_tab, rejected_tab, prompts_tab = st.tabs(
    ["Pipeline", "Signals", "Digest", "Rejected Noise", "Prompts"]
)

with pipeline_tab:
    st.subheader("Pipeline trace")
    st.write(
        "The prototype keeps the logic inspectable: cheap code filters first, dedup groups second, "
        "optional LLM enrichment only after candidates are selected."
    )
    st.code(
        "ingest -> normalize metadata -> rule filter -> fuzzy dedup -> hybrid score -> ranked digest",
        language="text",
    )
    st.markdown("**Scoring formula**")
    st.code(
        "score = 0.30*relevance + 0.20*source_quality + 0.20*novelty + 0.15*impact + 0.15*evidence_count",
        language="text",
    )

    st.markdown("**Candidate articles after filtering and clustering**")
    candidate_cols = [
        "cluster_id",
        "title",
        "source",
        "published_at",
        "detected_category",
        "relevance",
        "source_quality",
        "canonical_url",
    ]
    st.dataframe(result.candidate_articles[candidate_cols], width="stretch", hide_index=True)

    st.markdown("**Dedup groups**")
    dedup_rows = []
    for signal in result.signals:
        dedup_rows.append(
            {
                "signal_id": signal["id"],
                "headline": signal["headline"],
                "articles_grouped": len(signal["article_ids"]),
                "unique_sources": len(signal["sources"]),
                "deduped_titles": " | ".join(signal["deduped_titles"][:4]),
            }
        )
    st.dataframe(pd.DataFrame(dedup_rows), width="stretch", hide_index=True)

with signals_tab:
    st.subheader("Ranked signal cards")
    for signal in result.signals[:top_n]:
        render_signal_card(signal)

    signals_json = json.dumps(result.signals, ensure_ascii=False, indent=2)
    st.download_button("Download signals.json", signals_json, file_name="signals.json", mime="application/json")

with digest_tab:
    st.subheader("Final digest")
    st.markdown(result.digest_markdown)
    st.download_button("Download digest.md", result.digest_markdown, file_name="digest.md", mime="text/markdown")

with rejected_tab:
    st.subheader("Rejected as noise")
    rejected_cols = ["title", "source", "noise_reason", "deny_hits", "allow_hits", "canonical_url"]
    st.dataframe(result.rejected_articles[rejected_cols], width="stretch", hide_index=True)

with prompts_tab:
    st.subheader("LLM prompts")
    prompt_dir = Path("prompts")
    for prompt_file in sorted(prompt_dir.glob("*.txt")):
        with st.expander(prompt_file.stem.replace("_", " ").title()):
            st.code(prompt_file.read_text(encoding="utf-8"), language="text")
