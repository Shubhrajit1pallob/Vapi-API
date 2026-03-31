#!/usr/bin/env python3
"""Upload survey template questions to the backend PostgreSQL endpoint.

Usage:
  python3 backend/scripts/populate_survey_template.py --file file-2.json

By default, this sends only the first 10 questions to:
  http://localhost:8000/survey-templates
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any
from urllib import error, request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload survey questions to /survey-templates for backend testing."
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to input JSON file. Supports top-level list or {'questions': [...]}.",
    )
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of questions to upload (default: 10)",
    )
    parser.add_argument(
        "--version",
        type=int,
        default=None,
        help="Optional explicit template version.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20,
        help="HTTP timeout in seconds (default: 20)",
    )
    return parser.parse_args()


def load_questions(file_path: Path) -> list[dict[str, Any]]:
    with file_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if isinstance(data, list):
        questions = data
    elif isinstance(data, dict) and isinstance(data.get("questions"), list):
        questions = data["questions"]
    else:
        raise ValueError("Input JSON must be a list or an object with a 'questions' list.")

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(questions, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Question at index {idx} is not a JSON object.")

        q_text = item.get("Q")
        q_type = item.get("type", "open")
        answers = item.get("A", [])
        question_id = item.get("id") or f"q{idx}"

        if not isinstance(q_text, str) or not q_text.strip():
            raise ValueError(f"Question at index {idx} is missing a non-empty 'Q' field.")
        if not isinstance(answers, list):
            raise ValueError(f"Question at index {idx} must have list 'A'.")

        normalized.append(
            {
                "id": str(question_id),
                "type": str(q_type),
                "Q": q_text.strip(),
                "A": answers,
            }
        )

    return normalized


def upload_template(
    api_base: str,
    questions: list[dict[str, Any]],
    version: int | None,
    timeout: float,
) -> dict[str, Any]:
    endpoint = f"{api_base.rstrip('/')}/survey-templates"
    payload: dict[str, Any] = {"questions": questions}
    if version is not None:
        payload["version"] = version

    body = json.dumps(payload).encode("utf-8")
    req = request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {"success": True}
    except error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {endpoint}: {err_body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Could not reach backend at {endpoint}: {exc.reason}") from exc


def main() -> int:
    args = parse_args()

    file_path = Path(args.file)
    if not file_path.exists():
        print(f"Input file not found: {file_path}", file=sys.stderr)
        return 1

    if args.limit < 1:
        print("--limit must be >= 1", file=sys.stderr)
        return 1

    try:
        all_questions = load_questions(file_path)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"Invalid input JSON: {exc}", file=sys.stderr)
        return 1

    trimmed = all_questions[: args.limit]
    if not trimmed:
        print("No questions found to upload.", file=sys.stderr)
        return 1

    try:
        result = upload_template(
            api_base=args.api_base,
            questions=trimmed,
            version=args.version,
            timeout=args.timeout,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Uploaded survey template successfully.")
    print(f"Questions sent: {len(trimmed)}")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
