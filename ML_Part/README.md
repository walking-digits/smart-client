# ML-часть

## Запустить ML-сервисы

Два контейнера, у каждого своя папка. Из этой папки, каждую строку — в своём терминале:

```bash
sudo docker build -t model1 model1 && sudo docker run --rm -p 8000:8000 model1
sudo docker build -t model2 model2 && sudo docker run --rm -p 8001:8000 model2
```

| Адрес | Ручки | Подробнее |
|---|---|---|
| `localhost:8000` | `POST /offers` | [model1/README.md](model1/README.md) |
| `localhost:8001` | `POST /approval`, `POST /alternative` | [model2/README.md](model2/README.md) |

Форматы запросов и ответов — [API.md](API.md).

Тренировочные запросы (5 пользователей, готовые команды `curl`) — [examples.md](examples.md).

## Данные, обучение, тесты

| Что | Как |
|---|---|
| Синтетические данные | `python generate_data.py` — 1 млн заявок за 2 года и ежемесячные срезы компаний в `data/` ([GENERATOR.md](GENERATOR.md)) |
| Переобучить модели | `python model1/train.py`, `python model2/train.py` |
| Тесты | запустить оба сервиса, затем `python mock/stress_test.py` — 69 тестов, отчёт [TEST_REPORT.md](TEST_REPORT.md) |

Окружение для этого — `pip install -r requirements.txt` (сервисам в Docker оно не нужно).

