# Модель 1: `/offers`

`POST /offers` — по данным компании 10 кредитных продуктов с условиями, отсортированные по
`oftenhood` (какая доля похожих компаний приходила за этим продуктом).

## Запуск

```bash
sudo docker build -t model1 .
sudo docker run --rm -p 8000:8000 model1
```

## Запрос

Из этой папки, в другом терминале:

```bash
curl -X POST localhost:8000/offers -H "Content-Type: application/json" -d @example.json
```
```json
{
  "offers": [
    {
      "offer": {"product_type": "WORKING_CAPITAL", "amount": 21000000, "term_months": 36, "rate": 19.2, "collateral_value": 7500000},
      "oftenhood": 0.5361
    },
    ...ещё 9 продуктов
  ]
}
```

- Ошибка в запросе → `422 {"error": {"code": "VALIDATION_ERROR", "message": "..."}}`.

Формат полей — [../API.md](../API.md), раздел 4.1. В браузере — `http://localhost:8000/docs`.

## Для разработчика ML

| Файл | Что внутри |
|---|---|
| `app.py` | ручки `/offers`, `/health` |
| `model.py` | признаки и прогноз |
| `contract.py` | проверка запроса |
| `artifacts/` | обученные модели |
