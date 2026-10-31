# BikeCheck API

Backend for the [BikeCheck](https://github.com/Jagernout14/BikeCheck) iOS app — build your bikes from components and keep a service log for each part.

Built with **FastAPI + SQLite + JWT**. Written by Claude (Anthropic) as the server side for an iOS portfolio project; the iOS app is the main work.

## Features

- Registration and login with JWT bearer tokens
- **Shared catalog** of components: everyone can browse and add parts; only the author can edit or delete their part; a part can't be deleted while it's installed on any bike (`409`)
- **Private bikes**: each user sees only their own bikes, installed components and service records
- Service log per component (date + mileage) and a full history across all bikes with pagination

## Run locally

Requires Python 3.9+.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

export BIKECHECK_SECRET="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
uvicorn app.main:app --reload
```

- API: http://127.0.0.1:8000
- Interactive docs (Swagger): http://127.0.0.1:8000/docs

The database file `bikecheck.db` is created on first start and seeded with a small catalog.

**iOS Simulator** can reach the server at `http://127.0.0.1:8000`. For a real iPhone, run `uvicorn app.main:app --host 0.0.0.0` and use your Mac's local IP. Plain HTTP needs an App Transport Security exception in the app's `Info.plist` for development.

### Configuration

| Variable | Default | Meaning |
|---|---|---|
| `BIKECHECK_SECRET` | insecure dev key | JWT signing key — always set it |
| `BIKECHECK_DB` | `bikecheck.db` | SQLite file path |
| `BIKECHECK_TOKEN_DAYS` | `7` | Token lifetime in days |

### Tests

```bash
pytest
```

## API

All endpoints except `/auth/register`, `/auth/login` and `/health` need the header `Authorization: Bearer <token>`. Dates are `YYYY-MM-DD`; errors come as `{"detail": "..."}`.

### Auth

| Method | Path | Body | Result |
|---|---|---|---|
| POST | `/auth/register` | `{email, password}` (password ≥ 8) | `201` `{access_token, token_type, user}`; `409` if email taken |
| POST | `/auth/login` | `{email, password}` | `200` same as above; `401` on wrong credentials |
| GET | `/auth/me` | — | `{id, email, created_at}` |

### Catalog (shared)

| Method | Path | Notes |
|---|---|---|
| GET | `/catalog?q=&category=&limit=20&offset=0` | Search by name/brand, filter by category. Returns `{items, total, limit, offset}` |
| POST | `/catalog` | `{name, brand?, category, weight_g?, needs_service=true}` |
| GET | `/catalog/{id}` | |
| PATCH | `/catalog/{id}` | Author only (`403` otherwise) |
| DELETE | `/catalog/{id}` | Author only; `409` while installed on any bike |

Categories: `frame`, `fork`, `rims`, `hubs`, `drivetrain`, `headset`, `cockpit`, `brakes`, `suspension`, `other`.
Each item has `is_mine` so the app knows when to show Edit/Delete. Built-in items have `author_id: null` and can't be changed.

### Bikes (private)

| Method | Path | Notes |
|---|---|---|
| GET | `/bikes` | List with `component_count` and `total_weight_g` |
| POST | `/bikes` | `{name, photo_url?}` |
| GET | `/bikes/{id}` | Bike + `components` array |
| PATCH | `/bikes/{id}` | `{name?, photo_url?}` |
| DELETE | `/bikes/{id}` | Also deletes its components and service records |
| GET | `/bikes/{id}/components` | |
| POST | `/bikes/{id}/components` | Install a part: `{catalog_id, installed_at, note?}` |

### Components (installed on a bike)

| Method | Path | Notes |
|---|---|---|
| GET | `/components/{id}` | Includes `catalog`, `last_service_at`, `last_service_mileage_km` |
| PATCH | `/components/{id}` | `{installed_at?, note?}` |
| DELETE | `/components/{id}` | Removes the part from the bike |
| GET | `/components/{id}/services` | Newest first |
| POST | `/components/{id}/services` | `{done_at, mileage_km, note?}`; `422` if the part doesn't need service |

### Service history

| Method | Path | Notes |
|---|---|---|
| GET | `/services?bike_id=&limit=20&offset=0` | All your records, newest first, with `component_name`, `component_category`, `bike_id`, `bike_name` |
| GET | `/services/{id}` | |
| PATCH | `/services/{id}` | `{done_at?, mileage_km?, note?}` |
| DELETE | `/services/{id}` | |

## Project structure

```
app/
  main.py          # FastAPI app and routers
  db.py            # SQLite schema, seed catalog, connections
  security.py      # password hashing (PBKDF2) and JWT
  schemas.py       # request/response models
  deps.py          # current user, shared queries
  routers/         # auth, catalog, bikes, components, services
tests/test_api.py
```
