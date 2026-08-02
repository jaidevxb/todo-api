from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()  # read .env when running outside Docker; a no-op if the file is absent

import auth  # noqa: E402,F401  creates the Supabase client at import time; must come after load_dotenv()
from repository import get_repository  # noqa: E402

repo = get_repository()  # must come after load_dotenv() — it reads DATABASE_URL


class TaskCreate(BaseModel):
    title: Optional[str] = None


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    done: Optional[bool] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    repo.init_schema()
    print("Server running and connected to Supabase")
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/tasks", summary="List all tasks")
def get_tasks():
    return repo.list_tasks()


@app.get("/tasks/{task_id}", summary="Get a single task by id")
def get_task(task_id: int):
    task = repo.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@app.post("/tasks", status_code=201, summary="Create a new task")
def create_task(task: TaskCreate):
    if not task.title or not task.title.strip():
        raise HTTPException(status_code=400, detail="title is required")
    return repo.create(task.title)


@app.put("/tasks/{task_id}", summary="Update a task's title or done status")
def update_task(task_id: int, update: TaskUpdate):
    if update.title is not None and not update.title.strip():
        raise HTTPException(status_code=400, detail="title cannot be empty")
    task = repo.update(task_id, update.title, update.done)
    if task is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    return task


@app.delete("/tasks/{task_id}", status_code=204, summary="Delete a task")
def delete_task(task_id: int):
    if not repo.delete(task_id):
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
