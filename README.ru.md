# Netflix Catalog

Небольшой full-stack проект: берёт CSV с каталогом Netflix, загружает его в Postgres и предоставляет FastAPI-бэкенд со встроенным веб-интерфейсом для поиска с фильтрами.

English version: [README.md](README.md).

## Стек

- **pandas** — чтение и очистка CSV
- **SQLAlchemy** — ORM и создание таблиц
- **FastAPI** — HTTP API
- **Postgres 16** — хранилище
- **Docker / Compose** — локальная инфраструктура
- Чистый HTML/CSS/JS для интерфейса (без сборки)

## Структура

```
netflix_project/
├── app/
│   ├── main.py        приложение FastAPI, модели, авторизация, роуты
│   ├── etl.py         загрузчик CSV → Postgres на pandas
│   ├── config.py      настройки из переменных окружения
│   └── static/        веб-интерфейс (index.html, style.css, app.js)
├── data/
│   └── netflix.csv    положите CSV сюда
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Запуск

1. Убедитесь, что файл `data/netflix.csv` лежит на месте.
2. Соберите и поднимите стек:
   ```bash
   docker compose up --build
   ```
3. При первом старте API загрузит CSV в базу (идемпотентно — повторные перезапуски не перезагружают данные).
4. Откройте интерфейс по адресу http://localhost:8090 — зарегистрируйтесь, войдите и пользуйтесь фильтрами.
5. Swagger/OpenAPI доступен по http://localhost:8090/docs.

## API

### Авторизация

```bash
# Регистрация
curl -X POST http://localhost:8090/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}'

# Вход (OAuth2 password flow — form-encoded)
TOKEN=$(curl -s -X POST http://localhost:8090/auth/login \
  -d "username=alice&password=secret123" | jq -r .access_token)
```

### Поиск

```bash
# Комедии с рейтингом TV-MA, выпущенные с 2018 года
curl "http://localhost:8090/shows?genre=Comedies&rating=TV-MA&year_from=2018&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Поиск подстроки по названию / актёрам / описанию / режиссёру
curl "http://localhost:8090/shows?q=stranger" -H "Authorization: Bearer $TOKEN"

# Уникальные значения для выпадающих списков фильтров
curl http://localhost:8090/categories -H "Authorization: Bearer $TOKEN"
```

### Фильтры

| Параметр       | Описание                                     |
| -------------- | -------------------------------------------- |
| `q`            | Поиск подстроки по title / cast / desc / director |
| `type`         | `Movie` или `TV Show`                        |
| `rating`       | `TV-MA`, `PG-13`, …                          |
| `country`      | Поиск подстроки                              |
| `genre`        | Поиск подстроки по `listed_in`               |
| `release_year` | Точный год                                   |
| `year_from`    | Нижняя граница (включительно)                |
| `year_to`      | Верхняя граница (включительно)               |
| `limit`        | Размер страницы (по умолчанию 50, максимум 500) |
| `offset`       | Смещение                                     |

Формат ответа: `{ "total": <число>, "items": [...] }`.

## Особенности реализации

- `show_id` объявлен как `VARCHAR PRIMARY KEY` — внешние идентификаторы хранятся строками.
- Имена колонок таблицы `shows` повторяют CSV один к одному: `show_id, type, title, director, cast, country, date_added, release_year, rating, duration, listed_in, description`.
- ETL разбивает строки на корзины `(основной жанр, рейтинг)` перед вставкой — см. `_split_by_category_and_rating` в `app/etl.py`.
- Авторизация работает на JWT (HS256). Время жизни токена задаётся через `JWT_TTL_MIN`.
- Веб-интерфейс — это статическая страница, которая монтируется на `/static` и отдаётся по корневому маршруту `/`.

## Сброс базы

```bash
docker compose down -v   # -v удаляет том postgres; ETL запустится заново
```

## Конфигурация

Переменные окружения, которые читает приложение (см. `app/config.py`):

| Переменная      | Значение по умолчанию                                            |
| --------------- | ---------------------------------------------------------------- |
| `DATABASE_URL`  | `postgresql+psycopg2://netflix:netflix@db:5432/netflix`          |
| `CSV_PATH`      | `/data/netflix.csv`                                              |
| `JWT_SECRET`    | `change-me-in-production` — обязательно переопределяйте в проде  |
| `JWT_TTL_MIN`   | `60`                                                             |
