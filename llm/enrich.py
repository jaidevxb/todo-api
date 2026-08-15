"""Turn the model's raw text into a trustworthy EnrichResult.

The model is an external, untrusted source — same as any other data arriving from
outside the system. Parse it, validate it against the schema, repair once if that
fails, and quarantine (never crash, never guess) if it still doesn't fit.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from llm.client import call_model
from llm.prompts import load_prompt
from llm.schema import EnrichRequest, EnrichResult

QUARANTINE_LOG = Path(__file__).resolve().parent.parent / "logs" / "quarantine.jsonl"

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _extract_json_text(raw: str) -> str:
    """Models like to wrap JSON in a code fence, or add prose around it. Strip that."""
    text = raw.strip()
    fence_match = _FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return text


def _parse_and_validate(raw: str) -> tuple[EnrichResult | None, str | None]:
    try:
        data = json.loads(_extract_json_text(raw))
    except json.JSONDecodeError as exc:
        return None, f"could not parse JSON: {exc}"
    try:
        return EnrichResult.model_validate(data), None
    except ValidationError as exc:
        return None, str(exc)


def _quarantine(payload: EnrichRequest, prompt_version: str, raw: str, error: str) -> None:
    QUARANTINE_LOG.parent.mkdir(exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prompt_version": prompt_version,
        "input": {"title": payload.title, "description": payload.description},
        "raw_output": raw,
        "error": error,
    }
    with QUARANTINE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def run_enrichment(payload: EnrichRequest, prompt_version: str = "enrich-v1") -> EnrichResult:
    system_prompt = load_prompt(f"{prompt_version}.md")
    # JSON-encoded and sent as its own message — never glued into the system prompt —
    # so an untrusted book description can't hijack the instructions above it
    user_content = json.dumps({"title": payload.title, "description": payload.description})

    raw = call_model(system_prompt, user_content)
    result, error = _parse_and_validate(raw)
    if result is not None:
        return result

    # repair retry — one extra call, with the model's own broken answer and the exact
    # validation error handed back to it. Fixes the large majority of failures.
    repair_content = (
        f"{user_content}\n\n"
        f"Your previous answer was rejected for this reason: {error}\n"
        f"Your previous answer was: {raw}\n"
        "Return only corrected JSON matching the schema."
    )
    raw2 = call_model(system_prompt, repair_content)
    result2, error2 = _parse_and_validate(raw2)
    if result2 is not None:
        return result2

    _quarantine(payload, prompt_version, raw2, error2)
    raise HTTPException(
        status_code=422,
        detail="model output failed validation twice; see logs/quarantine.jsonl",
    )
