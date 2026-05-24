# Validation report: Fintech TrendWatcher

_Сформировано: 2026-05-23 14:27 UTC_

## Dataset

- Размер выборки: 60 публикаций.
- Seed: 42.
- Источник выборки: live_rss.
- Fallback: Нет, использовались live RSS публикации.
- RSS публикаций получено до fallback: 147.
- Материалов с `manual_relevance=1`: 40.
- Материалов с `manual_signal=1`: 38.

## RSS sources

- Банк России — новости
- Банк России — события
- Банк России — пресс-релизы
- РБК — новости
- Finextra
- TechCrunch Fintech
- PYMNTS
- Stripe Blog

## Pipeline run

- Dedup method requested: fuzzy.
- Dedup method used: fuzzy.
- Candidates: 33.
- Rejected: 27.
- Signals: 32.

## Metrics

| Metric | Value |
| --- | --- |
| Precision@5 | 1.000 |
| Precision@10 | 1.000 |
| Recall@10 | 0.263 |
| NDCG@10 | 0.678 |
| Category Accuracy | 0.425 |
| Signal Precision | 0.606 |
| Signal Recall | 0.526 |
| Spearman score/import. | 0.220 |

_Примечание: Spearman рассчитан через scipy._

## Короткий вывод для презентации

Pipeline поднимает наверх значимые финтех-сигналы и отсекает часть шума. Ошибки ожидаемо чаще возникают на коротких RSS snippet, широких рыночных новостях и спорных product/news материалах, где не хватает полного текста.

## Удачные срабатывания

| Title | Manual | Pipeline |
| --- | --- | --- |
| Результаты мониторинга максимальных процентных ставок кредитных организаций (05.05.2026) | banking_product / 2 | banking_product / score 82.0 / rank 1 |
| Результаты мониторинга максимальных процентных ставок кредитных организаций (18.05.2026) | banking_product / 2 | banking_product / score 82.0 / rank 1 |
| Mastercard Pushes Brazilian Processors to Split Banco Master Losses | payments / 2 | payments / score 78.6 / rank 2 |
| Giving agents the ability to pay | payments / 2 | payments / score 75.4 / rank 3 |
| Fintech Yotta fined $1 million for Synapse deception | regulation / 3 | banking_product / score 75.2 / rank 4 |

## Ошибки pipeline

| Title | Manual | Pipeline |
| --- | --- | --- |
| AI Spots Hard Hat Violations Before Supervisors Do | noise / signal 0 | fraud_risk / signal 1 /  |
| 10 things we learned building for the first generation of agentic commerce | noise / signal 0 | fraud_risk / signal 1 /  |
| De Morgen узнала о риске Бельгии остаться без флота из-за срыва поставок | noise / signal 0 | fraud_risk / signal 1 /  |
| Качество обслуживания новых ипотечных кредитов улучшается | regulation / signal 1 | banking_product / signal 0 / too little content to verify |
| Залог успешного IPO: рекомендации регуляторов | regulation / signal 1 | regulation / signal 0 / too little content to verify |

## Ограничения эксперимента

- Разметка имитирует работу аналитика через прозрачную deterministic rubric, а не заменяет настоящую независимую ручную разметку.
- RSS часто содержит только title/snippet, поэтому часть оценок сделана без полного текста статьи.
- Live RSS меняется со временем; seed фиксирует sampling, но не фиксирует содержимое внешних лент.
- Метрики считаются для MVP-ranking baseline, а не для production ML-модели.

## Slide summary

Ручная проверка качества:
- Размечено 60 RSS-публикаций.
- Оценивали релевантность, полезность как сигнала, категорию и важность.
- Сравнили ручную разметку с top-K выдачей pipeline.

Метрики:
- Precision@5 = 1.000
- Precision@10 = 1.000
- Recall@10 = 0.263
- NDCG@10 = 0.678
- Category Accuracy = 0.425

Вывод:
Pipeline поднимает наверх значимые финтех-сигналы и отсекает часть шума, но ошибки чаще возникают на коротких RSS snippet и спорных product/news материалах.

## Command

```bash
python3 scripts/run_validation_experiment.py
```
