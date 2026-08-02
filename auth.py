"""Supabase Auth: client setup and the open signup/login routes."""

import os

from fastapi import APIRouter
from pydantic import BaseModel
from supabase import Client, create_client
from supabase_auth.errors import AuthApiError

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthError(Exception):
    """Carries the {"error": ...} body the assignment spec requires, distinct from
    FastAPI's default {"detail": ...} shape used by validation errors elsewhere."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


class Credentials(BaseModel):
    email: str = None
    password: str = None


@router.post("/signup", status_code=201, summary="Create a new user account")
def signup(creds: Credentials):
    if not creds.email or not creds.password:
        raise AuthError(400, "email and password are required")
    try:
        result = supabase.auth.sign_up({"email": creds.email, "password": creds.password})
    except AuthApiError as exc:
        raise AuthError(400, str(exc))
    return result.user


@router.post("/login", summary="Authenticate a user and return a JWT")
def login(creds: Credentials):
    if not creds.email or not creds.password:
        raise AuthError(400, "email and password are required")
    try:
        result = supabase.auth.sign_in_with_password(
            {"email": creds.email, "password": creds.password}
        )
    except AuthApiError:
        raise AuthError(401, "Invalid login credentials")
    return {
        "access_token": result.session.access_token,
        "refresh_token": result.session.refresh_token,
        "user": result.user,
    }
