# Модель 1: `POST /offers`

По данным компании возвращает 10 кредитных продуктов. Для каждого:
- `oftenhood` — какая доля похожих компаний приходила за этим продуктом;
- `offer` — с какой суммой, сроком, ставкой и залогом похожие компании его оформляют.

Продукты отсортированы по убыванию `oftenhood`. Полный контракт — [../API.md](../API.md), раздел 4.1.

## Файлы

| Файл | За что отвечает |
|---|---|
| `app.py` | сервис: принимает запрос, проверяет, отдаёт ответ |
| `model.py` | признаки компании и прогноз моделей |
| `contract.py` | проверка запроса и допустимые значения продуктов |
| `artifacts/` | обученные модели — сервис работает только на них |
| `example.json` | пример запроса |
| `Dockerfile`, `requirements.txt` | контейнер и его зависимости |
| `train.py` | переобучение моделей (в контейнер не входит) |

## Запуск

Из этой папки:

```bash
sudo docker build -t model1 .
sudo docker run --rm -p 8000:8000 model1
```

Готово, когда в логе появится `Application startup complete`.

## Запрос

В другом терминале, из этой папки:

```bash
curl -X POST localhost:8000/offers -H "Content-Type: application/json" -d @example.json
```

Ответ:

```json
{
  "offers": [
    {
      "offer": {"product_type": "WORKING_CAPITAL", "amount": 21000000, "term_months": 36,
                "rate": 19.2, "collateral_value": 7500000},
      "oftenhood": 0.5361
    },
    ...ещё 9 продуктов
  ]
}
```

Другую компанию — поменять поля в `example.json`. Все 20 полей обязательны, «нет данных» — `null`.

Ошибка в запросе → `422`:

```json
{"error": {"code": "VALIDATION_ERROR", "message": "company.legal_form: нет поля"}}
```

Ещё:
- `GET /health` → `{"status": "ok"}` — сервис жив;
- `http://localhost:8000/docs` — то же в браузере: `POST /offers` → Try it out → Execute.

## Переобучить

Нужны данные `../data/applications.csv` (`python ../generate_data.py`) и окружение `../requirements.txt`.

```bash
python train.py      # ≈ 4 минуты, перезаписывает artifacts/
```

Потом пересобрать контейнер и закоммитить новые `artifacts/`.
