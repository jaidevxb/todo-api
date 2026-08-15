"""Chat-completion client for POST /enrich.

Provider is swappable via three env vars only (LLM_BASE_URL, LLM_API_KEY,
LLM_MODEL) — see .env.example. Nothing else in this module or in main.py
knows which provider is behind them.
"""
import os

from openai import OpenAI

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            base_url=os.environ["LLM_BASE_URL"],
            api_key=os.environ["LLM_API_KEY"],
        )
    return _client


def call_model(system_prompt: str, user_content: str) -> str:
    """One call to the model. Returns raw text — not yet parsed or validated (Stage 3)."""
    client = get_client()
    res = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        temperature=0.2,  # low: we want the same shape back for the same input, not creativity
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
    )
    return res.choices[0].message.content
