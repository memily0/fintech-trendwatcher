# Fintech TrendWatcher MVP

Демонстрационный прототип для хакатон-кейса: сервис берет поток открытых финтех-публикаций, убирает шум и дубли, оценивает важность сигналов и собирает короткий дайджест для внутренней команды банка.

## Что Уже Есть

- Streamlit-дашборд с прозрачным pipeline: raw articles -> filtering -> deduplication -> scoring -> signal cards -> digest.
- Встроенный demo dataset с релевантными сигналами, дублями, перепечатками и шумом.
- Дешевый deterministic режим без API: все работает сразу.
- Опциональное LLM-обогащение через OpenRouter, если задан `OPENROUTER_API_KEY`.
- Экспорт артефактов: `data/articles.csv`, `data/signals.json`, `data/digest.md`.

## Быстрый Старт

```bash
cd ~/Desktop/fintech-trendwatcher
python3 scripts/run_pipeline.py
streamlit run app.py
```

Если зависимостей не хватает:

```bash
python3 -m pip install -r requirements.txt
```

## OpenRouter

LLM не обязательна для демо. Если нужен режим с моделью:

```bash
export OPENROUTER_API_KEY="your_key"
export OPENROUTER_MODEL="openai/gpt-5-nano"
python3 scripts/run_pipeline.py --use-llm --max-llm-items 8
```

В UI можно включить LLM enrichment в сайдбаре. По умолчанию прототип работает без API, чтобы не тратить бюджет и не зависеть от сети.

## Структура

```text
app.py                         Streamlit UI
scripts/run_pipeline.py         CLI запуск pipeline
trendwatcher/pipeline.py        нормализация, фильтр, dedup, scoring, digest
trendwatcher/demo_data.py       встроенный тестовый набор
trendwatcher/llm.py             OpenRouter клиент + кеш
trendwatcher/rss.py             простой RSS ingest на стандартной библиотеке
prompts/*.txt                   промпты для презентации и LLM-режима
data/                           генерируемые артефакты
```

## Что Показывать Жюри

1. Сырой поток: есть новости, дубли, перепечатки и шум.
2. Rule-based фильтр: почему публикация прошла или была отброшена.
3. Dedup groups: один сигнал может иметь несколько источников.
4. Scoring: видны компоненты `relevance`, `source_quality`, `novelty`, `impact`, `evidence_count`.
5. Итоговые карточки: headline, hotness, tags, why now, sources, summary, suggested action.
6. Дайджест: готовый черновик для продуктовой/стратегической команды банка.

## Ограничения MVP

- Это не production crawler и не real-time мониторинг.
- Демо использует короткие snippets, а не полные тексты всех статей.
- Дедупликация эвристическая, без embeddings.
- LLM вызывается только после дешевой фильтрации и только для top candidates.
