# Advanced Python - Code-Along Version

One file per session. Each file is complete, runs on its own with `python <file>`,
and has a demo at the bottom. No stubs, no pytest, no `make`.

**How to use it in class:** the trainer opens the file and types it top to bottom
(or shares it); participants type along into a blank file, then run it.
Comments marked `--- Step N ---` are the natural pause points.

## One-time setup (everyone)

```bat
python -m venv .venv
.venv\Scripts\activate
pip install requests httpx pandas pydantic pydantic-settings "psycopg[binary,pool]" SQLAlchemy fastapi uvicorn web.py
```

All commands below are run from this `codealong` folder.

## Day 1

| # | Session | File | Needs | ~Time |
|---|---|---|---|---|
| 1 | OOP: dataclasses, ABC, dunder methods | `day1/01_oop.py` | - | 60 |
| 2 | Decorators, context managers, generators | `day1/02_language_features.py` | - | 45 |
| 3 | Exception handling | `day1/03_exceptions.py` | - | 30 |
| 4 | Requests: retries, pagination | `day1/04_requests_client.py` | mock server (below) | 50 |
| 5 | Pandas: clean, join, aggregate | `day1/05_pandas.py` | - | 70 |
| 6 | Pydantic: validation + settings | `day1/06_pydantic.py` | - | 45 |
| 7 | Integration pipeline | `day1/07_pipeline.py` | needs 5 and 6 | 30 |

Mock server for session 4 (leave running in a second terminal; sessions 11 also use it):

```bat
uvicorn day1.mock_server:app --port 8001
```

## Day 2

| # | Session | File | Needs | ~Time |
|---|---|---|---|---|
| 9 | Psycopg: raw SQL, transactions, pool | `day2/09_psycopg.py` | **Postgres** (Docker command in file) | 40 |
| 10 | SQLAlchemy ORM, N+1 problem | `day2/10_sqlalchemy.py` (+ `db.py`) | - (SQLite) | 55 |
| 11 | Async: gather, semaphore | `day2/11_async.py` | mock server | 40 |
| 12 | Threads vs processes, race conditions | `day2/12_parallel.py` | - | 55 |
| 13 | Web.py | `day2/13_webpy.py` | - | 10 |
| 14 | FastAPI REST API | `day2/14_fastapi.py` (+ `db.py`) | - (SQLite) | 80 |

Run commands:

```bat
python day2/10_sqlalchemy.py
python day2/12_parallel.py
python day2/13_webpy.py 8080
uvicorn 14_fastapi:app --app-dir day2 --reload      # then open http://localhost:8000/docs
```


