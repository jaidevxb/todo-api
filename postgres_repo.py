"""Postgres backend — same five methods, same return shapes, different SQL dialect."""

import time
from pathlib import Path
from typing import Optional

import psycopg
from psycopg.rows import dict_row

from repository import TaskRepository

SCHEMA_FILE = Path(__file__).parent / "init.sql"


class PostgresTaskRepository(TaskRepository):
    def __init__(self, dsn: str):
        self.dsn = dsn

    def _conn(self):
        """A connection used as a context manager: commits on success, closes on exit."""
        return psycopg.connect(self.dsn, row_factory=dict_row)

    def init_schema(self, attempts: int = 15, delay: float = 2.0) -> None:
        """Apply init.sql, retrying while Postgres is still starting up.

        Compose waits on the healthcheck before starting the app, but this keeps the
        app usable when it is started by hand against a database that is still booting.
        """
        sql = SCHEMA_FILE.read_text()
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                with self._conn() as conn:
                    conn.execute(sql)
                return
            except psycopg.OperationalError as exc:
                last_error = exc
                print(f"Postgres not ready (attempt {attempt}/{attempts}), retrying in {delay}s")
                time.sleep(delay)
        raise RuntimeError(f"could not reach Postgres at startup: {last_error}")

    def list_tasks(self) -> list[dict]:
        with self._conn() as conn:
            return conn.execute("SELECT id, title, done FROM tasks ORDER BY id").fetchall()

    def get(self, task_id: int) -> Optional[dict]:
        with self._conn() as conn:
            return conn.execute(
                "SELECT id, title, done FROM tasks WHERE id = %s", (task_id,)
            ).fetchone()

    def create(self, title: str) -> dict:
        with self._conn() as conn:
            return conn.execute(
                "INSERT INTO tasks (title, done) VALUES (%s, false) RETURNING id, title, done",
                (title,),
            ).fetchone()

    def update(self, task_id: int, title: Optional[str], done: Optional[bool]) -> Optional[dict]:
        with self._conn() as conn:
            # COALESCE keeps the existing value wherever the caller passed None. The
            # casts tell Postgres the parameter types, which a bare NULL would not.
            return conn.execute(
                """
                UPDATE tasks
                   SET title = COALESCE(%s::text, title),
                       done  = COALESCE(%s::boolean, done)
                 WHERE id = %s
             RETURNING id, title, done
                """,
                (title, done, task_id),
            ).fetchone()

    def delete(self, task_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
            return cur.rowcount > 0
