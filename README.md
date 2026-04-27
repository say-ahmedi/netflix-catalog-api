# Netflix Catalog API

Reads `netflix.csv` → loads it into Postgres → exposes a FastAPI service with auth + filtered search.

## Stack
- **pandas** — CSV read & cleaning
- **SQLAlchemy** — ORM / table creation
- **FastAPI** — web interface
- **Postgres** — database
- **Docker / docker-compose** — local infrastructure

## Project layout
```
netflix_project/
├── app/
│   ├── main.py        # FastAPI app, models, auth, routes
│   ├── etl.py         # pandas CSV → Postgres loader
│   └── config.py      # env-driven settings
├── data/
│   └── netflix.csv    # <-- put the CSV here
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Run

1. Place `netflix.csv` in `./data/netflix.csv`
2. Build and start everything:
   ```bash
   docker compose up --build
   ```
3. On first start the API creates tables and bulk-loads the CSV (idempotent — restart won't reload).
4. Open http://localhost:8000/docs for the interactive Swagger UI.

## Use the API

```bash
# Register
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username":"alice","password":"secret123"}'

# Login (form-encoded — OAuth2 password flow)
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -d "username=alice&password=secret123" | jq -r .access_token)

# Search: comedies rated TV-MA, released 2018+
curl "http://localhost:8000/shows?genre=Comedies&rating=TV-MA&year_from=2018&limit=10" \
  -H "Authorization: Bearer $TOKEN"

# Full-text-ish search across title / cast / description
curl "http://localhost:8000/shows?q=stranger" -H "Authorization: Bearer $TOKEN"

# Filter dropdown values
curl http://localhost:8000/categories -H "Authorization: Bearer $TOKEN"
```

## Available filters

| Param          | Description                              |
| -------------- | ---------------------------------------- |
| `q`            | Substring across title/cast/desc/director|
| `type`         | `Movie` or `TV Show`                     |
| `rating`       | `TV-MA`, `PG-13`, …                      |
| `country`      | Substring match                          |
| `genre`        | Substring match on `listed_in`           |
| `release_year` | Exact year                               |
| `year_from`    | Inclusive lower bound                    |
| `year_to`      | Inclusive upper bound                    |
| `limit`/`offset`| Pagination (default 50, max 500)        |

## Notes on the spec
- **External IDs as strings** — `show_id` is `VARCHAR PRIMARY KEY`.
- **Column names match CSV** — table columns are `show_id, type, title, director, cast, country, date_added, release_year, rating, duration, listed_in, description`.
- **Split by category & rating** — the ETL groups rows into `(primary_genre, rating)` buckets before insertion (see `etl.py::_split_by_category_and_rating`).
- **Auth** — JWT bearer tokens (HS256, configurable TTL via `JWT_TTL_MIN`).

## Reset the database
```bash
docker compose down -v   # -v drops the pg volume; ETL will re-run on next start
```
