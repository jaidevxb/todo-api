"""Chat-completion client for POST /enrich.

Provider is swappable via three env vars only (LLM_BASE_URL, LLM_API_KEY,
LLM_MODEL) — see .env.example. Nothing else in this module or in main.py
knows which provider is behind them.
"""
import os
import random
import time

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
# We retry ourselves (below), so the SDK's own default of 2 retries is turned off —
# otherwise a single "attempt" here could silently fire up to 3 real requests.
MAX_OWN_ATTEMPTS = 3

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=os.environ["LLM_BASE_URL"],
            api_key=os.environ["LLM_API_KEY"],
            timeout=TIMEOUT_SECONDS,
            max_retries=0,
        )
    return _client


def _is_retryable(exc: Exception) -> bool:
    # Retry on timeouts, connection errors, 429, and 5xx.
    # Never on 400/401/403 — a bad request or bad key is still bad on the next try,
    # and every pointless retry burns real quota on a metered free tier.
    if isinstance(exc, (APITimeoutError, APIConnectionError, RateLimitError)):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code >= 500
    return False


def _retry_after_seconds(exc: Exception) -> float | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    value = response.headers.get("retry-after")
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def call_model(system_prompt: str, user_content: str) -> tuple[str, dict]:
    """One (possibly retried) call to the model.

    Returns (raw_text, usage) where usage has input_tokens, output_tokens, duration_ms.
    Raises the underlying openai exception if every attempt fails — main.py's
    exception handlers turn that into a 504/429/502 for the caller.
    """
    client = get_client()
    model = os.environ["LLM_MODEL"]
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]

    for attempt in range(MAX_OWN_ATTEMPTS):
        started = time.monotonic()
        try:
            res = client.chat.completions.create(
                model=model,
                temperature=0.2,  # low: same input should get the same shape back
                messages=messages,
            )
        except Exception as exc:
            if not _is_retryable(exc) or attempt == MAX_OWN_ATTEMPTS - 1:
                raise
            wait = _retry_after_seconds(exc)
            if wait is None:
                wait = (2**attempt) + random.uniform(0, 0.5)  # 1s, 2s, 4s + jitter
            time.sleep(wait)
            continue

        duration_ms = round((time.monotonic() - started) * 1000)
        usage = {
            "input_tokens": res.usage.prompt_tokens if res.usage else None,
            "output_tokens": res.usage.completion_tokens if res.usage else None,
            "duration_ms": duration_ms,
        }
        return res.choices[0].message.content, usage

    raise AssertionError("unreachable")  # loop always returns or raises
