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

Тренировочные запросы: 5 пользователей, `/offers` — по одному на пользователя, `/approval` и `/alternative` — по 10:
`bash examples.sh`
(когда оба контейнера запущены).
