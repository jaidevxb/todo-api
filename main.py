import os
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

load_dotenv()  # read .env when running outside Docker; a no-op if the file is absent

# auth and repository both read env vars at import time, so they must come after load_dotenv()
from auth import AuthError, get_current_user, router as auth_router  # noqa: E402
from repository import get_repository  # noqa: E402
from llm.enrich import run_enrichment  # noqa: E402
from llm.schema import EnrichRequest, EnrichResult, STUB_RESULT  # noqa: E402

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


app = FastAPI(
    title="Task API",
    description="A to-do list API with Supabase-backed auth. Protected routes take a "
    "Bearer access_token from POST /auth/login — click Authorize below to try them.",
    lifespan=lifespan,
)
app.include_router(auth_router)


@app.exception_handler(AuthError)
def auth_error_handler(request: Request, exc: AuthError):
    return JSONResponse(status_code=exc.status_code, content={"error": exc.message})


@app.exception_handler(RequestValidationError)
def validation_error_handler(request: Request, exc: RequestValidationError):
    # FastAPI's default is 422; we want a plain 400 naming the offending field,
    # so a malformed request never reaches (and never bills) the model.
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"] if part != "body") or "body"
    return JSONResponse(status_code=400, content={"error": f"{field}: {first['msg']}"})


@app.get("/")
def root():
    return {"name": "Task API", "version": "1.0", "endpoints": ["/tasks"]}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/public/info", summary="Public, unauthenticated info")
def public_info():
    return {"message": "Welcome stranger! This info is public."}


@app.get("/protected/profile", summary="The caller's own profile")
def profile(user=Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "created_at": user.created_at}


@app.get("/protected/dashboard", summary="Another route behind the same auth guard")
def dashboard(user=Depends(get_current_user)):
    return {"message": f"Welcome back, {user.email}"}


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


@app.post("/enrich", response_model=EnrichResult, summary="Enrich a scraped book record")
def enrich(payload: EnrichRequest):
    if os.getenv("LLM_STUB") == "1":
        return STUB_RESULT
    return run_enrichment(payload)
