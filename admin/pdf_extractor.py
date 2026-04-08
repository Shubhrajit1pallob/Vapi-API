"""
PDF → questions JSON + Vapi system prompt.

Total LLM spend per PDF upload:
  - 1 call to extract all questions from the PDF text
  - 1 small call to generate the system prompt template

At session time: 0 LLM calls — just string substitution of {{QUESTIONS}}.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, List, Optional, Tuple

import anthropic
from pypdf import PdfReader


# ── PDF text extraction (free — no LLM) ──────────────────────────────

def _extract_pdf_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    pages = []
    for i, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            pages.append(f"[PAGE {i}]\n{text}")
    return "\n\n".join(pages)


# ── Question extraction ───────────────────────────────────────────────

_Q_SYSTEM = """\
You extract survey questions from raw PDF text and format them for a voice AI agent.

Return a JSON array. Each element:
{
  "id":      "q1",                  // sequential, no gaps
  "section": "Demographics",        // top-level section heading
  "type":    "open|mcq|multi_select|boolean|scale|number|datetime",
  "Q":       "What is your birth year?",   // clean, natural speech phrasing
  "A":       []                     // answer options for mcq/multi_select/scale/boolean; empty otherwise
}

Type rules:
  open         – free-text answer
  mcq          – pick exactly one option
  multi_select – pick one or more
  boolean      – strictly Yes / No
  scale        – ordered frequency or intensity (e.g. Never … Daily)
  number       – numeric value (age, weight, minutes, etc.)
  datetime     – date or time

Extraction rules:
  - Include EVERY question, including each row of a grid/matrix table.
  - For grid rows: type = "scale", A = the column headers.
  - Skip page headers, footers, section intros, and instruction paragraphs.
  - "Please describe" / "Other" follow-ups → do NOT emit as a separate question.
  - Make Q text natural spoken language: remove "(select all that apply)",
    "(check all that apply)", parenthetical codes, etc. Emma will handle phrasing.
  - Preserve A options verbatim — Emma reads them out to the patient.

Output ONLY valid JSON. No markdown, no commentary.\
"""


def _parse_json_response(raw: str) -> List[Any]:
    raw = raw.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"^```\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        result = json.loads(raw)
        if not isinstance(result, list):
            raise ValueError("Expected JSON array")
        return result
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(f"Bad JSON from Claude: {e}\n\nRaw (500 chars):\n{raw[:500]}") from e


def _extract_questions_chunk(
    client: anthropic.Anthropic,
    chunk: str,
    start_index: int,
) -> List[Any]:
    """One API call for one chunk. IDs start at q{start_index}."""
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=8000,
        system=_Q_SYSTEM,
        messages=[{
            "role": "user",
            "content": f"Start IDs from q{start_index}. Extract all questions:\n\n{chunk}",
        }],
    )
    return _parse_json_response(resp.content[0].text)


def _chunk_by_pages(pdf_text: str, pages_per_chunk: int = 10) -> List[str]:
    """Split PDF text on [PAGE N] markers into fixed-size chunks."""
    splits = re.split(r"(\[PAGE \d+\])", pdf_text)
    # splits alternates: ['', '[PAGE 1]', 'text...', '[PAGE 2]', 'text...', ...]
    chunks: List[str] = []
    current: List[str] = []
    page_count = 0
    for part in splits:
        if re.match(r"\[PAGE \d+\]", part):
            page_count += 1
            if page_count > pages_per_chunk and current:
                chunks.append("".join(current).strip())
                current = []
                page_count = 1
        current.append(part)
    if current:
        chunks.append("".join(current).strip())
    return [c for c in chunks if c]


def _extract_questions(
    client: anthropic.Anthropic,
    pdf_text: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> List[Any]:
    """
    Chunk PDF into 10-page segments and extract questions per chunk.
    Prevents output token truncation on large surveys.
    """
    chunks = _chunk_by_pages(pdf_text, pages_per_chunk=10)
    all_questions: List[Any] = []

    for i, chunk in enumerate(chunks, start=1):
        if progress_callback:
            progress_callback(f"Extracting questions — chunk {i}/{len(chunks)}…")
        qs = _extract_questions_chunk(client, chunk, start_index=len(all_questions) + 1)
        all_questions.extend(qs)

    # Renumber sequentially after merge
    for idx, q in enumerate(all_questions, start=1):
        q["id"] = f"q{idx}"

    return all_questions


# ── System prompt generation ──────────────────────────────────────────

_SP_SYSTEM = """\
You write system prompts for Emma, a healthcare voice AI assistant built on Vapi.

Emma's job: conduct a brief well-being check-in, ask exactly 3 survey questions
(injected at runtime via {{QUESTIONS}}), record each answer with the record_answer
tool, then end the call with the endCall tool.

Write a complete system prompt that:
1. Defines Emma's persona (warm, patient, professional healthcare assistant).
2. States the exact protocol:
   - Greet patient, introduce yourself.
   - Ask question 1 → wait → call record_answer(question_id, patient_answer) → next.
   - Repeat for questions 2 and 3.
   - After q3: ask "Any feedback on how this call went?" → record it → thank patient → endCall.
3. Gives voice-specific guidance (speak slowly, rephrase if confused, read options aloud for choice questions).
4. Contains the literal placeholder text {{QUESTIONS}} where the 3 questions will be inserted.

The prompt must be practical and tight — no fluff. Emma must never skip calling record_answer before moving on.

Output ONLY the system prompt text. No markdown headers, no explanation.\
"""


def _generate_system_prompt(
    client: anthropic.Anthropic,
    questions_sample: List[Any],
    additional_instructions: str = "",
) -> str:
    """
    One small API call.
    questions_sample: first ~10 questions to give Claude context on the survey domain.
    additional_instructions: any extra rules the admin typed in.
    """
    sample_text = json.dumps(questions_sample[:10], indent=2)
    user_msg = (
        f"Survey domain context (first 10 questions):\n{sample_text}\n\n"
        + (f"Additional instructions from admin:\n{additional_instructions}\n\n" if additional_instructions else "")
        + "Write the Emma system prompt."
    )
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1500,
        system=_SP_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    return resp.content[0].text.strip()


# ── Public API ────────────────────────────────────────────────────────

def extract_from_pdf(
    pdf_path: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> Tuple[List[Any], str]:
    """
    Full pipeline. Returns (questions, system_prompt).
    2 LLM calls total.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")

    client = anthropic.Anthropic(api_key=api_key)

    def log(msg: str) -> None:
        if progress_callback:
            progress_callback(msg)

    log("Extracting text from PDF…")
    pdf_text = _extract_pdf_text(pdf_path)
    log(f"PDF text extracted ({len(pdf_text):,} chars). Calling Claude for questions…")

    questions = _extract_questions(client, pdf_text, progress_callback=progress_callback)
    log(f"{len(questions)} questions extracted. Generating system prompt…")

    system_prompt = _generate_system_prompt(client, questions)
    log("Done.")

    return questions, system_prompt


def regenerate_system_prompt(
    questions: List[Any],
    additional_instructions: str,
    progress_callback: Optional[Callable[[str], None]] = None,
) -> str:
    """
    Regenerate system prompt with admin's additional instructions.
    1 LLM call.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env")

    if progress_callback:
        progress_callback("Regenerating system prompt…")

    client = anthropic.Anthropic(api_key=api_key)
    result = _generate_system_prompt(client, questions, additional_instructions)

    if progress_callback:
        progress_callback("Done.")

    return result
