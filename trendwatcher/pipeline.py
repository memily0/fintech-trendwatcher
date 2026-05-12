"""Transparent fintech news pipeline for the MVP."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import pandas as pd

from .demo_data import demo_articles
from .llm import LLMClient


FINTECH_KEYWORDS = {
    "account",
    "ai",
    "aml",
    "authentication",
    "bank",
    "banking",
    "bnpl",
    "card",
    "checkout",
    "compliance",
    "credit",
    "debit",
    "deposit",
    "digital euro",
    "embedded",
    "finance",
    "fintech",
    "fraud",
    "identity",
    "kyc",
    "lending",
    "loan",
    "merchant",
    "mobile app",
    "neobank",
    "open banking",
    "open finance",
    "passkey",
    "payment",
    "payments",
    "regulator",
    "settlement",
    "sme",
    "tokenized",
    "wallet",
}

NOISE_KEYWORDS = {
    "analyst upgrade",
    "bitcoin price",
    "course",
    "earnings outlook",
    "job",
    "landing page",
    "price prediction",
    "seo",
    "shares rise",
    "sponsored",
    "stock market",
    "traders expect",
    "vacancy",
}

CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "payments": {"checkout", "merchant", "payment", "payments", "refunds", "settlement", "tap to pay", "vrp"},
    "banking_product": {"account", "banking", "budgeting", "debit", "deposit", "loan", "loans", "savings", "sme"},
    "UX": {"app", "biometric", "consent", "dashboard", "experience", "loyalty", "mobile", "palm", "wallet"},
    "partnership": {"partner", "partners", "partnership", "merchant-funded", "embedded insurance"},
    "regulation": {"central bank", "consultation", "disclosure", "ecb", "guidance", "regulator", "rules"},
    "market_signal": {"bis", "cross-border", "market", "project", "tokenized"},
    "fraud_risk": {"ai", "aml", "authentication", "fraud", "kyc", "mule", "passkey", "risk"},
}

SOURCE_QUALITY: dict[str, float] = {
    "BIS": 1.00,
    "ECB": 1.00,
    "CFPB": 1.00,
    "Bank of England": 1.00,
    "Visa": 0.92,
    "Mastercard": 0.92,
    "JPMorgan": 0.90,
    "PayPal": 0.88,
    "Open Banking UK": 0.90,
    "Finextra": 0.82,
    "The Paypers": 0.80,
    "PYMNTS": 0.76,
    "TechCrunch": 0.72,
    "Regulator": 0.88,
    "Fintech Repost": 0.42,
}

TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid", "gclid"}


@dataclass
class PipelineResult:
    raw_articles: pd.DataFrame
    normalized_articles: pd.DataFrame
    candidate_articles: pd.DataFrame
    rejected_articles: pd.DataFrame
    signals: list[dict[str, Any]]
    digest_markdown: str
    generated_at: str


def canonical_url(url: str) -> str:
    parsed = urlparse(str(url).strip())
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in TRACKING_PARAMS]
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme or "https", netloc, path, "", urlencode(query), ""))


def domain_from_url(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^a-z0-9а-яё\s]+", " ", title)
    title = re.sub(r"\b(the|a|an|to|for|with|and|of|in|on|by)\b", " ", title)
    return " ".join(title.split())


def similarity(left: str, right: str) -> float:
    left_norm = normalize_title(left)
    right_norm = normalize_title(right)
    if not left_norm or not right_norm:
        return 0.0
    seq = SequenceMatcher(None, left_norm, right_norm).ratio()
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    token_overlap = len(left_tokens & right_tokens) / max(1, len(left_tokens | right_tokens))
    return max(seq, token_overlap)


def _blob(row: pd.Series | dict[str, Any]) -> str:
    return " ".join(str(row.get(field, "")) for field in ("title", "snippet", "text")).lower()


def _keyword_hits(blob: str, keywords: set[str]) -> list[str]:
    return sorted(keyword for keyword in keywords if keyword in blob)


def detect_category(blob: str) -> str:
    scored: list[tuple[int, str]] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        scored.append((len(_keyword_hits(blob, keywords)), category))
    scored.sort(reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else "other"


def extract_tags(blob: str, category: str) -> list[str]:
    tags = set(_keyword_hits(blob, FINTECH_KEYWORDS))
    tags.update(_keyword_hits(blob, CATEGORY_KEYWORDS.get(category, set())))
    if category != "other":
        tags.add(category)
    return sorted(tags)[:8]


def normalize_articles(articles: pd.DataFrame | list[dict[str, Any]]) -> pd.DataFrame:
    df = pd.DataFrame(articles).copy()
    required = ["id", "title", "url", "source", "published_at", "snippet", "text"]
    for column in required:
        if column not in df.columns:
            df[column] = ""
    if df["id"].eq("").all():
        df["id"] = [f"row-{idx + 1}" for idx in range(len(df))]

    df["title"] = df["title"].fillna("").astype(str).str.strip()
    df["url"] = df["url"].fillna("").astype(str).str.strip()
    df["source"] = df["source"].fillna("Unknown").astype(str).str.strip()
    df["snippet"] = df["snippet"].fillna("").astype(str).str.strip()
    df["text"] = df["text"].fillna("").astype(str).str.strip()
    df["published_at"] = df["published_at"].fillna("").astype(str).str.slice(0, 10)
    df["canonical_url"] = df["url"].map(canonical_url)
    df["domain"] = df["canonical_url"].map(domain_from_url)
    df["normalized_title"] = df["title"].map(normalize_title)
    df["dedup_text"] = (df["title"] + " " + df["snippet"]).map(normalize_title)
    df["source_quality"] = df["source"].map(SOURCE_QUALITY).fillna(0.55)
    df["content_length"] = (df["snippet"] + " " + df["text"]).str.len()
    return df


def filter_noise(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    allow_hits: list[list[str]] = []
    deny_hits: list[list[str]] = []
    relevance_scores: list[float] = []
    noise_reasons: list[str] = []
    is_candidates: list[bool] = []

    for _, row in df.iterrows():
        blob = _blob(row)
        allow = _keyword_hits(blob, FINTECH_KEYWORDS)
        deny = _keyword_hits(blob, NOISE_KEYWORDS)
        source_quality = float(row.get("source_quality", 0.55))
        category = detect_category(blob)

        relevance = min(5.0, 1.0 + len(allow) * 0.55 + source_quality)
        reason = ""
        is_candidate = True

        if deny and len(allow) < 3:
            is_candidate = False
            reason = "noise keywords: " + ", ".join(deny[:4])
        elif category == "other" and len(allow) < 2:
            is_candidate = False
            reason = "too few fintech/product signals"
        elif int(row.get("content_length", 0)) < 55:
            is_candidate = False
            reason = "too little content to verify"
        elif source_quality < 0.45 and len(allow) < 4:
            is_candidate = False
            reason = "low-quality source without enough evidence"

        allow_hits.append(allow)
        deny_hits.append(deny)
        relevance_scores.append(round(relevance, 2))
        noise_reasons.append(reason)
        is_candidates.append(is_candidate)

    df["allow_hits"] = allow_hits
    df["deny_hits"] = deny_hits
    df["relevance"] = relevance_scores
    df["noise_reason"] = noise_reasons
    df["is_candidate"] = is_candidates
    df["detected_category"] = [
        detect_category(_blob(row)) for _, row in df.iterrows()
    ]
    return df


def cluster_articles(candidates: pd.DataFrame, threshold: float = 0.72) -> pd.DataFrame:
    if candidates.empty:
        return candidates.assign(cluster_id=[])

    ordered = candidates.sort_values(["source_quality", "published_at"], ascending=[False, False]).copy()
    clusters: list[dict[str, Any]] = []
    cluster_ids: dict[str, str] = {}

    for _, row in ordered.iterrows():
        assigned: str | None = None
        for cluster in clusters:
            same_url = row["canonical_url"] in cluster["urls"]
            close_story = similarity(row["dedup_text"], cluster["representative_text"]) >= threshold
            same_category = row["detected_category"] == cluster["category"]
            if same_url or (same_category and close_story):
                assigned = cluster["id"]
                cluster["urls"].add(row["canonical_url"])
                cluster["titles"].append(row["title"])
                if float(row["source_quality"]) > cluster["representative_quality"]:
                    cluster["representative_title"] = row["title"]
                    cluster["representative_text"] = row["dedup_text"]
                    cluster["representative_quality"] = float(row["source_quality"])
                break

        if assigned is None:
            assigned = f"s{len(clusters) + 1:03d}"
            clusters.append(
                {
                    "id": assigned,
                    "urls": {row["canonical_url"]},
                    "titles": [row["title"]],
                    "representative_title": row["title"],
                    "representative_text": row["dedup_text"],
                    "representative_quality": float(row["source_quality"]),
                    "category": row["detected_category"],
                }
            )
        cluster_ids[str(row["id"])] = assigned

    result = candidates.copy()
    result["cluster_id"] = result["id"].astype(str).map(cluster_ids)
    return result


def _freshness_days(published_values: pd.Series) -> int:
    dates = pd.to_datetime(published_values, errors="coerce")
    if dates.dropna().empty:
        return 30
    newest = dates.max().date()
    return max(0, (datetime.now(timezone.utc).date() - newest).days)


def _novelty_score(blob: str, freshness_days: int) -> float:
    novelty_terms = {"launch", "new", "pilot", "prototype", "expands", "tests", "guidance", "consultation", "first"}
    score = 2.0 + min(2.0, len(_keyword_hits(blob, novelty_terms)) * 0.7)
    if freshness_days <= 3:
        score += 0.8
    elif freshness_days <= 7:
        score += 0.4
    return min(5.0, score)


def _impact_score(category: str, evidence_count: int, source_quality: float, relevance: float) -> float:
    base_by_category = {
        "regulation": 4.4,
        "fraud_risk": 4.2,
        "payments": 4.0,
        "banking_product": 3.8,
        "partnership": 3.4,
        "UX": 3.3,
        "market_signal": 3.2,
        "other": 2.0,
    }
    base = base_by_category.get(category, 2.5)
    evidence_bonus = min(0.5, evidence_count * 0.15)
    quality_bonus = max(0.0, source_quality - 0.65)
    relevance_bonus = max(0.0, relevance - 3.5) * 0.15
    return round(min(5.0, base + evidence_bonus + quality_bonus + relevance_bonus), 2)


def _confidence_score(evidence_count: int, source_quality: float) -> float:
    return round(min(5.0, 2.2 + evidence_count * 0.55 + source_quality * 1.2), 2)


def _summary(title: str, category: str, sources: list[str]) -> str:
    source_text = ", ".join(sources[:3])
    return (
        f"{title}. Сигнал относится к категории {category} и подтвержден источниками: {source_text}. "
        "Для банка это повод проверить влияние на продуктовые сценарии, риски или конкурентную позицию."
    )


def _why_now(category: str, evidence_count: int, freshness_days: int) -> str:
    timing = "свежий сигнал" if freshness_days <= 7 else "сигнал остается актуальным"
    if category == "regulation":
        return f"Это {timing}: регуляторные изменения быстро превращаются в требования к продуктам и compliance."
    if category == "fraud_risk":
        return f"Это {timing}: fraud/authentication механики стоит оценивать до роста потерь и давления на UX."
    if category == "payments":
        return f"Это {timing}: платежные механики быстро масштабируются через банки, сети и merchant-сценарии."
    if category == "banking_product":
        return f"Это {timing}: конкурент меняет банковский сценарий, который можно проверить в продуктовой дорожной карте."
    if evidence_count >= 2:
        return f"Это {timing}: сигнал подтверждается несколькими источниками, значит это не единичный инфоповод."
    return f"Это {timing}: тема может быть ранним индикатором изменения клиентского поведения."


def _suggested_action(category: str) -> str:
    actions = {
        "regulation": "Передать compliance/product owner и проверить влияние на текущие процессы.",
        "fraud_risk": "Проверить применимость для антифрода, KYC/AML и платежной авторизации.",
        "payments": "Сравнить механику с текущими платежными сценариями и merchant-предложением.",
        "banking_product": "Добавить в конкурентный обзор и оценить быстрый продуктовый эксперимент.",
        "UX": "Проверить UX-механику на применимость в мобильном банке.",
        "partnership": "Оценить партнерскую модель и возможный аналог для банковской экосистемы.",
        "market_signal": "Занести в стратегический radar и дождаться подтверждений от первоисточников.",
    }
    return actions.get(category, "Оставить в мониторинге и собрать дополнительные подтверждения.")


def build_signals(clustered: pd.DataFrame, use_llm: bool = False, max_llm_items: int = 10) -> list[dict[str, Any]]:
    if clustered.empty:
        return []

    llm = LLMClient() if use_llm else None
    signals: list[dict[str, Any]] = []

    for cluster_id, group in clustered.groupby("cluster_id", sort=False):
        group = group.sort_values(["source_quality", "published_at"], ascending=[False, False])
        representative = group.iloc[0]
        blob = " ".join((_blob(row) for _, row in group.iterrows()))
        category = detect_category(blob)
        tags = extract_tags(blob, category)
        evidence_count = int(group["canonical_url"].nunique())
        sources = []
        seen_urls: set[str] = set()
        for _, row in group.iterrows():
            if row["canonical_url"] in seen_urls:
                continue
            seen_urls.add(row["canonical_url"])
            sources.append(
                {"source": row["source"], "url": row["canonical_url"], "quality": round(float(row["source_quality"]), 2)}
            )
        freshness_days = _freshness_days(group["published_at"])
        relevance = round(float(group["relevance"].mean()), 2)
        source_quality = round(float(group["source_quality"].max()), 2)
        novelty = round(_novelty_score(blob, freshness_days), 2)
        impact = _impact_score(category, evidence_count, source_quality, relevance)
        confidence = _confidence_score(evidence_count, source_quality)

        score = (
            0.30 * (relevance / 5.0)
            + 0.20 * source_quality
            + 0.20 * (novelty / 5.0)
            + 0.15 * (impact / 5.0)
            + 0.15 * (min(evidence_count, 3) / 3.0)
        ) * 100
        hotness = max(1, min(5, math.ceil(score / 20)))

        signal = {
            "id": cluster_id,
            "headline": representative["title"],
            "category": category,
            "tags": tags,
            "hotness": hotness,
            "score": round(score, 1),
            "score_components": {
                "relevance": relevance,
                "source_quality": source_quality,
                "novelty": novelty,
                "impact": impact,
                "evidence_count": evidence_count,
                "confidence": confidence,
            },
            "why_now": _why_now(category, evidence_count, freshness_days),
            "summary": _summary(representative["title"], category, [str(s["source"]) for s in sources]),
            "suggested_action": _suggested_action(category),
            "sources": sources,
            "article_ids": group["id"].astype(str).tolist(),
            "deduped_titles": sorted(set(group["title"].astype(str))),
            "freshness_days": freshness_days,
        }
        signals.append(signal)

    signals.sort(key=lambda item: (item["score"], item["score_components"]["confidence"]), reverse=True)

    if llm and llm.enabled:
        for signal in signals[:max_llm_items]:
            enrichment = llm.enrich_signal(signal)
            if not enrichment:
                continue
            signal["summary"] = str(enrichment.get("summary") or signal["summary"])
            signal["why_now"] = str(enrichment.get("why_now") or signal["why_now"])
            signal["suggested_action"] = str(enrichment.get("suggested_action") or signal["suggested_action"])
            signal["category"] = str(enrichment.get("category") or signal["category"])
            if isinstance(enrichment.get("tags"), list):
                signal["tags"] = [str(tag) for tag in enrichment["tags"]][:8]
            for component in ("impact", "novelty"):
                value = enrichment.get(component)
                if isinstance(value, (int, float)):
                    signal["score_components"][component] = max(1, min(5, round(float(value), 2)))
            signal["llm_enriched"] = True
    return signals


def format_digest(signals: list[dict[str, Any]], top_n: int = 7) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Fintech TrendWatcher Digest",
        "",
        f"_Generated: {generated_at}_",
        "",
        "Короткий дайджест для продуктовой, стратегической или competitive intelligence команды банка.",
        "",
    ]
    for idx, signal in enumerate(signals[:top_n], 1):
        tags = ", ".join(signal.get("tags", [])[:6])
        source_links = "; ".join(
            f"{source['source']} ({source['url']})" for source in signal.get("sources", [])[:3]
        )
        lines.extend(
            [
                f"## {idx}. {signal['headline']}",
                "",
                f"- Hotness: {signal['hotness']}/5 ({signal['score']}/100)",
                f"- Category/tags: {signal['category']} | {tags}",
                f"- Why now: {signal['why_now']}",
                f"- Summary: {signal['summary']}",
                f"- Suggested action: {signal['suggested_action']}",
                f"- Sources: {source_links}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def run_pipeline(
    articles: pd.DataFrame | list[dict[str, Any]] | None = None,
    use_llm: bool = False,
    max_llm_items: int = 10,
    top_n: int = 7,
) -> PipelineResult:
    raw = pd.DataFrame(articles if articles is not None else demo_articles())
    normalized = normalize_articles(raw)
    filtered = filter_noise(normalized)
    candidates = filtered[filtered["is_candidate"]].copy()
    rejected = filtered[~filtered["is_candidate"]].copy()
    clustered = cluster_articles(candidates)
    signals = build_signals(clustered, use_llm=use_llm, max_llm_items=max_llm_items)
    digest = format_digest(signals, top_n=top_n)
    return PipelineResult(
        raw_articles=raw,
        normalized_articles=filtered,
        candidate_articles=clustered,
        rejected_articles=rejected,
        signals=signals,
        digest_markdown=digest,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def save_outputs(result: PipelineResult, output_dir: str | Path = "data") -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result.normalized_articles.to_csv(output / "articles.csv", index=False)
    result.candidate_articles.to_csv(output / "candidates.csv", index=False)
    result.rejected_articles.to_csv(output / "rejected.csv", index=False)
    (output / "signals.json").write_text(json.dumps(result.signals, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "digest.md").write_text(result.digest_markdown, encoding="utf-8")
