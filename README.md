# Euribor Rates API

A self-hosted REST API that scrapes historical Euribor rates from
[euriborrates.com](https://euriborrates.com/historical-euribor) and returns
them as JSON. Built with **FastAPI** and designed to deploy on
[Railway](https://railway.app) in one click.

---

## Endpoints

| Method | Path                   | Description                          |
| ------ | ---------------------- | ------------------------------------ |
| `GET`  | `/`                    | API info & endpoint list             |
| `GET`  | `/docs`                | Interactive Swagger UI               |
| `GET`  | `/rates/latest`        | Most recent rate for every term      |
| `GET`  | `/rates`               | All historical data (all terms)      |
| `GET`  | `/rates?term=3m`       | All historical data filtered by term |
| `GET`  | `/rates/{term}`        | All historical data for one term     |
| `GET`  | `/rates/{term}/{year}` | Data for a specific term + year      |
| `GET`  | `/rates/year/{year}`   | All terms for a calendar year        |

**Available terms:** `1w`, `1m`, `3m`, `6m`, `12m`  
**Data range:** 1999 → today

---

## Example Responses

### `GET /rates/latest`

```json
{
  "success": true,
  "data": [
    { "date": "2026-02-20", "term": "1w", "rate": 2.524 },
    { "date": "2026-02-20", "term": "1m", "rate": 2.541 },
    { "date": "2026-02-20", "term": "3m", "rate": 2.536 },
    { "date": "2026-02-20", "term": "6m", "rate": 2.499 },
    { "date": "2026-02-20", "term": "12m", "rate": 2.453 }
  ],
  "meta": { "count": 5, "fetched_at": "2026-02-23T10:00:00Z" }
}
```

### `GET /rates/3m/2025`

```json
{
  "success": true,
  "data": [
    { "date": "2025-01-02", "term": "3m", "rate": 2.736 },
    { "date": "2025-01-03", "term": "3m", "rate": 2.731 },
    ...
  ],
  "meta": { "term": "3m", "year": 2025, "count": 256, "fetched_at": "..." }
}
```

---

## Caching

- **Past years** (< current year): cached for **24 hours** – the data never changes.
- **Current year**: cached for **1 hour** – refreshes daily rates promptly.

Cache is in-memory per process; it resets on restart.

---

## Local Development

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate   # Windows
# source .venv/bin/activate  # macOS / Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
uvicorn main:app --reload --port 8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the
interactive Swagger UI.

---

## Deploy to Railway

1. Push this repository to GitHub.
2. Go to [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**.
3. Select your repo – Railway will detect the Python project automatically,
   install `requirements.txt`, and run the `Procfile` start command.
4. Railway exposes the app on a public HTTPS URL. Set the `PORT` environment
   variable if needed (Railway injects it automatically).

The `railway.toml` in this repo configures the build and health-check settings.

---

## Data Source

Data is sourced from [euriborrates.com](https://euriborrates.com). Please
reference that site when sharing or using this data.
