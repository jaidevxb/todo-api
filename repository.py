"""The storage interface the API talks to, and the factory that picks an implementation.

Routes never import a database driver. They call these five methods and get plain
dicts back, so swapping SQLite for Postgres touches only the implementation files.
"""

import os
from abc import ABC, abstractmethod
from typing import Optional


class TaskRepository(ABC):
    """What a storage backend has to provide. Both backends return the same shapes."""

    @abstractmethod
    def init_schema(self) -> None:
        """Create the table if missing and seed the example tasks once."""

    @abstractmethod
    def list_tasks(self) -> list[dict]:
        """Every task, ordered by id."""

    @abstractmethod
    def get(self, task_id: int) -> Optional[dict]:
        """One task, or None if no row has that id."""

    @abstractmethod
    def create(self, title: str) -> dict:
        """Insert a task with done=false and return it, including its new id."""

    @abstractmethod
    def update(self, task_id: int, title: Optional[str], done: Optional[bool]) -> Optional[dict]:
        """Update the given fields (None means leave alone). None if no such row."""

    @abstractmethod
    def delete(self, task_id: int) -> bool:
        """Delete the row. True if something was deleted, False if the id was unknown."""


def get_repository() -> TaskRepository:
    """Choose a backend from DATABASE_URL.

    A postgres:// or postgresql:// URL selects Postgres; anything else (including no
    DATABASE_URL at all) falls back to the local SQLite file, so the app still runs
    without Docker.
    """
    url = os.getenv("DATABASE_URL", "")
    if url.startswith(("postgres://", "postgresql://")):
        from postgres_repo import PostgresTaskRepository

        return PostgresTaskRepository(url)

    from sqlite_repo import SqliteTaskRepository

    return SqliteTaskRepository()
