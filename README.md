# Task API

A small CRUD API for managing a to-do list, built with FastAPI. Tasks live in Postgres,
running in Docker alongside the app. `docker compose up` starts the whole stack.

The same API also runs against a local SQLite file with no Docker at all — the storage
backend is chosen at startup from `DATABASE_URL`.

## Quick start

```bash
git clone https://github.com/jaidevxb/todo-api.git
cd todo-api
cp .env.example .env      # Windows: copy .env.example .env
docker compose up
```

That is the whole setup. Compose builds the app image, starts Postgres, waits for its
healthcheck, applies `init.sql`, and starts the API on <http://localhost:8000>
(Swagger UI at <http://localhost:8000/docs>).

### Running without Docker

Leave `DATABASE_URL` unset — or set it to anything that does not start with `postgres`
— and the app falls back to the SQLite file from the previous assignment:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Architecture — and an honest note about it

```
routes (main.py)  ->  TaskRepository (repository.py)  ->  sqlite_repo.py
                                                      \-> postgres_repo.py
```

`main.py` imports no database driver. It calls five methods — `list_tasks`, `get`,
`create`, `update`, `delete` — and gets plain dicts back. Each backend does its own SQL
and normalises its own quirks, so the JSON coming out is identical either way.

**Being straight about what was already there:** the previous assignment did *not* have
this seam. Its SQL sat inline in the route handlers, so there was no in-memory-style
interface for a Postgres repository to implement. The interface was extracted here, as
its own commit (`Extract TaskRepository interface behind the routes`), and only then was
Postgres added. So the claim "swapping storage changed only one file" is true of the
second step, not of the assignment as a whole:

- Extracting the interface **did** rewrite `main.py` — the SQL had to come out of it.
  HTTP behaviour was unchanged, and that was verified by re-running the full request set
  against SQLite and diffing the responses.
- Adding Postgres after that added exactly one new file, `postgres_repo.py`, and changed
  **zero** lines in `main.py`. `git log --oneline -- main.py` shows no commit for it.

That second step is the part that proves the layering works. The first step is the price
of not having had the layer to begin with.

### Known limitation

Both repositories open a connection per operation. That is fine at this size and keeps
the two backends symmetrical, but a connection pool (`psycopg_pool`) is the obvious next
step for anything with real traffic.

## Configuration

All configuration comes from `.env`, which is **gitignored**. `.env.example` is
committed — copy it and edit as needed.

| Variable            | Used by         | Purpose                                  |
| ------------------- | --------------- | ---------------------------------------- |
| `POSTGRES_USER`     | db container    | Role created on first boot               |
| `POSTGRES_PASSWORD` | db container    | Its password                             |
| `POSTGRES_DB`       | db container    | Database created on first boot           |
| `POSTGRES_PORT`     | compose         | Host port mapped to Postgres (def. 5432) |
| `DATABASE_URL`      | app             | Connection string; picks the backend     |

`DATABASE_URL` appears in two places on purpose. In `.env` it points at `localhost`, for
running uvicorn on your machine against the container. Inside Compose the `app` service
overrides the host with `db`, because on the compose network the service name is the
hostname — `localhost` inside a container is that container, not Postgres.

## Schema

One file, [init.sql](init.sql), defines the Postgres table. It is applied twice over,
deliberately:

1. Postgres runs it on first boot, via the `/docker-entrypoint-initdb.d` mount. This
   only ever fires when the volume is empty.
2. The app runs it at startup, so a volume that already exists but has no table still
   ends up with one.

Both paths are safe because the file is idempotent — `CREATE TABLE IF NOT EXISTS`, and a
seed guarded by `WHERE NOT EXISTS (SELECT 1 FROM tasks)`. The three example tasks appear
on a fresh database and never duplicate on later starts.

The SQLite backend keeps its own `CREATE TABLE` in `sqlite_repo.py`, since the dialects
differ (`SERIAL` vs `INTEGER PRIMARY KEY`, real booleans vs `0`/`1`).

## Persistence, and how it was checked

Postgres writes to the named volume `pgdata`, mounted at `/var/lib/postgresql/data`.
The volume is what outlives the container — `docker compose down` destroys containers
but leaves the volume alone. (`docker compose down -v` deletes it, and with it your
data.)

The check that was actually run:

```bash
# 1. Mutate the seeded data through the API
curl -X POST http://localhost:8000/tasks -H "Content-Type: application/json" \
     -d "{\"title\":\"Survives a restart\"}"     # -> 201, id 4
curl -X PUT  http://localhost:8000/tasks/4 -H "Content-Type: application/json" \
     -d "{\"done\":true}"                        # -> 200
curl -X DELETE http://localhost:8000/tasks/3     # -> 204

# 2. Confirm in the database itself
docker compose exec db psql -U todo -d todo -c "SELECT * FROM tasks ORDER BY id;"
#  id |       title        | done
# ----+--------------------+------
#   1 | Buy milk           | f
#   2 | Walk dog           | t
#   4 | Survives a restart | t

# 3. Destroy both containers and the network — not the volume
docker compose down

# 4. Bring the stack back up from scratch
docker compose up -d

# 5. Read through the API again
curl http://localhost:8000/tasks
# [{"id":1,"title":"Buy milk","done":false},
#  {"id":2,"title":"Walk dog","done":true},
#  {"id":4,"title":"Survives a restart","done":true}]
```

Three things in that last response are the actual proof: the created row (id 4) is
still there, the edit to it stuck, and the deleted row (id 3) stayed deleted. The seed
did not re-run either — no second "Write README" — which confirms the `WHERE NOT EXISTS`
guard holds across restarts.

## Endpoints

| Method | Path          | Description                | Success | Errors   |
| ------ | ------------- | -------------------------- | ------- | -------- |
| GET    | `/`           | API info                   | 200     | —        |
| GET    | `/health`     | Health check               | 200     | —        |
| GET    | `/tasks`      | List all tasks             | 200     | —        |
| GET    | `/tasks/{id}` | Get one task               | 200     | 404      |
| POST   | `/tasks`      | Create a new task          | 201     | 400      |
| PUT    | `/tasks/{id}` | Update a task's title/done | 200     | 400, 404 |
| DELETE | `/tasks/{id}` | Delete a task              | 204     | 404      |

Unchanged since the in-memory version. The full request set above was run against both
SQLite and Postgres and the responses matched byte for byte, including error bodies.

## Example request

```bash
curl -i -X POST http://localhost:8000/tasks -H "Content-Type: application/json" -d "{\"title\":\"Buy milk\"}"
```

```
HTTP/1.1 201 Created
content-type: application/json

{"id":4,"title":"Buy milk","done":false}
```

## Example SQL

Against Postgres:

```bash
docker compose exec db psql -U todo -d todo -c "SELECT * FROM tasks WHERE done = true;"
```

More queries, run against the SQLite version with their output, are in
[sql-notes.md](sql-notes.md).

## Useful commands

```bash
docker compose up -d          # start in the background
docker compose logs -f app    # follow the API logs
docker compose ps             # container + health status
docker compose down           # stop and remove containers, keep data
docker compose down -v        # ...and delete the volume, wiping the database
docker compose up -d --build  # rebuild the image after changing the code
```

## Database viewer

`tasks.db` opened in a SQLite viewer, showing the `tasks` table after a first run — the
three seed rows, with `done` displayed as `FALSE`/`TRUE`. This is the SQLite backend,
which is still the fallback when `DATABASE_URL` is not set:

![tasks.db open in a SQLite viewer](db-screenshot.png)

## Swagger UI

![Swagger UI screenshot](swagger-screenshot.png)
