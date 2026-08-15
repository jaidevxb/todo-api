"""Runs evals/cases.json against a running POST /enrich and reports how many matched.

Usage:
    venv/Scripts/python.exe evals/run_eval.py [base_url]

Defaults to http://localhost:8000. Makes one real model call per case (eight total) —
don't run this in a loop against a metered free tier.
"""
import json
import sys
from pathlib import Path

import httpx

CASES_PATH = Path(__file__).resolve().parent / "cases.json"


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    cases = json.loads(CASES_PATH.read_text(encoding="utf-8"))

    matched = 0
    failures = []
    for case in cases:
        resp = httpx.post(f"{base_url}/enrich", json=case["input"], timeout=60.0)
        if resp.status_code != 200:
            failures.append((case["id"], f"HTTP {resp.status_code}: {resp.text}"))
            continue

        result = resp.json()
        reasons = []
        if result.get("category") != case["expected_category"]:
            reasons.append(
                f"expected category '{case['expected_category']}', got '{result.get('category')}'"
            )
        expected_flag = case.get("expected_flag")
        if expected_flag and expected_flag not in result.get("quality_flags", []):
            reasons.append(
                f"expected flag '{expected_flag}' in quality_flags, got {result.get('quality_flags')}"
            )

        if reasons:
            failures.append((case["id"], "; ".join(reasons)))
        else:
            matched += 1

    total = len(cases)
    print(f"{matched}/{total} matched")
    for case_id, reason in failures:
        print(f"  FAIL {case_id}: {reason}")


if __name__ == "__main__":
    main()
