# Fintech TrendWatcher MVP

Хакатонный MVP внутреннего инструмента для банка. Прототип берет открытые финтех-публикации, очищает входные данные, отбрасывает шум, объединяет дубли и перепечатки, оценивает важность сигналов и собирает короткий проверяемый дайджест для продуктовой, стратегической или competitive intelligence команды.

Проект сделан как explainable demo, а не production-ready мониторинг. Главная ценность: можно показать весь путь от RSS/CSV до финального дайджеста и объяснить, почему конкретная публикация прошла фильтр, получила такой score и попала в итоговый список.

## Быстрый Запуск

```bash
cd ~/Desktop/fintech-trendwatcher
python3 scripts/run_pipeline.py
streamlit run app.py
```

Опционально, если зависимости не установлены:

```bash
python3 -m pip install -r requirements.txt
```

## Что Собрано

- Русский Streamlit-интерфейс для демо перед жюри.
- Детерминированный pipeline без обязательного API и интернета.
- Demo dataset с полезными сигналами, шумом, дублями и перепечатками.
- Live RSS mode с российскими и международными источниками.
- Два режима дедупликации: `Fuzzy` и lightweight `TF-IDF`.
- Гибридная оценка важности: relevance, source quality, novelty, impact, evidence count.
- Карточки сигналов: что произошло, почему это важно для банка, рекомендованное действие, источники, важность.
- Техническая explainability в раскрывающихся блоках: компоненты score, причина фильтрации, метод dedup.
- Опциональное LLM-обогащение через OpenRouter после дешевой фильтрации и дедупликации.

## Архитектура Pipeline

```text
RSS / CSV / demo dataset
        ↓
Очистка и нормализация текста
        ↓
Rule-based фильтрация шума
        ↓
Deduplication: Fuzzy или TF-IDF
        ↓
Группировка публикаций в сигналы
        ↓
Hybrid scoring
        ↓
Карточки сигналов
        ↓
Финальный дайджест
```

Pipeline живет в `trendwatcher/pipeline.py`, RSS ingestion — в `trendwatcher/rss.py`, интерфейс — в `app.py`, CLI-запуск — в `scripts/run_pipeline.py`.

## Шаг 1. Ingestion

Поддерживаются три входа:

- `Демо-набор`: встроенные публикации из `trendwatcher/demo_data.py`; лучший режим для стабильной защиты без сети.
- `CSV-файл`: пользовательский файл с колонками `title`, `url`, `source`, `published_at`, `snippet`, `text`.
- `Live RSS`: реальные RSS-источники.

RSS-источники:

- Банк России — новости: `https://www.cbr.ru/rss/RssNews`
- Банк России — события: `https://www.cbr.ru/rss/eventrss`
- Банк России — пресс-релизы: `https://www.cbr.ru/rss/RssPress`
- РБК — новости: `https://rssexport.rbc.ru/rbcnews/news/30/full.rss`
- Finextra
- TechCrunch Fintech
- The Paypers
- PYMNTS
- Stripe Blog

Метод: стандартный XML/RSS parser на Python. Если отдельный RSS не загрузился или вернул некорректный XML, приложение показывает warning и продолжает обработку остальных источников. Если RSS полностью пустой, UI может вернуться к demo dataset для стабильного показа.

## Шаг 2. Очистка И Нормализация

На входе все публикации приводятся к единой схеме:

```text
id, title, url, source, published_at, snippet, text
```

Что делаем:

- `html.unescape` для HTML entities: `&nbsp;`, `&laquo;`, `&raquo;` и похожих.
- Удаление HTML-тегов из `title`, `snippet`, `text`.
- Нормализация пробелов и неразрывных пробелов.
- Очистка URL от tracking-параметров: `utm_*`, `fbclid`, `gclid`.
- Выделение `domain`.
- Нормализация заголовка для дальнейшего matching.
- Подготовка `dedup_text = title + snippet`.

Зачем: RSS часто приносит HTML entities, теги и tracking-ссылки. Без очистки UI выглядит грязно, а дедупликация и фильтрация работают хуже.

## Шаг 3. Rule-Based Фильтрация Шума

Фильтр работает до LLM и до scoring, чтобы не тратить бюджет на очевидный шум.

Используются словари:

- `FINTECH_KEYWORDS`: русские и английские финтех-триггеры: банк, платежи, СБП, цифровой рубль, KYC, AML, биометрия, open banking, fraud, payments и т.д.
- `NOISE_KEYWORDS`: вакансии, курсы, вебинары, SEO, крипто-прогнозы, биржевые обзоры, промо и другие нерелевантные темы.
- `CATEGORY_KEYWORDS`: признаки категорий `payments`, `banking_product`, `UX`, `partnership`, `regulation`, `fraud_risk`, `market_signal`.

Основные правила:

- Если есть шумовые триггеры и мало финтех-триггеров, публикация уходит в rejected.
- Если категория `other` и мало финтех-сигналов, публикация уходит в rejected.
- Если текста слишком мало, публикация уходит в rejected как плохо проверяемая.
- Если источник слабый и нет достаточных финтех-триггеров, публикация уходит в rejected.

Отдельное правило для Банка России:

- Публикации про памятные монеты, нумизматику, коллекционные выпуски, ордена и драгоценные металлы не считаются финтех/банковским продуктовым сигналом.
- Исключение: если в тексте есть сильные финтех-триггеры вроде `цифровой рубль`, `СБП`, `платежи`, `переводы`, `кредит`, `вклад`, `регулирование`, `антифрод`, `KYC`, `AML`, `биометрия`, `персональные данные`.
- Причина rejected: `публикация Банка России, но не финтех/банковский продуктовый сигнал`.

Зачем: у регулятора много официальных новостей, но не каждая новость Банка России полезна продуктовой или стратегической команде банка.

## Шаг 4. Категоризация

Категория определяется обычным кодом: считаем совпадения текста с `CATEGORY_KEYWORDS` и выбираем категорию с максимальным числом hit-ов.

Категории:

- `payments`: платежи, переводы, СБП, карты, checkout, acquiring.
- `banking_product`: кредит, вклад, счет, BNPL, ипотека, депозит.
- `UX`: мобильное приложение, onboarding, биометрия, кошелек, лояльность.
- `partnership`: партнерство, интеграция, экосистема, marketplace.
- `regulation`: ЦБ, Банк России, регулятор, закон, надзор, персональные данные.
- `fraud_risk`: антифрод, мошенничество, KYC, AML, идентификация, безопасность.
- `market_signal`: рынок, тренд, запуск, пилот, стратегия, исследование.

Зачем: категория нужна для dedup safety, scoring и выбора рекомендованного действия.

## Шаг 5. Deduplication

В UI и CLI доступны два метода.

### Fuzzy

Дефолтный стабильный режим.

Методы:

- Canonical URL matching: одинаковые URL после удаления `utm_*` считаются дублями.
- `difflib.SequenceMatcher` по нормализованному `title + snippet`.
- Token overlap по словам.
- Склейка разрешена при совпадении категории и similarity выше порога.

Default threshold: `0.72`.

Зачем: работает без дополнительных ML-зависимостей и стабилен для live demo.

### TF-IDF

Lightweight NLP/ML режим без transformer-моделей.

Методы:

- `sklearn.feature_extraction.text.TfidfVectorizer`.
- Текст для векторизации: `title + snippet`.
- `ngram_range=(1, 2)`.
- `cosine_similarity`.
- Склейка при `similarity >= tfidf_threshold` и совпадении категории.

Default threshold: `0.58`.

Pipeline принимает оба имени метода: `tfidf` и `tf-idf`. Если `sklearn` недоступен или TF-IDF падает, pipeline автоматически возвращается к `fuzzy` и добавляет warning.

CLI:

```bash
python3 scripts/run_pipeline.py --dedup-method fuzzy
python3 scripts/run_pipeline.py --dedup-method tfidf
python3 scripts/run_pipeline.py --dedup-method tf-idf
```

Зачем: TF-IDF лучше ловит близкие перепечатки с измененным заголовком, но не требует тяжелых моделей, vector DB, LangChain или fine-tuning.

## Шаг 6. Группировка В Сигналы

После dedup каждая группа публикаций становится одним сигналом.

В сигнал попадает:

- `headline`: лучший заголовок группы.
- `category` и `tags`.
- `published_at`, `date_label`, `freshness_label`.
- `sources`: ссылки, даты и качество источников.
- `summary`: описание события.
- `why_now`: почему это важно сейчас.
- `suggested_action`: осторожное действие для аналитика.
- `score_components`.
- `score_explanation`.

Если RSS дал только title/snippet, в технических деталях карточки показывается: `Полный текст не загружался, анализ основан на RSS snippet.`

## Шаг 7. Scoring

Score считается обычным кодом по формуле:

```text
score = 0.30 * relevance
      + 0.20 * source_quality
      + 0.20 * novelty
      + 0.15 * impact
      + 0.15 * evidence_count
```

Компоненты:

- `relevance`: сколько финтех/product-триггеров найдено в тексте.
- `source_quality`: надежность источника. Регуляторы и первоисточники выше, перепечатки ниже.
- `novelty`: есть ли признаки свежего запуска, пилота, консультации, тестирования или guidance.
- `impact`: базовая значимость категории для банка, например regulation/fraud/payments выше.
- `evidence_count`: сколько уникальных источников подтверждает сигнал.
- `confidence`: вспомогательная оценка уверенности на базе источников и подтверждений.

`hotness` переводит score в шкалу `1–5`.

Зачем: score не должен быть “магическим”. В UI видно, какие компоненты подняли или снизили итоговую важность.

## Шаг 8. Recommended Action

Рекомендация зависит от категории, score и уверенности.

Если сигнал слабый или сомнительный, действие осторожное:

```text
Оставить в мониторинге и не выносить в продуктовые действия без дополнительных подтверждений.
```

Для более сильных сигналов:

- `regulation`: проверить влияние на документы, процессы, клиентские сценарии или compliance-требования.
- `payments`: сравнить механику с текущими платежными сценариями и применимостью для банковского продукта.
- `fraud_risk`: передать risk/anti-fraud команде для оценки KYC/AML, мониторинга операций или авторизации.
- `UX`: оценить применимость в мобильном банке или onboarding.
- `partnership`: проверить партнерскую модель и возможный аналог для банковской экосистемы.
- `market_signal`: оставить в radar и дождаться подтверждения от первоисточников.

Зачем: рекомендация помогает аналитику, но не выдает сильные product/compliance next steps для слабых или нерелевантных публикаций.

## Шаг 9. Digest Generation

Финальный дайджест собирается из top-сигналов.

Формат:

- дата и свежесть сигнала;
- важность `hotness/score`;
- категория и теги;
- почему score такой;
- почему это важно сейчас;
- краткое summary;
- рекомендованное действие;
- проверяемые источники.

Результаты сохраняются в:

- `data/articles.csv`: все нормализованные публикации.
- `data/candidates.csv`: публикации, прошедшие фильтр.
- `data/rejected.csv`: отфильтрованный шум с причинами.
- `data/signals.json`: итоговые карточки сигналов.
- `data/digest.md`: финальный дайджест.

## Streamlit UI

Интерфейс в `app.py` показывает:

- метрики: исходные публикации, кандидаты, отфильтрованный шум, сигналы, средний score, объединенные дубли;
- визуальный pipeline flow;
- top candidates с краткими колонками;
- technical details в expander;
- карточки сигналов для бизнес-пользователя;
- expander `Как рассчитана оценка`;
- финальный дайджест;
- rejected noise с причинами;
- LLM-промпты.

В live RSS режиме UI дополнительно поясняет: количество дублей зависит от пересечения источников; для демонстрации dedup лучше подходит demo dataset.

## LLM Enrichment

LLM не обязательна. По умолчанию MVP работает deterministic.

Если включить OpenRouter, LLM вызывается только после фильтрации и dedup для top-сигналов. Она может улучшить:

- summary;
- why now;
- tags;
- category;
- wording.

При этом pipeline, фильтр, dedup, scoring и fallback остаются обычным кодом.

Пример:

```bash
export OPENROUTER_API_KEY="your_key"
export OPENROUTER_MODEL="openai/gpt-5-nano"
python3 scripts/run_pipeline.py --use-llm --max-llm-items 8
```

## CLI

Базовый запуск:

```bash
python3 scripts/run_pipeline.py
```

С CSV:

```bash
python3 scripts/run_pipeline.py --input-csv data/articles.csv
```

С TF-IDF dedup:

```bash
python3 scripts/run_pipeline.py --dedup-method tfidf --tfidf-threshold 0.58
```

С Fuzzy dedup:

```bash
python3 scripts/run_pipeline.py --dedup-method fuzzy --fuzzy-threshold 0.72
```

## Структура Проекта

```text
app.py                         Русский Streamlit UI
scripts/run_pipeline.py         CLI запуск pipeline
trendwatcher/pipeline.py        Очистка, фильтр, dedup, scoring, digest
trendwatcher/rss.py             RSS ingestion и RSS status warnings
trendwatcher/demo_data.py       Демо-набор с сигналами, дублями и шумом
trendwatcher/llm.py             Опциональный OpenRouter клиент и кеш
prompts/*.txt                   Промпты для LLM-режима
data/                           Экспортируемые артефакты
```

## Что Показывать На Защите

1. Демо-набор: видно шум, дубли и полезные сигналы.
2. Live RSS: есть российские и международные источники.
3. Отфильтрованный шум: причины rejected, включая нерелевантные публикации Банка России.
4. Dedup groups: сколько кандидатов объединено в сигналы.
5. Карточку сигнала: что произошло, почему важно для банка, что сделать, какие источники.
6. `Как рассчитана оценка`: прозрачные компоненты score.
7. Финальный digest как готовый черновик для внутренней команды.

## Ограничения MVP

- Это не production crawler и не real-time мониторинг.
- RSS mode часто получает только title/snippet, а не полный текст статьи.
- TF-IDF помогает в lightweight semantic deduplication, но не заменяет embeddings.
- Rule-based фильтр не идеален, зато быстрый, объяснимый и стабильный для хакатона.
- LLM enrichment опционален и не нужен для базового демо.
