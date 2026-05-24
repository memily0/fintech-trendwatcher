"""Manual score coefficient configuration."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


FEATURES = ("relevance", "source_quality", "novelty", "impact", "evidence_score")

DEFAULT_WEIGHTS: dict[str, float] = {
    "relevance": 0.30,
    "source_quality": 0.20,
    "novelty": 0.20,
    "impact": 0.15,
    "evidence_score": 0.15,
}

WEIGHTS_PATH = Path("data/score_weights.json")
WEIGHT_PRECISION = 6


def _clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def _float_or_default(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_weights(weights: dict[str, Any] | None) -> dict[str, float]:
    cleaned: dict[str, float] = {}
    for feature in FEATURES:
        cleaned[feature] = _clamp(_float_or_default((weights or {}).get(feature), DEFAULT_WEIGHTS[feature]))
    return cleaned


def normalize_weights(weights: dict[str, Any] | None) -> dict[str, float]:
    cleaned = _clean_weights(weights)
    total = sum(cleaned.values())
    if total <= 0:
        cleaned = DEFAULT_WEIGHTS.copy()
        total = sum(cleaned.values())
    normalized = {feature: round(cleaned[feature] / total, WEIGHT_PRECISION) for feature in FEATURES}
    rounding_diff = round(1.0 - sum(normalized.values()), WEIGHT_PRECISION)
    if rounding_diff:
        adjustment_feature = max(FEATURES, key=lambda feature: normalized[feature])
        normalized[adjustment_feature] = round(normalized[adjustment_feature] + rounding_diff, WEIGHT_PRECISION)
    return normalized


def load_score_weights(path: str | Path = WEIGHTS_PATH) -> dict[str, float]:
    weights_path = Path(path)
    if not weights_path.exists():
        return DEFAULT_WEIGHTS.copy()
    try:
        payload = json.loads(weights_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_WEIGHTS.copy()
    weights = payload.get("weights", payload) if isinstance(payload, dict) else {}
    return normalize_weights(weights)


def save_score_weights(weights: dict[str, Any], path: str | Path = WEIGHTS_PATH) -> dict[str, float]:
    normalized = normalize_weights(weights)
    weights_path = Path(path)
    weights_path.parent.mkdir(parents=True, exist_ok=True)
    weights_path.write_text(json.dumps({"weights": normalized}, ensure_ascii=False, indent=2), encoding="utf-8")
    return normalized


def feature_vector(components: dict[str, Any]) -> dict[str, float]:
    return {
        "relevance": _clamp(_float_or_default(components.get("relevance")) / 5.0),
        "source_quality": _clamp(_float_or_default(components.get("source_quality"))),
        "novelty": _clamp(_float_or_default(components.get("novelty")) / 5.0),
        "impact": _clamp(_float_or_default(components.get("impact")) / 5.0),
        "evidence_score": _clamp(_float_or_default(components.get("evidence_score"))),
    }


def score_from_components(components: dict[str, Any], weights: dict[str, Any] | None = None) -> float:
    active_weights = normalize_weights(weights or load_score_weights())
    features = feature_vector(components)
    score = sum(active_weights[feature] * features[feature] for feature in FEATURES) * 100
    return round(max(0.0, min(100.0, score)), 1)


def hotness_from_score(score: float) -> int:
    return max(1, min(5, math.ceil(float(score) / 20)))
