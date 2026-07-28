"""SQLite backend — the A2 storage code, moved behind the TaskRepository interface."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from repository import TaskRepository

DB_PATH = Path(__file__).parent / "tasks.db"

EXAMPLE_TASKS = [
    ("Buy milk", 0),
    ("Walk dog", 1),
    ("Write README", 0),
]


def _to_task(row) -> dict:
    """SQLite has no real boolean, so turn the stored 0/1 back into true/false."""
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}


class SqliteTaskRepository(TaskRepository):
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path

    @contextmanager
    def _conn(self):
        """Open a connection, commit on success, always close."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id    INTEGER PRIMARY KEY,
                    title TEXT    NOT NULL,
                    done  BOOLEAN NOT NULL DEFAULT 0
                )
                """
            )
            if conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0:
                conn.executemany("INSERT INTO tasks (title, done) VALUES (?, ?)", EXAMPLE_TASKS)

    def list_tasks(self) -> list[dict]:
        with self._conn() as conn:
            rows = conn.execute("SELECT id, title, done FROM tasks ORDER BY id").fetchall()
        return [_to_task(r) for r in rows]

    def get(self, task_id: int) -> Optional[dict]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return _to_task(row) if row else None

    def create(self, title: str) -> dict:
        with self._conn() as conn:
            cur = conn.execute("INSERT INTO tasks (title, done) VALUES (?, 0)", (title,))
            new_id = cur.lastrowid
        return {"id": new_id, "title": title, "done": False}

    def update(self, task_id: int, title: Optional[str], done: Optional[bool]) -> Optional[dict]:
        with self._conn() as conn:
            # COALESCE keeps the existing value wherever the caller passed None.
            conn.execute(
                "UPDATE tasks SET title = COALESCE(?, title), done = COALESCE(?, done) WHERE id = ?",
                (title, done, task_id),
            )
            row = conn.execute(
                "SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)
            ).fetchone()
        return _to_task(row) if row else None

    def delete(self, task_id: int) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cur.rowcount > 0
