# Модель 2: `/approval` и `/alternative`

- `POST /approval` — шанс, что заявку одобрят.
- `POST /alternative` — похожее предложение того же продукта, у которого шанс больше `gamma`.

## Запуск

```bash
sudo docker build -t model2 .
sudo docker run --rm -p 8001:8000 model2
```

8 процессов: 10 000 запросов `/approval` ≈ 2 с, `/alternative` ≈ 5–6 с. На слабой машине: `-e WEB_CONCURRENCY=4`.

## Запросы

Из этой папки, в другом терминале:

```bash
curl -X POST localhost:8001/approval -H "Content-Type: application/json" -d @example_approval.json
```
```json
{"approval_probability": 0.6054}
```

```bash
curl -X POST localhost:8001/alternative -H "Content-Type: application/json" -d @example_alternative.json
```
```json
{
  "source_approval_probability": 0.6054,
  "offer": {"product_type": "WORKING_CAPITAL", "amount": 31000000, "term_months": 12, "rate": 20.0,
            "collateral_value": 0, "collateral_type": null, "collateral_subtype": null},
  "likelyhood": 0.775,
  "approval_probability": 0.7042
}
```

- Залог: `collateral_type` и `collateral_subtype` — вид залога (справочник в [../API.md](../API.md),
  раздел 6); без залога — `null`.
- Формальный признак отказа ([REJECT_RULES.md](REJECT_RULES.md)) → шанс `0`.
- Исходное уже проходит порог → вернётся оно, `likelyhood` = 1.
- Подходящего нет → `"offer": null` (это не ошибка).
- Ошибка в запросе → `422 {"error": {"code": "VALIDATION_ERROR", "message": "..."}}`.

Формат полей — [../API.md](../API.md), разделы 4.2–4.3. В браузере — `http://localhost:8001/docs`.

## Для разработчика ML

| Файл | Что внутри |
|---|---|
| `app.py` | ручки `/approval`, `/alternative`, `/health` |
| `model.py` | признаки, прогноз, поиск альтернативы; веса похожести `W_AMOUNT`, `W_TERM`, `W_COLL` |
| `contract.py` | проверка запроса |
| `REJECT_RULES.md` | формальные признаки отказа (шанс 0) |
| `artifacts/approval.txt` | обученная модель |
