"""Transparent fintech news pipeline for the MVP."""

from __future__ import annotations

import html
import json
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
from .score_weights import hotness_from_score, load_score_weights, score_from_components


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
    "aml",
    "bnpl",
    "kyc",
    "qr",
    "акции",
    "антифрод",
    "банк",
    "банк россии",
    "банки",
    "банковский",
    "биометрия",
    "быстрые платежи",
    "вклад",
    "депозит",
    "заем",
    "идентификация",
    "карта",
    "карты",
    "кешбэк",
    "кошелек",
    "кредит",
    "кредитование",
    "маркетплейс",
    "мерчант",
    "мобильное приложение",
    "мошенничество",
    "накопительный счет",
    "открытый банкинг",
    "партнерство",
    "перевод",
    "переводы",
    "персональные данные",
    "платеж",
    "платежи",
    "подписка",
    "рассрочка",
    "регулирование",
    "регулятор",
    "риск",
    "сбп",
    "скоринг",
    "финтех",
    "цифровой рубль",
    "цб",
    "эквайринг",
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
    "seo",
    "акции выросли",
    "биткоин",
    "вакансия",
    "вебинар",
    "котировки",
    "криптовалюта",
    "драгоценные металлы",
    "курс",
    "монета",
    "номиналом",
    "нумизматика",
    "обзор рынка",
    "обучение",
    "орден",
    "памятная монета",
    "памятный выпуск",
    "прогноз цены",
    "промо",
    "реклама",
    "серебряная монета",
    "серия",
    "скидка на курс",
    "спонсорский",
    "трейдеры",
}

CBR_COLLECTIBLE_NOISE = {
    "драгоценные металлы",
    "коллекционная монета",
    "монета",
    "номиналом",
    "нумизматика",
    "орден",
    "памятная монета",
    "памятный выпуск",
    "серебряная монета",
}

STRONG_CBR_FINTECH_TRIGGERS = {
    "aml",
    "kyc",
    "антифрод",
    "биометрия",
    "вклад",
    "кредит",
    "перевод",
    "переводы",
    "персональные данные",
    "платежи",
    "регулирование",
    "сбп",
    "цифровой рубль",
}

CATEGORY_KEYWORDS: dict[str, set[str]] = {
    "payments": {
        "checkout",
        "merchant",
        "payment",
        "payments",
        "qr",
        "refunds",
        "settlement",
        "tap to pay",
        "vrp",
        "быстрые платежи",
        "карта",
        "карты",
        "перевод",
        "переводы",
        "платеж",
        "платежи",
        "сбп",
        "эквайринг",
    },
    "banking_product": {
        "account",
        "banking",
        "bnpl",
        "budgeting",
        "debit",
        "deposit",
        "loan",
        "loans",
        "savings",
        "sme",
        "банковский продукт",
        "вклад",
        "депозит",
        "заем",
        "ипотека",
        "кредит",
        "накопительный счет",
        "рассрочка",
        "счет",
    },
    "UX": {
        "app",
        "biometric",
        "consent",
        "dashboard",
        "experience",
        "loyalty",
        "mobile",
        "palm",
        "wallet",
        "биометрия",
        "интерфейс",
        "кешбэк",
        "кошелек",
        "лояльность",
        "мобильное приложение",
        "онбординг",
        "приложение",
    },
    "partnership": {
        "embedded insurance",
        "merchant-funded",
        "partner",
        "partners",
        "partnership",
        "интеграция",
        "маркетплейс",
        "партнер",
        "партнерство",
        "совместно",
        "экосистема",
    },
    "regulation": {
        "central bank",
        "consultation",
        "disclosure",
        "ecb",
        "guidance",
        "regulator",
        "rules",
        "банк россии",
        "закон",
        "надзор",
        "персональные данные",
        "раскрытие",
        "регулирование",
        "регулятор",
        "требование",
        "цифровой рубль",
        "цб",
    },
    "market_signal": {
        "bis",
        "cross-border",
        "market",
        "project",
        "tokenized",
        "запуск",
        "исследование",
        "пилот",
        "развитие",
        "рынок",
        "стратегия",
        "тестирование",
        "тренд",
    },
    "fraud_risk": {
        "ai",
        "aml",
        "authentication",
        "fraud",
        "kyc",
        "mule",
        "passkey",
        "risk",
        "антифрод",
        "безопасность",
        "биометрия",
        "идентификация",
        "мошенничество",
        "подозрительные операции",
        "риск",
    },
}

SOURCE_TIERS: dict[str, float] = {
    "regulator_or_public_authority": 1.00,
    "official_company_source": 0.90,
    "specialized_fintech_media": 0.80,
    "general_business_or_tech_media": 0.70,
    "repost_or_low_confidence": 0.45,
}

SOURCE_TIER_BY_SOURCE: dict[str, str] = {
    "BIS": "regulator_or_public_authority",
    "ECB": "regulator_or_public_authority",
    "CFPB": "regulator_or_public_authority",
    "Bank of England": "regulator_or_public_authority",
    "Банк России — новости": "regulator_or_public_authority",
    "Банк России — события": "regulator_or_public_authority",
    "Банк России — пресс-релизы": "regulator_or_public_authority",
    "Regulator": "regulator_or_public_authority",
    "Visa": "official_company_source",
    "Mastercard": "official_company_source",
    "JPMorgan": "official_company_source",
    "PayPal": "official_company_source",
    "Open Banking UK": "official_company_source",
    "Stripe Blog": "official_company_source",
    "Finextra": "specialized_fintech_media",
    "The Paypers": "specialized_fintech_media",
    "PYMNTS": "specialized_fintech_media",
    "РБК — новости": "general_business_or_tech_media",
    "TechCrunch": "general_business_or_tech_media",
    "Fintech Repost": "repost_or_low_confidence",
}

SOURCE_QUALITY: dict[str, float] = {
    source: SOURCE_TIERS[tier] for source, tier in SOURCE_TIER_BY_SOURCE.items()
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
    dedup_method_used: str = "fuzzy"
    warnings: list[str] | None = None


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


def clean_text(value: str) -> str:
    value = html.unescape(str(value or ""))
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("\xa0", " ")
    return " ".join(value.split())


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
    return sorted(keyword for keyword in keywords if keyword.lower() in blob)


def _is_cbr_source(source: str) -> bool:
    source = source.lower()
    return "банк россии" in source or source == "цб" or "central bank of russia" in source


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

    df["title"] = df["title"].fillna("").astype(str).map(clean_text)
    df["url"] = df["url"].fillna("").astype(str).str.strip()
    df["source"] = df["source"].fillna("Unknown").astype(str).map(clean_text)
    df["snippet"] = df["snippet"].fillna("").astype(str).map(clean_text)
    df["text"] = df["text"].fillna("").astype(str).map(clean_text)
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
        collectible_noise = _keyword_hits(blob, CBR_COLLECTIBLE_NOISE)
        strong_cbr_fintech = _keyword_hits(blob, STRONG_CBR_FINTECH_TRIGGERS)
        source_quality = float(row.get("source_quality", 0.55))
        category = detect_category(blob)

        relevance = min(5.0, 1.0 + len(allow) * 0.55 + source_quality)
        reason = ""
        is_candidate = True

        if _is_cbr_source(str(row.get("source", ""))) and collectible_noise and not strong_cbr_fintech:
            is_candidate = False
            reason = "публикация Банка России, но не финтех/банковский продуктовый сигнал"
        elif deny and len(allow) < 3:
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
    df["candidate_score"] = [round(score * 20, 1) for score in relevance_scores]
    df["noise_reason"] = noise_reasons
    df["is_candidate"] = is_candidates
    df["detected_category"] = [
        detect_category(_blob(row)) for _, row in df.iterrows()
    ]
    return df


def _empty_clustered(candidates: pd.DataFrame, method: str, threshold: float) -> pd.DataFrame:
    result = candidates.copy()
    result["cluster_id"] = pd.Series(dtype="object")
    result["dedup_method"] = method
    result["dedup_threshold"] = threshold
    result["dedup_similarity"] = pd.Series(dtype="float")
    return result


def _cluster_articles_fuzzy(candidates: pd.DataFrame, threshold: float = 0.72) -> pd.DataFrame:
    if candidates.empty:
        return _empty_clustered(candidates, "fuzzy", threshold)

    ordered = candidates.sort_values(["source_quality", "published_at"], ascending=[False, False]).copy()
    clusters: list[dict[str, Any]] = []
    cluster_ids: dict[str, str] = {}
    cluster_scores: dict[str, float] = {}

    for _, row in ordered.iterrows():
        assigned: str | None = None
        assigned_score = 1.0
        for cluster in clusters:
            same_url = row["canonical_url"] in cluster["urls"]
            story_similarity = similarity(row["dedup_text"], cluster["representative_text"])
            close_story = story_similarity >= threshold
            same_category = row["detected_category"] == cluster["category"]
            if same_url or (same_category and close_story):
                assigned = cluster["id"]
                assigned_score = 1.0 if same_url else round(story_similarity, 3)
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
        cluster_scores[str(row["id"])] = assigned_score

    result = candidates.copy()
    result["cluster_id"] = result["id"].astype(str).map(cluster_ids)
    result["dedup_method"] = "fuzzy"
    result["dedup_threshold"] = threshold
    result["dedup_similarity"] = result["id"].astype(str).map(cluster_scores).fillna(1.0)
    return result


def _cluster_articles_tfidf(candidates: pd.DataFrame, threshold: float = 0.58) -> pd.DataFrame:
    if candidates.empty:
        return _empty_clustered(candidates, "tfidf", threshold)

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except Exception as exc:  # pragma: no cover - exercised when sklearn is absent.
        raise RuntimeError(f"sklearn is unavailable: {exc}") from exc

    ordered = candidates.sort_values(["source_quality", "published_at"], ascending=[False, False]).copy()
    texts = (ordered["title"].fillna("") + " " + ordered["snippet"].fillna("")).map(normalize_title).tolist()
    if len(texts) < 2:
        result = ordered.copy()
        result["cluster_id"] = [f"s{idx + 1:03d}" for idx in range(len(result))]
        result["dedup_method"] = "tfidf"
        result["dedup_threshold"] = threshold
        result["dedup_similarity"] = 1.0
        return result

    try:
        matrix = TfidfVectorizer(ngram_range=(1, 2), min_df=1).fit_transform(texts)
        similarities = cosine_similarity(matrix)
    except Exception as exc:
        raise RuntimeError(f"TF-IDF vectorization failed: {exc}") from exc

    clusters: list[dict[str, Any]] = []
    cluster_ids: dict[str, str] = {}
    cluster_scores: dict[str, float] = {}

    for row_pos, (_, row) in enumerate(ordered.iterrows()):
        assigned: str | None = None
        assigned_score = 1.0
        for cluster in clusters:
            same_url = row["canonical_url"] in cluster["urls"]
            same_category = row["detected_category"] == cluster["category"]
            tfidf_similarity = max(float(similarities[row_pos, idx]) for idx in cluster["row_positions"])
            if same_url or (same_category and tfidf_similarity >= threshold):
                assigned = cluster["id"]
                assigned_score = 1.0 if same_url else round(tfidf_similarity, 3)
                cluster["urls"].add(row["canonical_url"])
                cluster["titles"].append(row["title"])
                cluster["row_positions"].append(row_pos)
                if float(row["source_quality"]) > cluster["representative_quality"]:
                    cluster["representative_quality"] = float(row["source_quality"])
                break

        if assigned is None:
            assigned = f"s{len(clusters) + 1:03d}"
            clusters.append(
                {
                    "id": assigned,
                    "urls": {row["canonical_url"]},
                    "titles": [row["title"]],
                    "representative_quality": float(row["source_quality"]),
                    "category": row["detected_category"],
                    "row_positions": [row_pos],
                }
            )
        cluster_ids[str(row["id"])] = assigned
        cluster_scores[str(row["id"])] = assigned_score

    result = candidates.copy()
    result["cluster_id"] = result["id"].astype(str).map(cluster_ids)
    result["dedup_method"] = "tfidf"
    result["dedup_threshold"] = threshold
    result["dedup_similarity"] = result["id"].astype(str).map(cluster_scores).fillna(1.0)
    return result


def cluster_articles(
    candidates: pd.DataFrame,
    method: str = "fuzzy",
    fuzzy_threshold: float = 0.72,
    tfidf_threshold: float = 0.58,
) -> tuple[pd.DataFrame, str, list[str]]:
    method = method.lower().strip().replace("-", "")
    warnings: list[str] = []
    if method == "tfidf":
        try:
            return _cluster_articles_tfidf(candidates, tfidf_threshold), "tfidf", warnings
        except Exception as exc:
            warnings.append(f"TF-IDF дедупликация недоступна, использован fallback fuzzy: {exc}")
    elif method != "fuzzy":
        warnings.append(f"Неизвестный метод дедупликации '{method}', использован fuzzy.")
    return _cluster_articles_fuzzy(candidates, fuzzy_threshold), "fuzzy", warnings


def _freshness_days(published_values: pd.Series) -> int:
    dates = pd.to_datetime(published_values, errors="coerce")
    if dates.dropna().empty:
        return 30
    newest = dates.max().date()
    return max(0, (datetime.now(timezone.utc).date() - newest).days)


def _latest_published_at(published_values: pd.Series) -> str:
    dates = pd.to_datetime(published_values, errors="coerce")
    if dates.dropna().empty:
        return ""
    return dates.max().date().isoformat()


def _has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[а-яА-ЯёЁ]", text))


def format_publication_date(raw_date: str, source: str = "") -> str:
    parsed = pd.to_datetime(raw_date, errors="coerce")
    if pd.isna(parsed):
        return "дата не указана"
    if _has_cyrillic(source):
        return parsed.strftime("%d.%m.%Y")
    month = parsed.strftime("%b")
    return f"{parsed.day} {month} {parsed.year}"


def format_source_date(source: str, raw_date: str) -> str:
    return f"{source} · {format_publication_date(raw_date, source)}"


def freshness_label(days: int) -> str:
    if days <= 0:
        return "сегодня"
    if days == 1:
        return "1 день назад"
    if days <= 4:
        return f"{days} дня назад"
    if days <= 14:
        return f"{days} дней назад"
    return "старше двух недель"


def _novelty_score(blob: str, freshness_days: int) -> float:
    novelty_terms = {
        "consultation",
        "expands",
        "first",
        "guidance",
        "launch",
        "new",
        "pilot",
        "prototype",
        "tests",
        "запуск",
        "исследование",
        "новый",
        "пилот",
        "развитие",
        "тестирование",
    }
    score = 2.0 + min(2.0, len(_keyword_hits(blob, novelty_terms)) * 0.7)
    if freshness_days <= 3:
        score += 0.8
    elif freshness_days <= 7:
        score += 0.4
    return min(5.0, score)


def _impact_score(category: str, evidence_score: float, source_quality: float, relevance: float) -> float:
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
    evidence_bonus = max(0.0, evidence_score) * 0.5
    quality_bonus = max(0.0, source_quality - 0.65)
    relevance_bonus = max(0.0, relevance - 3.5) * 0.15
    return round(min(5.0, base + evidence_bonus + quality_bonus + relevance_bonus), 2)


def _confidence_score(evidence_score: float, source_quality: float) -> float:
    evidence_bonus = max(0.0, evidence_score) * 1.65
    return round(min(5.0, 2.2 + evidence_bonus + source_quality * 1.2), 2)


def _normalized_confidence(confidence: float) -> float:
    return max(0.0, min(1.0, float(confidence) / 5.0))


def _signal_level(score: float, confidence: float) -> str:
    if score >= 80 and confidence >= 0.70:
        return "strong"
    if score >= 65 and confidence >= 0.50:
        return "medium"
    return "weak"


def _score_explanation(score: float, components: dict[str, Any]) -> str:
    if score >= 80:
        level = "Высокий score"
    elif score >= 60:
        level = "Средний score"
    else:
        level = "Наблюдательный score"

    drivers: list[str] = []
    if float(components["relevance"]) >= 4.0:
        drivers.append("много финтех-триггеров")
    if float(components["source_quality"]) >= 0.9:
        drivers.append("сильный первоисточник")
    elif float(components["source_quality"]) >= 0.75:
        drivers.append("надежное отраслевое медиа")
    if float(components["novelty"]) >= 4.0:
        drivers.append("есть признаки свежего запуска/пилота")
    evidence_score = float(components.get("evidence_score", 0))
    if evidence_score >= 0.75:
        drivers.append("есть качественные похожие подтверждения")
    elif evidence_score >= 0.45:
        drivers.append("есть подтверждения, но их качество или схожесть умеренные")
    if float(components["impact"]) >= 4.0:
        drivers.append("высокая потенциальная значимость для банка")

    if not drivers:
        drivers.append("тема релевантна, но качество подтверждений или новизна пока невысокие")
    return f"{level}: " + "; ".join(drivers[:4]) + "."


def _clean_excerpt(text: str, max_chars: int = 420) -> str:
    text = clean_text(text)
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rsplit(" ", 1)[0]
    return clipped.rstrip(".,;:") + "..."


def _summary(title: str, category: str, sources: list[str], snippet: str = "", text: str = "") -> str:
    excerpt = _clean_excerpt(snippet or text)
    title_clean = _clean_excerpt(title, max_chars=220)
    if excerpt and excerpt.lower() not in title_clean.lower() and len(excerpt) >= 40:
        return f"{title_clean}. {excerpt}"
    if excerpt and len(excerpt) >= 25:
        return f"{title_clean}. {excerpt}"
    source_text = ", ".join(sources[:3])
    return (
        f"{title_clean}. В RSS доступен короткий фрагмент без полного текста; событие отнесено к категории "
        f"{category} и подтверждается источниками: {source_text}."
    )


def _why_important_for_bank(
    category: str,
    score: float,
    confidence: float,
    freshness_days: int,
    source_quality: float,
    evidence_score: float,
) -> str:
    level = _signal_level(score, confidence)
    timing = "Сигнал свежий" if freshness_days <= 7 else "Сигнал не новый, но может оставаться актуальным"
    evidence = (
        "подтверждения хорошо совпадают с темой и идут из надежных источников"
        if evidence_score >= 0.7
        else "подтверждения требуют ручной проверки качества и схожести"
    )
    source_note = "источник выглядит надежным" if source_quality >= 0.85 else "источник требует дополнительной проверки"

    if category == "regulation":
        base = (
            "Сигнал затрагивает регуляторную повестку: такие изменения могут повлиять на документы, "
            "клиентские коммуникации, compliance-процессы или правила запуска продукта."
        )
    elif category == "fraud_risk":
        base = (
            "Сигнал связан с fraud/security: такие изменения могут повлиять на потери, KYC/AML-процессы, "
            "авторизацию или баланс между безопасностью и UX."
        )
    elif category == "payments":
        base = (
            "Сигнал затрагивает платежный сценарий: изменения в платежах быстро влияют на ожидания клиентов "
            "к скорости, удобству, комиссии и доступности операций."
        )
    elif category == "banking_product":
        base = (
            "Сигнал связан с банковским продуктом: он может указывать на изменение конкурентного предложения "
            "или ожиданий клиентов."
        )
    elif category == "UX":
        base = (
            "Сигнал затрагивает клиентский опыт: UX-механики в финтехе могут быстро становиться новым "
            "стандартом удобства в мобильном банке или onboarding."
        )
    elif category == "partnership":
        base = (
            "Сигнал связан с партнерской моделью: такие новости могут показывать новый способ дистрибуции, "
            "монетизации или расширения банковской экосистемы."
        )
    elif category == "market_signal":
        base = (
            "Сигнал отражает рыночный тренд: он может быть ранним индикатором изменения поведения клиентов, "
            "конкурентов или финтех-инфраструктуры."
        )
    else:
        base = "Сигнал может быть полезен для мониторинга, но его прикладное значение нужно проверить вручную."

    caution = " Уровень сигнала слабый, поэтому это аналитическая подсказка, а не основание для решения." if level == "weak" else ""
    return f"{base} {timing}; {evidence}; {source_note}.{caution}"


def _recommended_action(category: str, score: float, components: dict[str, Any]) -> str:
    confidence = _normalized_confidence(float(components.get("confidence", 0)))
    level = _signal_level(score, confidence)

    if level == "weak":
        return (
            "Оставить сигнал в мониторинге: проверить первоисточник, дождаться дополнительных подтверждений "
            "и не выносить в продуктовые решения без ручной валидации."
        )

    if level == "medium":
        medium_actions = {
            "regulation": "Добавить в regulatory radar, проверить первоисточник вручную и оценить возможное влияние на процессы без запуска отдельной инициативы.",
            "fraud_risk": "Добавить в risk/anti-fraud radar, вручную проверить применимость к текущим операциям, KYC/AML или авторизации.",
            "payments": "Добавить в payments radar, вручную сравнить с текущими переводами, оплатой или acquiring-сценариями и собрать дополнительные подтверждения.",
            "banking_product": "Добавить в product discovery radar, сравнить с текущим клиентским сценарием и не превращать сразу в продуктовую инициативу.",
            "UX": "Добавить в UX/onboarding radar, вручную проверить механику и оценить, где она может снизить friction.",
            "partnership": "Добавить в партнерский radar, проверить участников модели и дождаться подтверждений от первоисточников.",
            "market_signal": "Добавить в аналитический radar, проверить тренд вручную и дождаться подтверждений от первоисточников.",
        }
        return medium_actions.get(
            category,
            "Добавить сигнал в radar, проверить вручную и не превращать сразу в продуктовую инициативу.",
        )

    actions = {
        "regulation": "Передать сигнал compliance/legal и владельцу затронутого продукта. Проверить, нужны ли изменения в документах, клиентских сценариях, процессах идентификации, коммуникации или отчетности.",
        "fraud_risk": "Передать risk/anti-fraud команде. Проверить, есть ли похожий риск в текущих операциях, KYC/AML, авторизации или мониторинге транзакций.",
        "payments": "Передать владельцу платежного сценария. Сравнить механику с текущими переводами, оплатой, checkout/acquiring или merchant-сценариями и сформулировать гипотезу для discovery или A/B-теста.",
        "banking_product": "Передать продуктовой команде для discovery. Сравнить с текущим предложением, клиентским путем и конкурентными альтернативами.",
        "UX": "Передать команде мобильного банка или onboarding. Проверить, можно ли адаптировать механику в текущем клиентском пути и где она может снизить friction.",
        "partnership": "Разобрать партнерскую модель: кто участники, какая ценность для клиента, какой канал дистрибуции используется и можно ли воспроизвести аналогичный сценарий.",
        "market_signal": "Добавить в аналитический обзор для продуктовой/стратегической команды. Проверить, влияет ли тренд на клиентский спрос, конкурентов или приоритеты roadmap.",
    }
    return actions.get(category, "Передать профильной команде для ручной проверки и формулирования гипотезы.")


def _weighted_evidence_score(group: pd.DataFrame) -> float:
    """Score evidence by source quality and similarity within the cluster."""

    best_contribution_by_url: dict[str, float] = {}
    for _, row in group.iterrows():
        url = str(row.get("canonical_url") or row.get("url") or row.get("id"))
        try:
            similarity_score = float(row.get("dedup_similarity", 1.0))
        except (TypeError, ValueError):
            similarity_score = 1.0
        try:
            source_quality = float(row.get("source_quality", 0.55))
        except (TypeError, ValueError):
            source_quality = 0.55

        similarity_score = max(0.0, min(1.0, similarity_score))
        source_quality = max(0.0, min(1.0, source_quality))
        contribution = similarity_score * source_quality
        best_contribution_by_url[url] = max(best_contribution_by_url.get(url, 0.0), contribution)

    if not best_contribution_by_url:
        return 0.0

    contributions = list(best_contribution_by_url.values())
    return round(sum(contributions), 2)


def build_signals(
    clustered: pd.DataFrame,
    use_llm: bool = False,
    max_llm_items: int = 10,
    score_weights: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if clustered.empty:
        return []

    llm = LLMClient() if use_llm else None
    active_score_weights = score_weights or load_score_weights()
    signals: list[dict[str, Any]] = []

    for cluster_id, group in clustered.groupby("cluster_id", sort=False):
        group = group.sort_values(["source_quality", "published_at"], ascending=[False, False])
        representative = group.iloc[0]
        blob = " ".join((_blob(row) for _, row in group.iterrows()))
        category = detect_category(blob)
        tags = extract_tags(blob, category)
        evidence_score = _weighted_evidence_score(group)
        published_at = _latest_published_at(group["published_at"])
        representative_snippet = str(representative.get("snippet", ""))
        representative_text = str(representative.get("text", ""))
        has_loaded_text = bool(
            representative_text
            and representative_text.strip() != representative_snippet.strip()
            and len(representative_text.strip()) > len(representative_snippet.strip()) + 60
        )
        sources = []
        seen_urls: set[str] = set()
        for _, row in group.iterrows():
            if row["canonical_url"] in seen_urls:
                continue
            seen_urls.add(row["canonical_url"])
            sources.append(
                {
                    "source": row["source"],
                    "url": row["canonical_url"],
                    "quality": round(float(row["source_quality"]), 2),
                    "published_at": row["published_at"],
                    "date_label": format_publication_date(row["published_at"], row["source"]),
                    "source_date": format_source_date(row["source"], row["published_at"]),
                }
            )
        freshness_days = _freshness_days(group["published_at"])
        relevance = round(float(group["relevance"].mean()), 2)
        source_quality = round(float(group["source_quality"].max()), 2)
        novelty = round(_novelty_score(blob, freshness_days), 2)
        impact = _impact_score(category, evidence_score, source_quality, relevance)
        confidence = _confidence_score(evidence_score, source_quality)
        score_components = {
            "relevance": relevance,
            "source_quality": source_quality,
            "novelty": novelty,
            "impact": impact,
            "evidence_score": evidence_score,
            "confidence": confidence,
        }
        score = score_from_components(score_components, active_score_weights)
        hotness = hotness_from_score(score)

        signal = {
            "id": cluster_id,
            "headline": representative["title"],
            "category": category,
            "tags": tags,
            "hotness": hotness,
            "score": round(score, 1),
            "published_at": published_at,
            "date_label": format_publication_date(published_at, str(representative["source"])),
            "freshness_label": freshness_label(freshness_days),
            "score_components": score_components,
            "score_weights": active_score_weights,
            "score_explanation": _score_explanation(
                score,
                score_components,
            ),
            "signal_level": _signal_level(score, _normalized_confidence(confidence)),
            "why_now": _why_important_for_bank(
                category,
                score,
                _normalized_confidence(confidence),
                freshness_days,
                source_quality,
                evidence_score,
            ),
            "summary": _summary(
                representative["title"],
                category,
                [str(s["source"]) for s in sources],
                snippet=representative_snippet,
                text=representative_text,
            ),
            "suggested_action": _recommended_action(category, score, score_components),
            "sources": sources,
            "article_ids": group["id"].astype(str).tolist(),
            "deduped_titles": sorted(set(group["title"].astype(str))),
            "freshness_days": freshness_days,
            "context_note": (
                "Полный текст не загружался, анализ основан на RSS snippet."
                if not has_loaded_text
                else "Использован расширенный текст/snippet из входных данных."
            ),
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
            signal["category"] = str(enrichment.get("category") or signal["category"])
            if isinstance(enrichment.get("tags"), list):
                signal["tags"] = [str(tag) for tag in enrichment["tags"]][:8]
            for component in ("impact", "novelty"):
                value = enrichment.get(component)
                if isinstance(value, (int, float)):
                    signal["score_components"][component] = max(1, min(5, round(float(value), 2)))
            signal["score"] = score_from_components(signal["score_components"], active_score_weights)
            signal["hotness"] = hotness_from_score(signal["score"])
            signal["score_explanation"] = _score_explanation(signal["score"], signal["score_components"])
            signal["signal_level"] = _signal_level(
                signal["score"],
                _normalized_confidence(float(signal["score_components"].get("confidence", 0))),
            )
            signal["suggested_action"] = _recommended_action(signal["category"], signal["score"], signal["score_components"])
            signal["llm_enriched"] = True
        signals.sort(key=lambda item: (item["score"], item["score_components"]["confidence"]), reverse=True)
    return signals


def format_digest(signals: list[dict[str, Any]], top_n: int = 7) -> str:
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Дайджест Fintech TrendWatcher",
        "",
        f"_Сформировано: {generated_at}_",
        "",
        "Короткий дайджест для продуктовой, стратегической или команды конкурентной аналитики банка.",
        "",
    ]
    for idx, signal in enumerate(signals[:top_n], 1):
        tags = ", ".join(signal.get("tags", [])[:6])
        source_links = "; ".join(
            f"{source.get('source_date', source['source'])} ({source['url']})" for source in signal.get("sources", [])[:3]
        )
        lines.extend(
            [
                f"## {idx}. {signal['headline']}",
                "",
                f"- Дата сигнала: {signal.get('date_label', 'дата не указана')} · свежесть: {signal.get('freshness_label', 'неизвестно')}",
                f"- Важность: {signal['hotness']}/5 ({signal['score']}/100)",
                f"- Категория/теги: {signal['category']} | {tags}",
                f"- Почему score такой: {signal.get('score_explanation', '')}",
                f"- Почему это может быть важно: {signal['why_now']}",
                f"- Кратко: {signal['summary']}",
                f"- Следующий шаг для команды: {signal['suggested_action']}",
                f"- Источники: {source_links}",
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def run_pipeline(
    articles: pd.DataFrame | list[dict[str, Any]] | None = None,
    use_llm: bool = False,
    max_llm_items: int = 10,
    top_n: int = 7,
    dedup_method: str = "fuzzy",
    fuzzy_threshold: float = 0.72,
    tfidf_threshold: float = 0.58,
    score_weights: dict[str, Any] | None = None,
) -> PipelineResult:
    raw = pd.DataFrame(articles if articles is not None else demo_articles())
    normalized = normalize_articles(raw)
    filtered = filter_noise(normalized)
    candidates = filtered[filtered["is_candidate"]].copy()
    rejected = filtered[~filtered["is_candidate"]].copy()
    clustered, dedup_method_used, warnings = cluster_articles(
        candidates,
        method=dedup_method,
        fuzzy_threshold=fuzzy_threshold,
        tfidf_threshold=tfidf_threshold,
    )
    signals = build_signals(
        clustered,
        use_llm=use_llm,
        max_llm_items=max_llm_items,
        score_weights=score_weights,
    )
    digest = format_digest(signals, top_n=top_n)
    return PipelineResult(
        raw_articles=raw,
        normalized_articles=filtered,
        candidate_articles=clustered,
        rejected_articles=rejected,
        signals=signals,
        digest_markdown=digest,
        generated_at=datetime.now(timezone.utc).isoformat(),
        dedup_method_used=dedup_method_used,
        warnings=warnings,
    )


def save_outputs(result: PipelineResult, output_dir: str | Path = "data") -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    result.normalized_articles.to_csv(output / "articles.csv", index=False)
    result.candidate_articles.to_csv(output / "candidates.csv", index=False)
    result.rejected_articles.to_csv(output / "rejected.csv", index=False)
    (output / "signals.json").write_text(json.dumps(result.signals, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "digest.md").write_text(result.digest_markdown, encoding="utf-8")
