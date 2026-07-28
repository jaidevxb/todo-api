import sqlite3
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

DB_PATH = Path(__file__).parent / "tasks.db"

EXAMPLE_TASKS = [
    ("Buy milk", 0),
    ("Walk dog", 1),
    ("Write README", 0),
]

@contextmanager
def db():
    """Open a connection, commit on success, always close."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    """Create tasks.db and the tasks table if missing, seeding it once."""
    with db() as conn:
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

class TaskCreate(BaseModel):
    title: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(lifespan=lifespan)

def to_task(row):
    """SQLite has no real boolean, so turn the stored 0/1 back into true/false."""
    return {"id": row["id"], "title": row["title"], "done": bool(row["done"])}

@app.get("/")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/tasks", summary="List all tasks")
def get_tasks():
    with db() as conn:
        rows = conn.execute("SELECT id, title, done FROM tasks ORDER BY id").fetchall()
    return [to_task(r) for r in rows]

@app.get("/tasks/{task_id}", summary="Get a single task by id")
def get_task(task_id: int):
    with db() as conn:
        row = conn.execute("SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return to_task(row)

@app.post("/tasks", status_code=201, summary="Create a new task")
def create_task(task: TaskCreate):
    if not task.title or not task.title.strip():
        raise HTTPException(status_code=400, detail="title is required")
    with db() as conn:
        cur = conn.execute("INSERT INTO tasks (title, done) VALUES (?, 0)", (task.title,))
        new_id = cur.lastrowid
    return {"id": new_id, "title": task.title, "done": False}

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None

@app.put("/tasks/{task_id}", summary="Update a task's title or done status")
def update_task(task_id: int, update: TaskUpdate):
    with db() as conn:
        row = conn.execute("SELECT id, title, done FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
        title, done = row["title"], bool(row["done"])
        if update.title is not None:
            if not update.title.strip():
                raise HTTPException(status_code=400, detail="title cannot be empty")
            title = update.title
        if update.done is not None:
            done = update.done
        conn.execute("UPDATE tasks SET title = ?, done = ? WHERE id = ?", (title, int(done), task_id))
    return {"id": task_id, "title": title, "done": done}

@app.delete("/tasks/{task_id}", status_code=204, summary="Delete a task")
def delete_task(task_id: int):
    with db() as conn:
        cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")