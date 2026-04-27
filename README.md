# Netflix Catalog

A small full-stack project: takes the Netflix titles CSV, loads it into Postgres, and serves it through a FastAPI backend with a built-in web UI for filtered search.

Russian version: [README.ru.md](README.ru.md).

## Stack

- **pandas** — CSV reading & cleaning
- **SQLAlchemy** — ORM and table creation
- **FastAPI** — HTTP API
- **Postgres 16** — storage
- **Docker / Compose** — local infrastructure
- Vanilla HTML/CSS/JS for the UI (no build step)

## Layout

```
netflix_project/
├── app/
│   ├── main.py        FastAPI app, models, auth, routes
│   ├── etl.py         pandas CSV → Postgres loader
│   ├── config.py      env-driven settings
│   └── static/        web UI (index.html, style.css, app.js)
├── data/
│   └── netflix.csv    place the CSV here
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Run

1. Make sure `data/netflix.csv` exists.
2. Build and start the stack:
   ```bash
   docker compose up --build
   ```
3. The API loads the CSV on first start (idempotent — restarts don't reload).
4. Open the UI at http://localhost:8090 — register an account, sign in, and start filtering.
5. Swagger / OpenAPI lives at http://localhost:8090/docs.

## API

### Auth

```bash
# Register
curl -X POST http://localhost:8090/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}'

# Login (OAuth2 password flow — form-encoded)
TOKEN=$(curl -s -X POST http://localhost:8090/auth/login \
  -d "username=alice&password=secret123" | jq -r .access_token)
```

### Search

```bash
# Comedies rated TV-MA, released 2018+
curl "http://localhost:8090/shows?genre=Comedies&rating=TV-MA&year_from=2018&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Substring search across title / cast / description / director
curl "http://localhost:8090/shows?q=stranger" -H "Authorization: Bearer $TOKEN"

# Distinct values for filter dropdowns
curl http://localhost:8090/categories -H "Authorization: Bearer $TOKEN"
```

### Filters

| Param          | Description                                |
| -------------- | ------------------------------------------ |
| `q`            | Substring across title / cast / desc / director |
| `type`         | `Movie` or `TV Show`                       |
| `rating`       | `TV-MA`, `PG-13`, …                        |
| `country`      | Substring match                            |
| `genre`        | Substring match on `listed_in`             |
| `release_year` | Exact year                                 |
| `year_from`    | Inclusive lower bound                      |
| `year_to`      | Inclusive upper bound                      |
| `limit`        | Page size (default 50, max 500)            |
| `offset`       | Page offset                                |

Response shape: `{ "total": <int>, "items": [...] }`.

## Implementation notes

- `show_id` is a `VARCHAR PRIMARY KEY` — external IDs are kept as strings.
- The `shows` table column names mirror the CSV exactly: `show_id, type, title, director, cast, country, date_added, release_year, rating, duration, listed_in, description`.
- The ETL groups rows into `(primary_genre, rating)` buckets before inserting them — see `_split_by_category_and_rating` in `app/etl.py`.
- Auth uses JWT bearer tokens (HS256). TTL is configurable via `JWT_TTL_MIN`.
- The web UI is a single static page mounted at `/static` and served from `/`.

## Reset the database

```bash
docker compose down -v   # -v drops the pg volume; ETL re-runs on next start
```

## Configuration

Environment variables read by the app (see `app/config.py`):

| Variable        | Default                                                          |
| --------------- | ---------------------------------------------------------------- |
| `DATABASE_URL`  | `postgresql+psycopg2://netflix:netflix@db:5432/netflix`          |
| `CSV_PATH`      | `/data/netflix.csv`                                              |
| `JWT_SECRET`    | `change-me-in-production` — override in any non-local environment |
| `JWT_TTL_MIN`   | `60`                                                             |
