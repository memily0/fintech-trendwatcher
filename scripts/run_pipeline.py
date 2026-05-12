#!/usr/bin/env python3
"""Run the TrendWatcher pipeline and export demo artifacts."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trendwatcher.pipeline import run_pipeline, save_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Fintech TrendWatcher MVP pipeline")
    parser.add_argument("--input-csv", type=Path, default=None, help="Optional CSV with title,url,source,published_at,snippet,text")
    parser.add_argument("--output-dir", type=Path, default=Path("data"), help="Where to write artifacts")
    parser.add_argument("--use-llm", action="store_true", help="Enable optional OpenRouter enrichment")
    parser.add_argument("--max-llm-items", type=int, default=8, help="Max top signals to enrich with LLM")
    parser.add_argument("--top-n", type=int, default=7, help="Signals in the final digest")
    parser.add_argument("--dedup-method", choices=["fuzzy", "tfidf", "tf-idf"], default="fuzzy", help="Deduplication method")
    parser.add_argument("--fuzzy-threshold", type=float, default=0.72, help="Fuzzy duplicate threshold")
    parser.add_argument("--tfidf-threshold", type=float, default=0.58, help="TF-IDF cosine duplicate threshold")
    args = parser.parse_args()

    articles = pd.read_csv(args.input_csv) if args.input_csv else None
    result = run_pipeline(
        articles=articles,
        use_llm=args.use_llm,
        max_llm_items=args.max_llm_items,
        top_n=args.top_n,
        dedup_method=args.dedup_method,
        fuzzy_threshold=args.fuzzy_threshold,
        tfidf_threshold=args.tfidf_threshold,
    )
    save_outputs(result, args.output_dir)

    print("Fintech TrendWatcher pipeline complete")
    print(f"Raw articles: {len(result.raw_articles)}")
    print(f"Candidates after filtering: {len(result.candidate_articles)}")
    print(f"Rejected as noise: {len(result.rejected_articles)}")
    print(f"Signals after deduplication: {len(result.signals)}")
    print(f"Dedup method used: {result.dedup_method_used}")
    for warning in result.warnings or []:
        print(f"Warning: {warning}")
    print(f"Digest: {args.output_dir / 'digest.md'}")
    print(f"Signals JSON: {args.output_dir / 'signals.json'}")


if __name__ == "__main__":
    main()
