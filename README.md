# Fintech TrendWatcher MVP

Hackathon MVP для внутренней команды банка: прототип берет открытые финтех-публикации, отбрасывает шум, объединяет дубли и перепечатки, оценивает важность сигналов и формирует короткий проверяемый дайджест.

Главный фокус проекта — explainable pipeline, а не production-ready мониторинг. Все ключевые решения видны в интерфейсе: что пришло на вход, что отфильтровано, какие статьи склеены в один сигнал, почему score высокий или средний, на какие источники можно опереться.

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

## Архитектура Pipeline

```text
RSS / CSV / demo dataset
        ↓
Очистка URL, дат, источников, title + snippet
        ↓
Rule-based фильтрация шума
        ↓
Deduplication: Fuzzy или TF-IDF
        ↓
Hybrid scoring: relevance, source quality, novelty, impact, evidence
        ↓
Карточки сигналов и финальный digest
```

Формула score:

```text
score = 0.30*релевантность
      + 0.20*качество_источника
      + 0.20*новизна
      + 0.15*impact
      + 0.15*количество_подтверждений
```

Почему так: релевантность важнее всего для борьбы с шумом; качество источника и новизна защищают от слабых перепечаток; impact и evidence count помогают поднять сигналы, которые подтверждены несколькими источниками и важны для банка.

## Источники

Live RSS mode использует российские и международные источники.

Российские источники:
- Банк России — новости: `https://www.cbr.ru/rss/RssNews`
- Банк России — события: `https://www.cbr.ru/rss/eventrss`
- Банк России — пресс-релизы: `https://www.cbr.ru/rss/RssPress`
- РБК — новости: `https://rssexport.rbc.ru/rbcnews/news/30/full.rss`

Международные источники:
- Finextra
- TechCrunch Fintech
- The Paypers
- PYMNTS
- Stripe Blog

Если один RSS не загрузился, приложение показывает warning и продолжает обработку остальных. Если live RSS полностью недоступен, включается demo fallback.

## Deterministic Mode vs LLM Enrichment

По умолчанию MVP работает в deterministic mode:
- не нужен интернет;
- не нужен API key;
- результаты воспроизводимы;
- все правила фильтрации и scoring можно объяснить жюри.

Опциональный LLM enrichment через OpenRouter включается только после дешевой фильтрации и дедупликации. LLM не решает весь pipeline, а только улучшает текстовые поля top-сигналов: summary, why now, tags, suggested action.

```bash
export OPENROUTER_API_KEY="your_key"
export OPENROUTER_MODEL="openai/gpt-5-nano"
python3 scripts/run_pipeline.py --use-llm --max-llm-items 8
```

## Deduplication

Доступны два режима.

`Fuzzy` — дефолтный fallback режим. Он сравнивает нормализованные `title + snippet` через стандартный `difflib.SequenceMatcher` и token overlap. Хорош для стабильного live demo без дополнительных зависимостей.

`TF-IDF` — lightweight NLP/ML режим. Он строит TF-IDF представления для `title + snippet`, считает cosine similarity и объединяет статьи, если similarity выше порога и категория совпадает. Это не transformer, не vector DB и не fine-tuning: модель не скачивает веса и не требует обучения.

CLI:

```bash
python3 scripts/run_pipeline.py --dedup-method fuzzy
python3 scripts/run_pipeline.py --dedup-method tfidf --tfidf-threshold 0.58
```

В Streamlit метод выбирается в сайдбаре.

## Explainability

В интерфейсе видно:
- top candidates после фильтрации;
- отфильтрованный шум и причины отбраковки;
- группы дублей и метод дедупликации;
- score components: relevance, source quality, novelty, impact, evidence count;
- короткое объяснение, почему сигнал получил такой score;
- дата публикации, свежесть сигнала и проверяемые ссылки.

## Структура Проекта

```text
app.py                         Русский Streamlit UI
scripts/run_pipeline.py         CLI запуск pipeline
trendwatcher/pipeline.py        Фильтр, dedup, scoring, digest
trendwatcher/demo_data.py       Демо-набор с сигналами, дублями и шумом
trendwatcher/llm.py             Опциональный OpenRouter клиент + кеш
trendwatcher/rss.py             Российские и международные RSS
prompts/*.txt                   Промпты для LLM-режима
data/                           Экспортируемые артефакты
```

## Что Показывать На Демо

1. Исходные публикации: есть полезные новости, дубли, перепечатки и шум.
2. Фильтрация: видно, почему публикация прошла или была отброшена.
3. Dedup groups: один сигнал объединяет несколько источников.
4. Score explanation: понятно, какие факторы подняли или снизили важность.
5. Карточки сигналов: headline, дата, hotness, why now, источники, действие.
6. Финальный дайджест: готовый черновик для продуктовой/стратегической команды банка.

## Ограничения MVP

- Это не production crawler и не real-time мониторинг.
- Demo dataset использует snippets, а не полный парсинг всех HTML-страниц.
- TF-IDF помогает на легкой semantic deduplication, но не заменяет полноценные embeddings.
- LLM вызывается только для top-сигналов и только если явно включен.
