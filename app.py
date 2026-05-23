from __future__ import annotations

import html
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from trendwatcher.demo_data import demo_articles
from trendwatcher.pipeline import SOURCE_TIERS, format_publication_date, run_pipeline, save_outputs
from trendwatcher.rss import DEFAULT_RSS_SOURCES, fetch_rss_articles_with_status
from trendwatcher.score_weights import DEFAULT_WEIGHTS, FEATURES, load_score_weights, save_score_weights


st.set_page_config(page_title="Fintech TrendWatcher", layout="wide")

st.markdown(
    """
    <style>
    :root {
      --tw-bg: #ffffff;
      --tw-card: #f7f9fc;
      --tw-card-strong: #edf3f8;
      --tw-border: #d7e0ea;
      --tw-text: #16202c;
      --tw-muted: #536579;
      --tw-link: #0b68c8;
      --tw-chip-bg: #ffffff;
      --tw-chip-text: #243246;
      --tw-good: #0d7c66;
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --tw-bg: #0f1720;
        --tw-card: #17212d;
        --tw-card-strong: #1f2d3c;
        --tw-border: #344457;
        --tw-text: #edf3f8;
        --tw-muted: #b7c4d3;
        --tw-link: #8cc8ff;
        --tw-chip-bg: #233246;
        --tw-chip-text: #edf3f8;
        --tw-good: #64d7b5;
      }
    }
    .block-container { padding-top: 1.35rem; }
    .metric-row [data-testid="stMetric"] {
      background: var(--tw-card);
      border: 1px solid var(--tw-border);
      border-radius: 8px;
      padding: 12px 14px;
    }
    .flow-card, .signal-card {
      border: 1px solid var(--tw-border);
      border-radius: 8px;
      background: var(--tw-card);
      color: var(--tw-text);
    }
    .flow-card {
      min-height: 124px;
      padding: 14px;
    }
    .flow-title {
      font-weight: 700;
      color: var(--tw-text);
      margin-bottom: 6px;
    }
    .flow-note, .small-muted {
      color: var(--tw-muted);
      font-size: 0.88rem;
      line-height: 1.45;
    }
    .signal-card {
      padding: 16px 18px;
      margin: 0 0 14px 0;
    }
    .signal-card h3 {
      font-size: 1.03rem;
      margin: 0 0 8px 0;
      color: var(--tw-text);
      letter-spacing: 0;
    }
    .signal-card p {
      color: var(--tw-text);
      margin: 8px 0;
      line-height: 1.5;
    }
    .signal-card a {
      color: var(--tw-link);
      text-decoration: none;
    }
    .score-line {
      background: var(--tw-card-strong);
      border: 1px solid var(--tw-border);
      border-radius: 8px;
      padding: 8px 10px;
      margin: 10px 0;
      color: var(--tw-text);
    }
    .chip {
      display: inline-block;
      border: 1px solid var(--tw-border);
      border-radius: 999px;
      padding: 2px 8px;
      margin: 0 4px 5px 0;
      font-size: 0.78rem;
      color: var(--tw-chip-text);
      background: var(--tw-chip-bg);
    }
    .source-line {
      color: var(--tw-muted);
      font-size: 0.88rem;
      line-height: 1.45;
    }
    .formula-card {
      border: 1px solid var(--tw-border);
      border-radius: 8px;
      background: var(--tw-card);
      color: var(--tw-text);
      padding: 14px 16px;
      margin: 10px 0 14px 0;
    }
    .formula {
      font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
      background: var(--tw-card-strong);
      border: 1px solid var(--tw-border);
      border-radius: 8px;
      padding: 10px 12px;
      line-height: 1.65;
      margin-top: 8px;
      white-space: pre-wrap;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


CATEGORY_LABELS = {
    "payments": "Платежи",
    "banking_product": "Банковский продукт",
    "UX": "UX / клиентский сценарий",
    "partnership": "Партнерство",
    "regulation": "Регулирование",
    "market_signal": "Рыночный сигнал",
    "fraud_risk": "Риски / антифрод",
    "other": "Другое",
}


FEATURE_LABELS = {
    "relevance": "Релевантность",
    "source_quality": "Качество источника",
    "novelty": "Новизна",
    "impact": "Impact",
    "evidence_score": "Качество подтверждений",
}


def esc(value: object) -> str:
    return html.escape(str(value))


def load_uploaded_csv(uploaded_file) -> pd.DataFrame | None:
    if uploaded_file is None:
        return None
    return pd.read_csv(uploaded_file)


def seed_score_weight_sliders(weights: dict[str, float]) -> None:
    for feature in FEATURES:
        st.session_state[f"score_weight_{feature}"] = float(weights.get(feature, DEFAULT_WEIGHTS[feature]))


def format_score_weight(weights: dict, feature: str) -> str:
    return f"{float(weights.get(feature, DEFAULT_WEIGHTS[feature])):.2f}"


def score_weights_table(weights: dict) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Компонент": "relevance",
                "Вес": format_score_weight(weights, "relevance"),
                "Что означает": "насколько публикация похожа на финтех/банковский сигнал",
                "Почему нужен": "главный вклад, потому что прежде всего фильтруется шум",
            },
            {
                "Компонент": "source_quality",
                "Вес": format_score_weight(weights, "source_quality"),
                "Что означает": "насколько надежен тип источника",
                "Почему нужен": "первоисточники и регуляторы проще проверить, перепечатки слабее",
            },
            {
                "Компонент": "novelty",
                "Вес": format_score_weight(weights, "novelty"),
                "Что означает": "есть ли признаки запуска, пилота, изменения или guidance",
                "Почему нужен": "свежие изменения чаще требуют внимания команды",
            },
            {
                "Компонент": "impact",
                "Вес": format_score_weight(weights, "impact"),
                "Что означает": "насколько категория потенциально важна для банка",
                "Почему нужен": "regulation, fraud и payments обычно имеют больший прикладной эффект",
            },
            {
                "Компонент": "evidence_score",
                "Вес": format_score_weight(weights, "evidence_score"),
                "Что означает": "сумма similarity × source_quality по похожим источникам",
                "Почему нужен": "каждый качественный похожий источник добавляет вклад, слабые источники добавляют мало",
            },
        ]
    )


def render_score_formula(weights: dict) -> None:
    st.markdown("**Формула оценки**")
    st.markdown(
        f"""
        <div class="formula-card">
          <div><b>score</b> — это оценка важности сигнала. Коэффициенты задаются вручную в настройках запуска.</div>
          <div class="formula">score =
  {format_score_weight(weights, "relevance")} × relevance
+ {format_score_weight(weights, "source_quality")} × source_quality
+ {format_score_weight(weights, "novelty")} × novelty
+ {format_score_weight(weights, "impact")} × impact
+ {format_score_weight(weights, "evidence_score")} × evidence_score</div>
          <div class="flow-note">evidence_score считается как сумма similarity × source_quality по похожим источникам в кластере.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.dataframe(score_weights_table(weights), width="stretch", hide_index=True)


def render_signal_card(signal: dict) -> None:
    components = signal["score_components"]
    tags = "".join(f'<span class="chip">{esc(tag)}</span>' for tag in signal.get("tags", [])[:7])
    sources = "<br>".join(
        (
            f'<span class="source-line"><a href="{esc(src["url"])}" target="_blank">'
            f'{esc(src.get("source_date", src["source"]))}</a> · надежность {esc(src["quality"])}</span>'
        )
        for src in signal.get("sources", [])[:4]
    )
    category = CATEGORY_LABELS.get(signal.get("category"), signal.get("category", "Другое"))
    st.markdown(
        f"""
        <div class="signal-card">
          <h3>{esc(signal["headline"])}</h3>
          <div class="small-muted">
            {esc(signal.get("date_label", "дата не указана"))} · свежесть: {esc(signal.get("freshness_label", "неизвестно"))}
            · категория: {esc(category)}
          </div>
          <div style="margin-top:8px;">{tags}</div>
          <p><b>Что произошло?</b><br>{esc(signal["summary"])}</p>
          <p><b>Почему это может быть важно</b><br>{esc(signal["why_now"])}</p>
          <p><b>Следующий шаг для команды:</b> {esc(signal["suggested_action"])}</p>
          <p class="small-muted"><b>Проверяемые источники</b><br>{sources}</p>
          <div class="score-line"><b>Важность:</b> {esc(signal["hotness"])}/5 · score {esc(signal["score"])}/100</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.expander("Как рассчитана оценка"):
        st.write(signal.get("score_explanation", "Подробное объяснение score недоступно."))
        weights = signal.get("score_weights", {})
        if weights:
            st.write("Коэффициенты score:")
            st.json({feature: weights.get(feature, DEFAULT_WEIGHTS[feature]) for feature in FEATURES})
        st.write(f"Релевантность: {components['relevance']}")
        st.write(f"Качество источника: {components['source_quality']}")
        st.write(f"Новизна: {components['novelty']}")
        st.write(f"Impact: {components['impact']}")
        st.write(f"Качество подтверждений: {components.get('evidence_score', 0)}")
        st.write(f"Confidence: {components['confidence']} / 5")
        st.write(f"Уровень сигнала: {signal.get('signal_level', 'не рассчитан')}")
        st.caption(signal.get("context_note", "Полный текст не загружался, анализ основан на RSS snippet."))


def flow_card(title: str, note: str) -> str:
    return f"""
    <div class="flow-card">
      <div class="flow-title">{esc(title)}</div>
      <div class="flow-note">{esc(note)}</div>
    </div>
    """


with st.sidebar:
    st.header("Настройки запуска")
    saved_score_weights = load_score_weights()
    score_weights = saved_score_weights.copy()
    if "score_weight_sliders_ready" not in st.session_state:
        seed_score_weight_sliders(saved_score_weights)
        st.session_state["score_weight_sliders_ready"] = True
    data_source = st.radio("Источник данных", ["Демо-набор", "CSV-файл", "Live RSS"], index=0)
    uploaded = st.file_uploader("CSV: title, url, source, published_at, snippet, text", type=["csv"])
    st.caption(
        "CSV-режим нужен для проверки pipeline на заранее собранном наборе публикаций или данных "
        "Обязательные поля: title, url, source, published_at, snippet, text"
    )
    top_n = st.slider("Сигналов в дайджесте", 3, 10, 7)

    st.divider()
    st.subheader("Дедупликация")
    dedup_label = st.radio("Метод дедупликации", ["Fuzzy", "TF-IDF"], index=0, horizontal=True)
    dedup_method = "tfidf" if dedup_label == "TF-IDF" else "fuzzy"
    st.caption(
        "Порог дедупликации управляет тем, насколько похожими должны быть две публикации, чтобы система объединила их в один сигнал "
        "Ниже порог - больше объединений и выше риск склеить разные события. Выше порог - осторожнее, но часть дублей может остаться"
    )
    fuzzy_threshold = st.slider("Порог Fuzzy", 0.55, 0.95, 0.72, 0.01, disabled=dedup_label != "Fuzzy")
    if dedup_label == "Fuzzy":
        st.caption("Активен Fuzzy. Он сравнивает тексты напрямую и лучше работает для почти одинаковых заголовков. Рекомендуемый стартовый порог: 0.72")
    else:
        st.caption("Порог Fuzzy сейчас не используется, потому что выбран TF-IDF.")
    tfidf_threshold = st.slider("Порог TF-IDF", 0.35, 0.85, 0.58, 0.01, disabled=dedup_label != "TF-IDF")
    if dedup_label == "TF-IDF":
        st.caption(
            "Активен TF-IDF. Он сравнивает публикации как векторы слов и n-грамм. "
            "Порог ниже, потому что cosine similarity на коротких title/snippet часто дает умеренные значения. Рекомендуемый стартовый порог: 0.58"
        )
    else:
        st.caption("Порог TF-IDF сейчас не используется. Для стабильного демо можно оставить дефолтные значения и показать trade-off при переключении метода")

    st.divider()
    st.subheader("Коэффициенты score")
    with st.form("score_weights_form"):
        edited_weights = {}
        for feature in FEATURES:
            edited_weights[feature] = st.slider(
                FEATURE_LABELS[feature],
                min_value=0.0,
                max_value=1.0,
                value=float(score_weights.get(feature, DEFAULT_WEIGHTS[feature])),
                step=0.01,
            )
        save_weights = st.form_submit_button("Сохранить коэффициенты", width="stretch")
        reset_weights = st.form_submit_button("Сбросить к базовым", width="stretch")
    if save_weights:
        score_weights = save_score_weights(edited_weights)
        seed_score_weight_sliders(score_weights)
        st.session_state.pop("result", None)
        st.success("Коэффициенты score сохранены")
        st.rerun()
    if reset_weights:
        score_weights = save_score_weights(DEFAULT_WEIGHTS)
        seed_score_weight_sliders(score_weights)
        st.session_state.pop("result", None)
        st.success("Коэффициенты score сброшены")
        st.rerun()
    st.caption("Базовый вес evidence_score: 0.15")

    st.divider()
    st.subheader("LLM-обогащение")
    use_llm = st.toggle("Включить OpenRouter", value=False)
    max_llm_items = st.slider("Сигналов для LLM", 1, 12, 6, disabled=not use_llm)
    api_key = st.text_input("OpenRouter API key", type="password", value=os.getenv("OPENROUTER_API_KEY", ""))
    model = st.text_input("Модель", value=os.getenv("OPENROUTER_MODEL", "openai/gpt-5-nano"), disabled=not use_llm)
    run_clicked = st.button("Запустить pipeline", type="primary", width="stretch")

    st.divider()
    st.caption(
        "Live RSS mode использует российские и международные источники "
        "Российские источники нужны для локальной применимости сигналов, международные — "
        "для отслеживания глобальных финтех-трендов"
    )
st.title("Fintech TrendWatcher")
st.caption("Внутренний инструмент банка: публикации → шум → дубли → важность → проверяемый дайджест")

if api_key:
    os.environ["OPENROUTER_API_KEY"] = api_key
if model:
    os.environ["OPENROUTER_MODEL"] = model

config = (
    data_source,
    uploaded.name if uploaded else "",
    top_n,
    use_llm,
    max_llm_items,
    model,
    tuple((feature, score_weights[feature]) for feature in FEATURES),
    dedup_label,
    fuzzy_threshold,
    tfidf_threshold,
)

if "result" not in st.session_state or run_clicked or st.session_state.get("config") != config:
    rss_warnings: list[str] = []
    if data_source == "CSV-файл":
        articles = load_uploaded_csv(uploaded)
        if articles is None:
            st.info("Загрузите CSV-файл или выберите демо-набор")
            st.stop()
    elif data_source == "Live RSS":
        with st.spinner("Загружаем российские и международные RSS-источники..."):
            rss_articles, rss_warnings = fetch_rss_articles_with_status(DEFAULT_RSS_SOURCES, limit_per_source=15)
            articles = pd.DataFrame(rss_articles)
        if rss_warnings:
            st.warning("Часть RSS-источников не загрузилась. Pipeline продолжит работу с доступными публикациями")
        if articles.empty:
            st.warning("RSS не вернул публикации. Для стабильного демо включен встроенный демо-набор")
            articles = pd.DataFrame(demo_articles())
    else:
        articles = pd.DataFrame(demo_articles())

    with st.spinner("Запускаем explainable pipeline..."):
        result = run_pipeline(
            articles=articles,
            use_llm=use_llm,
            max_llm_items=max_llm_items,
            top_n=top_n,
            dedup_method=dedup_method,
            fuzzy_threshold=fuzzy_threshold,
            tfidf_threshold=tfidf_threshold,
            score_weights=score_weights,
        )
        save_outputs(result, "data")
        st.session_state["result"] = result
        st.session_state["rss_warnings"] = rss_warnings
        st.session_state["config"] = config

result = st.session_state["result"]
rss_warnings = st.session_state.get("rss_warnings", [])

if result.warnings:
    for warning in result.warnings:
        st.warning(warning)
if rss_warnings:
    with st.expander("Статус RSS-источников"):
        for warning in rss_warnings:
            st.write(f"- {warning}")

st.markdown('<div class="metric-row">', unsafe_allow_html=True)
m1, m2, m3, m4, m5, m6 = st.columns(6)
m1.metric("Исходные публикации", len(result.raw_articles))
m2.metric("Кандидаты", len(result.candidate_articles))
m3.metric("Отфильтрованный шум", len(result.rejected_articles))
m4.metric("Сигналы", len(result.signals))
avg_score = round(sum(s["score"] for s in result.signals) / max(1, len(result.signals)), 1)
m5.metric("Средний score", avg_score)
duplicates_merged = max(0, len(result.candidate_articles) - len(result.signals))
m6.metric("Объединено дублей", duplicates_merged)
st.markdown("</div>", unsafe_allow_html=True)

if data_source == "Live RSS":
    st.caption(
        "В live RSS режиме количество дублей зависит от пересечения источников. "
        "Для демонстрации механики dedup можно использовать demo fallback dataset."
    )

with st.expander("Что означают метрики?"):
    st.markdown(
        """
        - **Исходные публикации** — все материалы, полученные из demo dataset / CSV / RSS до фильтрации
        - **Кандидаты** — публикации, которые прошли фильтр релевантности и не были признаны шумом
        - **Отфильтрованный шум** — материалы, отброшенные как нерелевантные, рекламные, слишком короткие или слабые
        - **Сигналы** — итоговые группы публикаций после удаления дублей. Один сигнал может объединять несколько похожих публикаций
        - **Средний score** — средний score найденных сигналов
        - **Объединено дублей** — сколько публикаций было объединено с похожими материалами
        """
    )

pipeline_tab, signals_tab, rejected_tab, prompts_tab = st.tabs(
    ["Pipeline", "Сигналы", "Отфильтрованный шум", "LLM-промпты"]
)

with pipeline_tab:
    st.subheader("Этапы обработки")
    st.write(
        "Pipeline показывает, как из открытых публикаций получается короткий проверяемый дайджест: "
        "сначала дешевые и объяснимые правила, затем дедупликация и score, LLM — только опционально"
    )
    steps = [
        ("RSS / CSV", "Получаем публикации из демо-набора, CSV или live RSS"),
        ("Очистка", "Нормализуем URL, даты, источники и текстовые поля"),
        ("Удаление дублей", f"Метод: {result.dedup_method_used.upper()}. Группируем перепечатки одного события"),
        ("Оценка важности", "Считаем relevance, source quality, novelty, impact и evidence count"),
        ("Финальный дайджест", "Оставляем top-сигналы с why now, источниками и действием для команды"),
    ]
    cols = st.columns(len(steps))
    for col, (title, note) in zip(cols, steps):
        col.markdown(flow_card(title, note), unsafe_allow_html=True)
    render_score_formula(score_weights)
    with st.expander("Как считается качество источника?"):
        st.write(
            "Регуляторы и официальные первоисточники получают максимальный вес, потому что их проще проверить и они ближе к исходному событию "
            "Отраслевые медиа помогают быстро находить сигналы, но могут быть пересказами. Перепечатки и слабые источники получают меньший вес"
        )
        tier_table = pd.DataFrame(
            [
                {
                    "Tier": "regulator_or_public_authority",
                    "source_quality": SOURCE_TIERS["regulator_or_public_authority"],
                    "Примеры": "Банк России, BIS, ECB, CFPB, Bank of England",
                },
                {
                    "Tier": "official_company_source",
                    "source_quality": SOURCE_TIERS["official_company_source"],
                    "Примеры": "Visa, Mastercard, Stripe Blog, PayPal, JPMorgan, Open Banking UK",
                },
                {
                    "Tier": "specialized_fintech_media",
                    "source_quality": SOURCE_TIERS["specialized_fintech_media"],
                    "Примеры": "Finextra, The Paypers, PYMNTS",
                },
                {
                    "Tier": "general_business_or_tech_media",
                    "source_quality": SOURCE_TIERS["general_business_or_tech_media"],
                    "Примеры": "РБК, TechCrunch",
                },
                {
                    "Tier": "repost_or_low_confidence",
                    "source_quality": SOURCE_TIERS["repost_or_low_confidence"],
                    "Примеры": "Fintech Repost, слабые перепечатки",
                },
            ]
        )
        st.dataframe(tier_table, width="stretch", hide_index=True)
        st.caption("confidence — отдельная вспомогательная оценка уверенности: она растет, когда сигнал подтверждается несколькими источниками и лучший источник имеет высокий source_quality")

    with st.expander("Почему выбраны эти источники?"):
        st.markdown(
            """
            Источники выбраны так, чтобы покрыть разные типы финтех-сигналов:
            - **регуляторы**: изменения правил, compliance, платежная инфраструктура;
            - **официальные источники компаний**: продуктовые запуски и первоисточники;
            - **отраслевые финтех-медиа**: раннее обнаружение трендов, partnerships, payments, open banking;
            - **деловые и технологические медиа**: широкий рыночный контекст

            """
        )

    with st.expander("Как выбирать пороги дедупликации?"):
        st.markdown(
            """
            Порог дедупликации управляет тем, насколько похожими должны быть две публикации, чтобы система объединила их в один сигнал

            - Ниже порог → система объединяет больше публикаций, но выше риск склеить разные события
            - Выше порог → система осторожнее объединяет материалы, но часть дублей может остаться в дайджесте
            - **Fuzzy** сравнивает тексты напрямую и лучше работает для почти одинаковых заголовков. Рекомендуемый стартовый порог: `0.72`
            - **TF-IDF** сравнивает публикации как векторы слов и n-грамм. Порог ниже, потому что cosine similarity на коротких title/snippet часто дает умеренные значения даже у похожих материалов. Рекомендуемый стартовый порог: `0.58`

            """
        )

    st.markdown("**Top candidates после фильтрации**")
    candidates = result.candidate_articles.copy()
    if not candidates.empty:
        candidates["Дата"] = candidates.apply(lambda row: format_publication_date(row["published_at"], row["source"]), axis=1)
        candidates["Категория"] = candidates["detected_category"].map(CATEGORY_LABELS).fillna(candidates["detected_category"])
        top_candidates = (
            candidates.sort_values(["candidate_score", "source_quality"], ascending=[False, False])
            .head(20)
            .rename(
                columns={
                    "title": "Заголовок",
                    "source": "Источник",
                    "candidate_score": "Score",
                }
            )
        )
        st.dataframe(
            top_candidates[["Заголовок", "Источник", "Дата", "Категория", "Score"]],
            width="stretch",
            hide_index=True,
        )

        with st.expander("Технические детали"):
            debug_cols = [
                "cluster_id",
                "title",
                "source",
                "published_at",
                "detected_category",
                "relevance",
                "source_quality",
                "candidate_score",
                "dedup_method",
                "dedup_similarity",
                "canonical_url",
                "allow_hits",
                "deny_hits",
            ]
            existing = [col for col in debug_cols if col in candidates.columns]
            st.dataframe(candidates[existing], width="stretch", hide_index=True)
    else:
        st.info("После фильтрации не осталось кандидатов")

    st.markdown("**Группы дублей**")
    dedup_rows = []
    for signal in result.signals:
        dedup_rows.append(
            {
                "signal_id": signal["id"],
                "заголовок": signal["headline"],
                "дата": signal.get("date_label", "дата не указана"),
                "статей в группе": len(signal["article_ids"]),
                "уникальных источников": len(signal["sources"]),
                "метод": result.dedup_method_used,
                "варианты заголовков": " | ".join(signal["deduped_titles"][:4]),
            }
        )
    st.dataframe(pd.DataFrame(dedup_rows), width="stretch", hide_index=True)

with signals_tab:
    mode = st.radio("Режим просмотра", ["Карточки сигналов", "Финальный дайджест"], horizontal=True)
    if mode == "Карточки сигналов":
        st.subheader("Приоритизированные сигналы")
        for signal in result.signals[:top_n]:
            render_signal_card(signal)
        signals_json = json.dumps(result.signals, ensure_ascii=False, indent=2)
        st.download_button("Скачать signals.json", signals_json, file_name="signals.json", mime="application/json")
    else:
        st.subheader("Финальный дайджест")
        st.markdown(result.digest_markdown)
        st.download_button("Скачать digest.md", result.digest_markdown, file_name="digest.md", mime="text/markdown")

with rejected_tab:
    st.subheader("Что отброшено как шум")
    rejected = result.rejected_articles.copy()
    if not rejected.empty:
        rejected["Дата"] = rejected.apply(lambda row: format_publication_date(row["published_at"], row["source"]), axis=1)
        rejected_view = rejected.rename(
            columns={
                "title": "Заголовок",
                "source": "Источник",
                "noise_reason": "Причина фильтрации",
                "deny_hits": "Шумовые триггеры",
                "allow_hits": "Финтех-триггеры",
            }
        )
        st.dataframe(
            rejected_view[["Заголовок", "Источник", "Дата", "Причина фильтрации", "Шумовые триггеры", "Финтех-триггеры"]],
            width="stretch",
            hide_index=True,
        )
    else:
        st.success("Шум не найден: все публикации прошли первичный фильтр")

with prompts_tab:
    st.subheader("LLM-промпты")
    st.write("Эти промпты используются только в опциональном режиме LLM-обогащения после дешевой фильтрации и дедупликации")
    prompt_dir = Path("prompts")
    for prompt_file in sorted(prompt_dir.glob("*.txt")):
        with st.expander(prompt_file.stem.replace("_", " ").title()):
            st.code(prompt_file.read_text(encoding="utf-8"), language="text")
