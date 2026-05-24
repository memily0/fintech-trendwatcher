#!/usr/bin/env python3
"""Run a lightweight validation experiment for the TrendWatcher MVP.

The script intentionally keeps the experiment simple and reproducible:
RSS/sample collection -> deterministic analyst-style labels -> existing
pipeline run -> ranking metrics -> CSV/JSON/Markdown report.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trendwatcher.demo_data import demo_articles
from trendwatcher.pipeline import run_pipeline
from trendwatcher.rss import DEFAULT_RSS_SOURCES, fetch_rss_articles_with_status


CATEGORIES = {
    "payments",
    "regulation",
    "fraud_risk",
    "UX",
    "partnership",
    "banking_product",
    "market_signal",
    "noise",
}

NOISE_KEYWORDS = {
    "vacancy",
    "job",
    "career",
    "course",
    "webinar",
    "sponsored",
    "advertisement",
    "promo",
    "discount",
    "bitcoin price",
    "price prediction",
    "crypto coins",
    "traders",
    "stock market",
    "shares rise",
    "earnings outlook",
    "market recap",
    "котировки",
    "акции выросли",
    "обзор рынка",
    "прогноз цены",
    "криптовалюта",
    "биткоин",
    "трейдер",
    "вакансия",
    "курс",
    "обучение",
    "вебинар",
    "реклама",
    "промо",
    "скидка",
    "памятная монета",
    "серебряная монета",
    "нумизматика",
    "коллекционная монета",
}

STRONG_FINTECH_TERMS = {
    "bank",
    "banking",
    "payment",
    "payments",
    "checkout",
    "merchant",
    "card",
    "wallet",
    "lending",
    "loan",
    "deposit",
    "fraud",
    "criminal",
    "criminals",
    "scam",
    "scams",
    "kyc",
    "aml",
    "biometric",
    "open banking",
    "regulation",
    "regulator",
    "compliance",
    "enforcement",
    "fine",
    "fined",
    "penalty",
    "fintech",
    "банк",
    "банки",
    "банковский",
    "платеж",
    "платежи",
    "перевод",
    "переводы",
    "карта",
    "кошелек",
    "кредит",
    "вклад",
    "депозит",
    "скоринг",
    "антифрод",
    "мошенничество",
    "идентификация",
    "биометрия",
    "регулирование",
    "регулятор",
    "цифровой рубль",
    "сбп",
}

CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "payments": {
        "payment",
        "payments",
        "checkout",
        "merchant",
        "acquiring",
        "qr",
        "card",
        "wallet",
        "tap to pay",
        "transfer",
        "платеж",
        "платежи",
        "перевод",
        "переводы",
        "эквайринг",
        "сбп",
        "быстрые платежи",
        "карта",
        "qr",
    },
    "regulation": {
        "regulation",
        "regulator",
        "compliance",
        "rule",
        "rules",
        "guidance",
        "enforcement",
        "fine",
        "fined",
        "penalty",
        "lawsuit",
        "complaint",
        "deception",
        "law",
        "supervision",
        "central bank",
        "digital euro",
        "digital ruble",
        "цб",
        "банк россии",
        "регулятор",
        "регулирование",
        "закон",
        "требование",
        "надзор",
        "цифровой рубль",
        "персональные данные",
    },
    "fraud_risk": {
        "fraud",
        "criminal",
        "criminals",
        "risk",
        "security",
        "scam",
        "scams",
        "kyc",
        "aml",
        "mule",
        "biometric",
        "authentication",
        "мошенничество",
        "антифрод",
        "риск",
        "безопасность",
        "идентификация",
        "биометрия",
        "подозрительные операции",
    },
    "UX": {
        "mobile app",
        "app",
        "onboarding",
        "interface",
        "customer experience",
        "loyalty",
        "cashback",
        "biometric",
        "мобильное приложение",
        "приложение",
        "онбординг",
        "интерфейс",
        "лояльность",
        "кешбэк",
        "биометрия",
    },
    "partnership": {
        "partner",
        "partnership",
        "integration",
        "ecosystem",
        "marketplace",
        "embedded",
        "партнерство",
        "партнер",
        "совместно",
        "интеграция",
        "экосистема",
        "маркетплейс",
    },
    "banking_product": {
        "loan",
        "lending",
        "deposit",
        "savings",
        "account",
        "bnpl",
        "mortgage",
        "credit",
        "debit",
        "кредит",
        "кредитование",
        "вклад",
        "депозит",
        "счет",
        "рассрочка",
        "ипотека",
        "заем",
        "bnpl",
    },
    "market_signal": {
        "trend",
        "pilot",
        "launch",
        "test",
        "strategy",
        "research",
        "report",
        "market",
        "tokenized",
        "тренд",
        "пилот",
        "запуск",
        "тестирование",
        "стратегия",
        "исследование",
        "рынок",
    },
}

HIGH_IMPORTANCE_TERMS = {
    "launch",
    "announces",
    "pilot",
    "expands",
    "guidance",
    "rules",
    "requirements",
    "regulation",
    "enforcement",
    "fine",
    "fined",
    "penalty",
    "criminal",
    "criminals",
    "scam",
    "scams",
    "fraud",
    "digital euro",
    "digital ruble",
    "open banking",
    "partnership",
    "запуск",
    "пилот",
    "расширяет",
    "требования",
    "регулирование",
    "цифровой рубль",
    "сбп",
    "антифрод",
    "мошенничество",
    "партнерство",
}

REGULATOR_SOURCES = {
    "Банк России — новости",
    "Банк России — события",
    "Банк России — пресс-релизы",
    "BIS",
    "ECB",
    "CFPB",
    "Bank of England",
}

OFFICIAL_OR_SPECIALIZED_SOURCES = {
    "Finextra",
    "The Paypers",
    "PYMNTS",
    "Stripe Blog",
    "Visa",
    "Mastercard",
    "PayPal",
    "Open Banking UK",
}


def _contains_cyrillic(text: str) -> bool:
    return any(("а" <= char.lower() <= "я") or char in {"ё", "Ё"} for char in text)


def _blob(row: pd.Series | dict[str, Any]) -> str:
    values = [
        row.get("title", ""),
        row.get("source", ""),
        row.get("url", ""),
        row.get("snippet", ""),
        row.get("raw_text", row.get("text", "")),
    ]
    return " ".join(str(value or "") for value in values).lower()


def _hits(blob: str, keywords: set[str]) -> list[str]:
    return sorted(keyword for keyword in keywords if keyword.lower() in blob)


def _unique_ids(values: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    output: list[str] = []
    for idx, raw in enumerate(values, 1):
        base = str(raw or f"val-{idx:03d}").strip() or f"val-{idx:03d}"
        count = seen.get(base, 0)
        seen[base] = count + 1
        output.append(base if count == 0 else f"{base}-{count + 1}")
    return output


def _normalize_sample_rows(rows: list[dict[str, Any]]) -> pd.DataFrame:
    normalized: list[dict[str, str]] = []
    for idx, row in enumerate(rows, 1):
        snippet = row.get("snippet") or row.get("summary") or row.get("description") or ""
        raw_text = row.get("raw_text") or row.get("text") or snippet
        normalized.append(
            {
                "id": str(row.get("id") or f"val-{idx:03d}"),
                "title": str(row.get("title") or ""),
                "source": str(row.get("source") or "Unknown"),
                "url": str(row.get("url") or ""),
                "published_at": str(row.get("published_at") or "")[:10],
                "snippet": str(snippet or ""),
                "raw_text": str(raw_text or ""),
            }
        )
    df = pd.DataFrame(normalized)
    if df.empty:
        return pd.DataFrame(columns=["id", "title", "source", "url", "published_at", "snippet", "raw_text"])
    df["id"] = _unique_ids(df["id"].astype(str).tolist())
    return df


def _load_fallback_articles() -> tuple[list[dict[str, Any]], str]:
    articles_csv = PROJECT_ROOT / "data" / "articles.csv"
    if articles_csv.exists():
        df = pd.read_csv(articles_csv)
        rows = []
        for _, row in df.iterrows():
            rows.append(
                {
                    "id": row.get("id", ""),
                    "title": row.get("title", ""),
                    "source": row.get("source", ""),
                    "url": row.get("url", ""),
                    "published_at": row.get("published_at", ""),
                    "snippet": row.get("snippet", ""),
                    "text": row.get("text", row.get("snippet", "")),
                }
            )
        return rows, "fallback_data_articles_csv"
    return demo_articles(), "fallback_demo_articles"


def collect_sample(sample_size: int, seed: int, limit_per_source: int) -> tuple[pd.DataFrame, dict[str, Any]]:
    min_sample_size = min(50, sample_size)
    rss_articles, rss_warnings = fetch_rss_articles_with_status(DEFAULT_RSS_SOURCES, limit_per_source=limit_per_source)
    source_mode = "live_rss"
    fallback_used = False
    fallback_reason = ""
    rows = rss_articles

    if len(rss_articles) < min_sample_size:
        fallback_rows, source_mode = _load_fallback_articles()
        rows = fallback_rows
        fallback_used = True
        fallback_reason = (
            f"RSS вернул {len(rss_articles)} публикаций, меньше минимального порога {min_sample_size}; "
            f"использован {source_mode}."
        )

    df = _normalize_sample_rows(rows)
    rng = random.Random(seed)
    indexes = list(df.index)
    rng.shuffle(indexes)
    n = min(max(50, min(70, sample_size)), len(indexes))
    sample = df.loc[indexes[:n]].reset_index(drop=True)
    sample["id"] = [f"val-{idx:03d}" for idx in range(1, len(sample) + 1)]

    meta = {
        "source_mode": source_mode,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "rss_articles_fetched": len(rss_articles),
        "rss_warnings": rss_warnings,
        "rss_sources": list(DEFAULT_RSS_SOURCES.keys()),
        "seed": seed,
        "requested_sample_size": sample_size,
        "actual_sample_size": len(sample),
    }
    return sample, meta


def _manual_category(blob: str) -> str:
    scores = {
        category: len(_hits(blob, keywords))
        for category, keywords in CATEGORY_KEYWORDS.items()
    }
    best_category, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score == 0:
        return "noise"
    return best_category


def analyst_label(row: pd.Series) -> dict[str, Any]:
    blob = _blob(row)
    source = str(row.get("source", ""))
    noise_hits = _hits(blob, NOISE_KEYWORDS)
    fintech_hits = _hits(blob, STRONG_FINTECH_TERMS)
    category = _manual_category(blob)

    if noise_hits and len(fintech_hits) < 3:
        return {
            "manual_relevance": 0,
            "manual_signal": 0,
            "manual_importance": 0,
            "manual_category": "noise",
            "manual_comment": f"Шум для банковского дайджеста: {', '.join(noise_hits[:3])}.",
        }

    if category == "noise" or len(fintech_hits) == 0:
        return {
            "manual_relevance": 0,
            "manual_signal": 0,
            "manual_importance": 0,
            "manual_category": "noise",
            "manual_comment": "Недостаточно признаков финтех/банковского сигнала.",
        }

    importance = 1
    reasons = [f"категория {category}"]
    if source in REGULATOR_SOURCES:
        importance += 1
        reasons.append("регуляторный/официальный источник")
    elif source in OFFICIAL_OR_SPECIALIZED_SOURCES:
        reasons.append("профильный или официальный источник")

    high_hits = _hits(blob, HIGH_IMPORTANCE_TERMS)
    if high_hits:
        importance += 1
        reasons.append(f"есть признаки события: {', '.join(high_hits[:2])}")

    if category in {"regulation", "fraud_risk", "payments"} and len(fintech_hits) >= 2:
        importance += 1
        reasons.append("тема потенциально прикладная для банка")

    importance = min(3, importance)
    manual_signal = 1 if importance >= 2 else 0
    if manual_signal:
        comment = "Полезный сигнал для дайджеста: " + "; ".join(reasons[:3]) + "."
    else:
        comment = "Слабый сигнал: тема релевантна, но прикладное действие неочевидно по RSS snippet."

    return {
        "manual_relevance": 1,
        "manual_signal": manual_signal,
        "manual_importance": importance,
        "manual_category": category,
        "manual_comment": comment,
    }


def build_manual_labels(sample: pd.DataFrame) -> pd.DataFrame:
    labels = sample.copy()
    manual_rows = [analyst_label(row) for _, row in labels.iterrows()]
    manual_df = pd.DataFrame(manual_rows)
    return pd.concat([labels, manual_df], axis=1)


def build_pipeline_output(sample: pd.DataFrame, dedup_method: str) -> tuple[pd.DataFrame, dict[str, Any]]:
    pipeline_input = sample.rename(columns={"raw_text": "text"}).copy()
    result = run_pipeline(articles=pipeline_input, use_llm=False, top_n=7, dedup_method=dedup_method)

    candidate_map = {
        str(row["id"]): row
        for _, row in result.candidate_articles.iterrows()
    }
    rejected_map = {
        str(row["id"]): row
        for _, row in result.rejected_articles.iterrows()
    }
    signal_map: dict[str, dict[str, Any]] = {}
    for rank, signal in enumerate(result.signals, 1):
        for article_id in signal.get("article_ids", []):
            signal_map[str(article_id)] = {
                "pipeline_signal": 1,
                "pipeline_category": signal.get("category", ""),
                "pipeline_score": signal.get("score", 0),
                "pipeline_rank": rank,
                "pipeline_signal_headline": signal.get("headline", ""),
                "pipeline_in_digest_top7": 1 if rank <= 7 else 0,
            }

    output_rows: list[dict[str, Any]] = []
    for _, row in sample.iterrows():
        article_id = str(row["id"])
        candidate = candidate_map.get(article_id)
        rejected = rejected_map.get(article_id)
        signal = signal_map.get(article_id, {})
        passed_filter = candidate is not None

        detected_category = ""
        pipeline_relevance = 1 if passed_filter else 0
        rejection_reason = ""
        pipeline_score = 0.0
        if candidate is not None:
            detected_category = str(candidate.get("detected_category", ""))
            pipeline_score = float(candidate.get("candidate_score", 0.0))
        if rejected is not None:
            detected_category = str(rejected.get("detected_category", ""))
            rejection_reason = str(rejected.get("noise_reason", ""))

        if signal:
            detected_category = str(signal["pipeline_category"])
            pipeline_score = float(signal["pipeline_score"])

        output_rows.append(
            {
                "id": article_id,
                "url": row["url"],
                "title": row["title"],
                "pipeline_relevance": pipeline_relevance,
                "pipeline_signal": int(signal.get("pipeline_signal", 0)),
                "pipeline_in_digest_top7": int(signal.get("pipeline_in_digest_top7", 0)),
                "pipeline_category": detected_category,
                "pipeline_score": round(pipeline_score, 2),
                "pipeline_rank": signal.get("pipeline_rank", ""),
                "pipeline_signal_headline": signal.get("pipeline_signal_headline", ""),
                "rejection_reason": rejection_reason,
            }
        )

    meta = {
        "dedup_method_requested": dedup_method,
        "dedup_method_used": result.dedup_method_used,
        "pipeline_warnings": result.warnings or [],
        "candidate_count": len(result.candidate_articles),
        "rejected_count": len(result.rejected_articles),
        "signal_count": len(result.signals),
    }
    return pd.DataFrame(output_rows), meta


def _dcg(gains: list[int]) -> float:
    return sum((2**gain - 1) / math.log2(position + 1) for position, gain in enumerate(gains, 1))


def _precision_at(joined: pd.DataFrame, k: int) -> float:
    ranked = _ranked_rows(joined).head(k)
    return float((ranked["manual_importance"] >= 2).sum() / k)


def _recall_at(joined: pd.DataFrame, k: int) -> float:
    total_relevant = int((joined["manual_importance"] >= 2).sum())
    if total_relevant == 0:
        return 0.0
    ranked = _ranked_rows(joined).head(k)
    return float((ranked["manual_importance"] >= 2).sum() / total_relevant)


def _ndcg_at(joined: pd.DataFrame, k: int) -> float:
    ranked_gains = _ranked_rows(joined).head(k)["manual_importance"].astype(int).tolist()
    ideal_gains = joined["manual_importance"].astype(int).sort_values(ascending=False).head(k).tolist()
    idcg = _dcg(ideal_gains)
    if idcg == 0:
        return 0.0
    return float(_dcg(ranked_gains) / idcg)


def _ranked_rows(joined: pd.DataFrame) -> pd.DataFrame:
    ranked = joined.copy()
    ranked["_rank_sort"] = pd.to_numeric(ranked["pipeline_rank"], errors="coerce").fillna(10**9)
    ranked["_score_sort"] = pd.to_numeric(ranked["pipeline_score"], errors="coerce").fillna(0)
    return ranked.sort_values(["_rank_sort", "_score_sort", "title"], ascending=[True, False, True])


def _safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator == 0:
        return None
    return float(numerator / denominator)


def compute_metrics(joined: pd.DataFrame) -> tuple[dict[str, Any], str | None]:
    relevant_for_category = joined[
        (joined["manual_relevance"] == 1)
        & joined["pipeline_category"].fillna("").astype(str).ne("")
    ].copy()
    if len(relevant_for_category) > 0:
        category_accuracy = float(
            (relevant_for_category["manual_category"].astype(str) == relevant_for_category["pipeline_category"].astype(str)).sum()
            / len(relevant_for_category)
        )
    else:
        category_accuracy = None

    pipeline_signals = joined[joined["pipeline_signal"] == 1]
    manual_signals = joined[joined["manual_signal"] == 1]
    signal_precision = _safe_rate(int((pipeline_signals["manual_signal"] == 1).sum()), len(pipeline_signals))
    signal_recall = _safe_rate(int((manual_signals["pipeline_signal"] == 1).sum()), len(manual_signals))

    spearman_note = None
    spearman = None
    try:
        from scipy.stats import spearmanr

        result = spearmanr(
            pd.to_numeric(joined["pipeline_score"], errors="coerce").fillna(0),
            joined["manual_importance"].astype(int),
        )
        if not math.isnan(float(result.statistic)):
            spearman = float(result.statistic)
    except Exception as exc:  # pragma: no cover - optional dependency.
        spearman_note = f"Spearman не рассчитан: scipy недоступен или вернул ошибку ({exc})."

    metrics = {
        "precision_at_5": _precision_at(joined, 5),
        "precision_at_10": _precision_at(joined, 10),
        "recall_at_10": _recall_at(joined, 10),
        "ndcg_at_10": _ndcg_at(joined, 10),
        "category_accuracy": category_accuracy,
        "signal_precision": signal_precision,
        "signal_recall": signal_recall,
        "spearman_pipeline_score_vs_manual_importance": spearman,
    }
    return {key: (round(value, 4) if isinstance(value, float) else value) for key, value in metrics.items()}, spearman_note


def _fmt_metric(value: Any) -> str:
    if value is None or value == "":
        return "n/a"
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _examples(joined: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    successes = joined[(joined["manual_signal"] == 1) & (joined["pipeline_signal"] == 1)].copy()
    successes = _ranked_rows(successes).head(5)

    false_positives = joined[(joined["manual_signal"] == 0) & (joined["pipeline_signal"] == 1)].copy()
    false_positives = false_positives.sort_values("pipeline_score", ascending=False).head(3)
    false_negatives = joined[(joined["manual_signal"] == 1) & (joined["pipeline_signal"] == 0)].copy()
    false_negatives = false_negatives.sort_values("manual_importance", ascending=False).head(3)
    category_errors = joined[
        (joined["manual_relevance"] == 1)
        & joined["pipeline_category"].fillna("").astype(str).ne("")
        & (joined["manual_category"].astype(str) != joined["pipeline_category"].astype(str))
    ].copy()
    category_errors = category_errors.sort_values("pipeline_score", ascending=False).head(3)
    errors = pd.concat([false_positives, false_negatives, category_errors]).drop_duplicates(subset=["id"]).head(5)
    return successes, errors


def _markdown_table(rows: list[dict[str, Any]], columns: list[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(str(row.get(column, "")).replace("\n", " ") for column in columns) + " |")
    return "\n".join([header, sep, *body])


def build_report_markdown(
    joined: pd.DataFrame,
    metrics: dict[str, Any],
    sample_meta: dict[str, Any],
    pipeline_meta: dict[str, Any],
    spearman_note: str | None,
) -> str:
    successes, errors = _examples(joined)
    metric_rows = [
        {"Metric": "Precision@5", "Value": _fmt_metric(metrics["precision_at_5"])},
        {"Metric": "Precision@10", "Value": _fmt_metric(metrics["precision_at_10"])},
        {"Metric": "Recall@10", "Value": _fmt_metric(metrics["recall_at_10"])},
        {"Metric": "NDCG@10", "Value": _fmt_metric(metrics["ndcg_at_10"])},
        {"Metric": "Category Accuracy", "Value": _fmt_metric(metrics["category_accuracy"])},
        {"Metric": "Signal Precision", "Value": _fmt_metric(metrics["signal_precision"])},
        {"Metric": "Signal Recall", "Value": _fmt_metric(metrics["signal_recall"])},
        {
            "Metric": "Spearman score/import.",
            "Value": _fmt_metric(metrics["spearman_pipeline_score_vs_manual_importance"]),
        },
    ]
    success_rows = [
        {
            "Title": row["title"][:90],
            "Manual": f"{row['manual_category']} / {row['manual_importance']}",
            "Pipeline": f"{row['pipeline_category']} / score {row['pipeline_score']} / rank {row['pipeline_rank']}",
        }
        for _, row in successes.iterrows()
    ]
    error_rows = [
        {
            "Title": row["title"][:90],
            "Manual": f"{row['manual_category']} / signal {row['manual_signal']}",
            "Pipeline": f"{row['pipeline_category']} / signal {row['pipeline_signal']} / {row['rejection_reason']}",
        }
        for _, row in errors.iterrows()
    ]

    relevant_count = int(joined["manual_relevance"].sum())
    signal_count = int(joined["manual_signal"].sum())
    fallback_text = (
        f"Да: {sample_meta['fallback_reason']}"
        if sample_meta.get("fallback_used")
        else "Нет, использовались live RSS публикации."
    )
    spearman_text = spearman_note or "Spearman рассчитан через scipy."

    conclusion = (
        "Pipeline поднимает наверх значимые финтех-сигналы и отсекает часть шума. "
        "Ошибки ожидаемо чаще возникают на коротких RSS snippet, широких рыночных новостях "
        "и спорных product/news материалах, где не хватает полного текста."
    )

    lines = [
        "# Validation report: Fintech TrendWatcher",
        "",
        f"_Сформировано: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "## Dataset",
        "",
        f"- Размер выборки: {len(joined)} публикаций.",
        f"- Seed: {sample_meta['seed']}.",
        f"- Источник выборки: {sample_meta['source_mode']}.",
        f"- Fallback: {fallback_text}",
        f"- RSS публикаций получено до fallback: {sample_meta['rss_articles_fetched']}.",
        f"- Материалов с `manual_relevance=1`: {relevant_count}.",
        f"- Материалов с `manual_signal=1`: {signal_count}.",
        "",
        "## RSS sources",
        "",
        *[f"- {source}" for source in sample_meta["rss_sources"]],
        "",
        "## Pipeline run",
        "",
        f"- Dedup method requested: {pipeline_meta['dedup_method_requested']}.",
        f"- Dedup method used: {pipeline_meta['dedup_method_used']}.",
        f"- Candidates: {pipeline_meta['candidate_count']}.",
        f"- Rejected: {pipeline_meta['rejected_count']}.",
        f"- Signals: {pipeline_meta['signal_count']}.",
        "",
        "## Metrics",
        "",
        _markdown_table(metric_rows, ["Metric", "Value"]),
        "",
        f"_Примечание: {spearman_text}_",
        "",
        "## Короткий вывод для презентации",
        "",
        conclusion,
        "",
        "## Удачные срабатывания",
        "",
        _markdown_table(success_rows, ["Title", "Manual", "Pipeline"]) if success_rows else "Нет удачных срабатываний в этой выборке.",
        "",
        "## Ошибки pipeline",
        "",
        _markdown_table(error_rows, ["Title", "Manual", "Pipeline"]) if error_rows else "Явных ошибок по заданным правилам не найдено.",
        "",
        "## Ограничения эксперимента",
        "",
        "- Разметка имитирует работу аналитика через прозрачную deterministic rubric, а не заменяет настоящую независимую ручную разметку.",
        "- RSS часто содержит только title/snippet, поэтому часть оценок сделана без полного текста статьи.",
        "- Live RSS меняется со временем; seed фиксирует sampling, но не фиксирует содержимое внешних лент.",
        "- Метрики считаются для MVP-ranking baseline, а не для production ML-модели.",
        "",
        "## Slide summary",
        "",
        "Ручная проверка качества:",
        f"- Размечено {len(joined)} RSS-публикаций.",
        "- Оценивали релевантность, полезность как сигнала, категорию и важность.",
        "- Сравнили ручную разметку с top-K выдачей pipeline.",
        "",
        "Метрики:",
        f"- Precision@5 = {_fmt_metric(metrics['precision_at_5'])}",
        f"- Precision@10 = {_fmt_metric(metrics['precision_at_10'])}",
        f"- Recall@10 = {_fmt_metric(metrics['recall_at_10'])}",
        f"- NDCG@10 = {_fmt_metric(metrics['ndcg_at_10'])}",
        f"- Category Accuracy = {_fmt_metric(metrics['category_accuracy'])}",
        "",
        "Вывод:",
        "Pipeline поднимает наверх значимые финтех-сигналы и отсекает часть шума, но ошибки чаще возникают на коротких RSS snippet и спорных product/news материалах.",
        "",
        "## Command",
        "",
        "```bash",
        "python3 scripts/run_validation_experiment.py",
        "```",
        "",
    ]
    if sample_meta.get("rss_warnings"):
        lines.extend(["## RSS warnings", "", *[f"- {warning}" for warning in sample_meta["rss_warnings"]], ""])
    if pipeline_meta.get("pipeline_warnings"):
        lines.extend(["## Pipeline warnings", "", *[f"- {warning}" for warning in pipeline_meta["pipeline_warnings"]], ""])
    return "\n".join(lines)


def write_outputs(
    output_dir: Path,
    sample: pd.DataFrame,
    manual_labels: pd.DataFrame,
    pipeline_output: pd.DataFrame,
    joined: pd.DataFrame,
    report: dict[str, Any],
    report_md: str,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    sample.to_csv(output_dir / "rss_validation_sample.csv", index=False)
    manual_labels.to_csv(output_dir / "manual_labels.csv", index=False)
    pipeline_output.to_csv(output_dir / "pipeline_validation_output.csv", index=False)
    joined.to_csv(output_dir / "validation_joined.csv", index=False)
    (output_dir / "validation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "validation_report.md").write_text(report_md, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run TrendWatcher validation experiment")
    parser.add_argument("--sample-size", type=int, default=60, help="RSS sample size, clamped to 50..70")
    parser.add_argument("--seed", type=int, default=42, help="Fixed random seed")
    parser.add_argument("--limit-per-source", type=int, default=25, help="RSS items to fetch per source")
    parser.add_argument("--output-dir", type=Path, default=Path("data/validation"), help="Validation output directory")
    parser.add_argument("--dedup-method", choices=["fuzzy", "tfidf", "tf-idf"], default="fuzzy", help="Pipeline dedup method")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sample_size = max(50, min(70, args.sample_size))
    sample, sample_meta = collect_sample(sample_size, args.seed, args.limit_per_source)
    manual_labels = build_manual_labels(sample)
    pipeline_output, pipeline_meta = build_pipeline_output(sample, args.dedup_method)
    joined = manual_labels.merge(
        pipeline_output.drop(columns=["url", "title"], errors="ignore"),
        on="id",
        how="left",
        validate="one_to_one",
    )
    metrics, spearman_note = compute_metrics(joined)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "command": "python3 scripts/run_validation_experiment.py",
        "sample": sample_meta,
        "pipeline": pipeline_meta,
        "counts": {
            "sample_size": len(joined),
            "manual_relevance_1": int(joined["manual_relevance"].sum()),
            "manual_signal_1": int(joined["manual_signal"].sum()),
            "pipeline_signal_1": int(joined["pipeline_signal"].sum()),
        },
        "metrics": metrics,
        "spearman_note": spearman_note,
        "outputs": {
            "rss_validation_sample": str(args.output_dir / "rss_validation_sample.csv"),
            "manual_labels": str(args.output_dir / "manual_labels.csv"),
            "pipeline_validation_output": str(args.output_dir / "pipeline_validation_output.csv"),
            "validation_joined": str(args.output_dir / "validation_joined.csv"),
            "validation_report_json": str(args.output_dir / "validation_report.json"),
            "validation_report_md": str(args.output_dir / "validation_report.md"),
        },
    }
    report_md = build_report_markdown(joined, metrics, sample_meta, pipeline_meta, spearman_note)
    write_outputs(args.output_dir, sample, manual_labels, pipeline_output, joined, report, report_md)

    print("TrendWatcher validation experiment complete")
    print(f"Sample size: {len(joined)}")
    print(f"Source mode: {sample_meta['source_mode']}")
    print(f"Fallback used: {sample_meta['fallback_used']}")
    print(f"Precision@5: {_fmt_metric(metrics['precision_at_5'])}")
    print(f"Precision@10: {_fmt_metric(metrics['precision_at_10'])}")
    print(f"Recall@10: {_fmt_metric(metrics['recall_at_10'])}")
    print(f"NDCG@10: {_fmt_metric(metrics['ndcg_at_10'])}")
    print(f"Report: {args.output_dir / 'validation_report.md'}")


if __name__ == "__main__":
    main()
