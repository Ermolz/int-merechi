# Практичне заняття 7

Wikidata SPARQL та аналіз географічного графа у NetworkX. Варіант 12, домен 5, числовий фільтр А: P1082 > 1000. Спільне ядро — Німеччина Q183.

Умова вимагає Jupyter Notebook із відтворюваним кодом та висновками до кожного завдання. У каталозі також є окремий Python-скрипт з тими самими обчислювальними функціями.

## Результат

2389 вузлів, 4402 ребра, три типи вузлів і три типізовані відношення. Є одна слабка компонента зв'язності; ізольованих вузлів немає. Усі 18 кодових комірок ноутбука виконано без помилок. Метрики скрипта й ноутбука збігаються.

| Файл | Призначення |
|---|---|
| `Практичне_заняття_7_Єрмолович_варіант_12.ipynb` | Самодостатній виконаний ноутбук, графіки та висновки |
| `geography_analysis.py` | Python-скрипт з CLI |
| `query.rq` | SPARQL-запит відбору |
| `data/` | Відповіді сервісу, підписи та походження даних |
| `outputs/` | GraphML, JSON, CSV, PNG та метрики |
| `tests/` | Перевірки фільтра, дедуплікації, відстаней, ентропії та серіалізації |

## Запуск

Перевірено з Python 3.12.14. Команди виконуються з каталогу `practice7`.

```sh
python -m pip install -r requirements.txt
python geography_analysis.py
```

Скрипт за замовчуванням використовує збережені дані й записує результати до `outputs/`. Інший каталог результатів:

```sh
python geography_analysis.py --output results
```

Нове завантаження:

```sh
python geography_analysis.py --refresh --endpoint wdqs
python geography_analysis.py --refresh --endpoint qlever
```

Збережений знімок отримано 26.10.2026 через [QLever Wikidata](https://www.wikidata.org/wiki/Wikidata:SPARQL_query_service/Alternative_endpoints), оскільки основний WDQS відповідав HTTP 429. Той самий SPARQL 1.1 запит підходить для обох endpoint. Новий мережевий запит може дати інші результати через редагування Wikidata; автоматичної прихованої заміни джерела немає.

Ноутбук відкривається у Jupyter або Google Colab й містить власний стиснений знімок. Для нового завантаження встановіть `REFRESH_FROM_WIKIDATA=True`; прапорець `USE_ALTERNATIVE_ENDPOINT=True` обирає QLever.

## Перевірки

```sh
python -m pip install -r requirements-dev.txt
python -m pytest
python -m ruff check geography_analysis.py tests
python -m ruff format --check geography_analysis.py tests
```

Пройдено 10 тестів. Середні шляхи на неорієнтованому графі враховують усі пари різних вузлів; на орієнтованому — лише досяжні пари, з окремим обліком їхньої частки. Посередництво обчислюється точно. Семантична різноманітність визначена через ентропію Шеннона та індекс Сімпсона.

Схема містить три типізовані відношення та два різні предикати: P17 використовується для City → Country й AdministrativeTerritory → Country. Підписи та населення є атрибутами вузлів.

Дані Wikidata доступні за [CC0](https://www.wikidata.org/wiki/Wikidata:Licensing).
