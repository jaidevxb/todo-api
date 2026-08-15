"""One structured log line per model call, to stdout — see Twelve-Factor App: Logs.

Not a file, so nothing here needs rotation or its own gitignore entry; the environment
(a shell redirect today, a log collector in production) decides where these lines go.
"""
import json
import logging

logger = logging.getLogger("llm.cost")
logger.setLevel(logging.INFO)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)


def log_call(prompt_version: str, model: str, usage: dict, is_repair_call: bool) -> None:
    logger.info(
        json.dumps(
            {
                "event": "llm_call",
                "prompt_version": prompt_version,
                "model": model,
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "duration_ms": usage.get("duration_ms"),
                "is_repair_call": is_repair_call,
            }
        )
    )
