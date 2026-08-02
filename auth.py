"""Supabase Auth: client setup, routes (signup/login/logout), and the bearer-token guard."""

import os
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from supabase import Client, create_client
from supabase_auth.errors import AuthApiError

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

router = APIRouter(prefix="/auth", tags=["auth"])

# auto_error=False so a missing/malformed header falls through to get_current_user,
# which raises AuthError with the assignment's exact {"error": ...} body instead of
# FastAPI's default {"detail": "Not authenticated"}.
_bearer_scheme = HTTPBearer(auto_error=False, description="Paste the access_token returned by /auth/login")


class AuthError(Exception):
    """Carries the {"error": ...} body the assignment spec requires, distinct from
    FastAPI's default {"detail": ...} shape used by validation errors elsewhere."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


class Credentials(BaseModel):
    email: str = None
    password: str = None


def get_current_user(creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)):
    """Dependency that verifies the bearer token with Supabase and returns its user.

    Applied to every route that requires a logged-in caller. FastAPI runs this before
    the route body, so a route only ever executes once the token is known-good. This
    replaces the header-parsing that used to live directly inside /protected/profile.
    """
    if creds is None or not creds.credentials:
        raise AuthError(401, "Access token required")
    try:
        response = supabase.auth.get_user(creds.credentials)
    except AuthApiError:
        raise AuthError(401, "Invalid or expired token")
    if response is None or response.user is None:
        raise AuthError(401, "Invalid or expired token")
    return response.user


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


@router.post("/logout", status_code=204, summary="Terminate the current session")
def logout(user=Depends(get_current_user)):
    supabase.auth.sign_out()
