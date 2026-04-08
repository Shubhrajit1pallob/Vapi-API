"""
Vapi routes:
  POST /patient/verify          – patient login (patient_id + PIN)
  GET  /start-session/{patient_id} – Vapi config with 3 random questions injected
  POST /vapi-webhook            – record tool-call answers into Supabase
"""
from __future__ import annotations

import hashlib
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.core.supabase_db import get_supabase

router = APIRouter(tags=["vapi"])


# ── Helpers ───────────────────────────────────────────────────────────

def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


def _get_active_template() -> Optional[Dict]:
    resp = (
        get_supabase()
        .table("survey_templates")
        .select("id, version, questions, system_prompt")
        .eq("is_active", True)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    return data[0] if data else None


def _format_questions_for_voice(questions: List[Dict[str, Any]]) -> str:
    """
    Format 3 selected questions into the block that replaces {{QUESTIONS}}.
    Each line is written so Emma can read it naturally over voice.
    """
    lines: List[str] = []
    for idx, q in enumerate(questions, start=1):
        q_type = q.get("type", "open")
        text = q.get("Q", "").strip()
        q_id = q.get("id", f"q{idx}")
        answers: List[str] = [str(a) for a in (q.get("A") or [])]

        if q_type in ("mcq", "boolean") and answers:
            options = ", ".join(answers)
            lines.append(f'{idx}. [id={q_id}] {text} Options: {options}')
        elif q_type == "multi_select" and answers:
            options = ", ".join(answers)
            lines.append(f'{idx}. [id={q_id}] {text} They may choose multiple. Options: {options}')
        elif q_type == "scale" and answers:
            scale = " / ".join(answers)
            lines.append(f'{idx}. [id={q_id}] {text} Scale: {scale}')
        else:
            lines.append(f'{idx}. [id={q_id}] {text}')

    return "\n".join(lines)


def _upsert_response(call_id: str, patient_id: str, new_answer: Dict) -> None:
    sb = get_supabase()
    existing = (
        sb.table("patient_responses")
        .select("id, answers")
        .eq("call_id", call_id)
        .limit(1)
        .execute()
    )
    rows = existing.data or []
    if rows:
        row = rows[0]
        updated = list(row.get("answers") or []) + [new_answer]
        sb.table("patient_responses").update({"answers": updated}).eq(
            "id", row["id"]
        ).execute()
    else:
        sb.table("patient_responses").insert({
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "call_id": call_id,
            "answers": [new_answer],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()


# ── Patient login ─────────────────────────────────────────────────────

class PatientVerifyPayload(BaseModel):
    patient_id: str
    pin: str


@router.post("/patient/verify")
def verify_patient(payload: PatientVerifyPayload):
    resp = (
        get_supabase()
        .table("patients")
        .select("patient_id, name, pin_hash")
        .eq("patient_id", payload.patient_id)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    if not data or data[0].get("pin_hash") != _hash_pin(payload.pin):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials.")

    return {
        "success": True,
        "patient": {"patient_id": data[0]["patient_id"], "name": data[0]["name"]},
    }


# ── Start session ─────────────────────────────────────────────────────

@router.get("/start-session/{patient_id}")
def start_session(patient_id: str):
    """
    Returns Vapi assistantOverrides with:
    - stored system prompt (system_prompt from template), {{QUESTIONS}} replaced
      with 3 randomly selected questions formatted for voice
    - record_answer tool definition
    - endCall tool
    Zero LLM calls at runtime.
    """
    if not settings.vapi_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="VAPI_API_KEY not configured.",
        )

    template = _get_active_template()
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active template. Upload a PDF and save a template in the admin UI.",
        )

    all_questions: List[Dict[str, Any]] = template.get("questions") or []
    if not all_questions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Active template has no questions.",
        )

    system_prompt_template: str = template.get("system_prompt") or ""
    if not system_prompt_template:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Active template has no system prompt. Re-upload the PDF in the admin UI.",
        )

    if "{{QUESTIONS}}" not in system_prompt_template:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="System prompt missing {{QUESTIONS}} placeholder. Regenerate it in the admin UI.",
        )

    # Pick 3 random questions
    selected = random.sample(all_questions, min(3, len(all_questions)))

    # Build the questions block and inject into the stored system prompt
    questions_block = _format_questions_for_voice(selected)
    final_system_prompt = system_prompt_template.replace("{{QUESTIONS}}", questions_block)

    overrides: Dict[str, Any] = {
        "assistantOverrides": {
            "model": {
                "provider": "openai",
                "model": "gpt-4o-mini",     # cheaper model is fine for structured interviewing
                "messages": [{"role": "system", "content": final_system_prompt}],
                "tools": [
                    {
                        "type": "function",
                        "function": {
                            "name": "record_answer",
                            "description": "Record the patient's answer to one survey question.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "question_id": {
                                        "type": "string",
                                        "description": "The question id, e.g. q42",
                                    },
                                    "patient_answer": {
                                        "type": "string",
                                        "description": "Patient's verbatim answer",
                                    },
                                },
                                "required": ["question_id", "patient_answer"],
                            },
                        },
                    }
                ],
            },
            "tools:append": [{"type": "endCall"}],
            "endCallMessage": "Thank you for your time. Your check-in is complete. Goodbye!",
            "stopSpeakingPlan": {"numWords": 0, "voiceSeconds": 0.2, "backoffSeconds": 1},
            "metadata": {"patientId": patient_id},
        },
        "vapiApiKey": settings.vapi_api_key,
    }

    if settings.vapi_assistant_id:
        overrides["assistantId"] = settings.vapi_assistant_id

    if settings.vapi_server_url:
        overrides["assistantOverrides"]["serverUrl"] = settings.vapi_server_url

    return {"success": True, "data": overrides}


# ── Vapi webhook ──────────────────────────────────────────────────────

@router.post("/vapi-webhook")
async def vapi_webhook(request: Request):
    body = await request.json()
    message = body.get("message", {})

    if message.get("type") != "tool-calls":
        return {"success": True, "message": "Ignored."}

    tool_calls = message.get("toolCalls") or message.get("toolCallList") or []
    results: List[Dict] = []

    for tc in tool_calls:
        func = tc.get("function", {})
        tc_id = tc.get("id")

        if func.get("name") != "record_answer":
            results.append({"toolCallId": tc_id, "result": "Unknown function."})
            continue

        args = func.get("arguments", {})
        call_id = message.get("call", {}).get("id")
        patient_id = (
            message.get("call", {})
            .get("assistantOverrides", {})
            .get("metadata", {})
            .get("patientId", "unknown")
        )

        if not call_id:
            results.append({"toolCallId": tc_id, "result": "Missing call_id."})
            continue

        try:
            _upsert_response(
                call_id=call_id,
                patient_id=patient_id,
                new_answer={
                    "question_id": args.get("question_id"),
                    "answer": args.get("patient_answer"),
                },
            )
            results.append({"toolCallId": tc_id, "result": "Recorded."})
        except Exception as exc:
            results.append({"toolCallId": tc_id, "result": f"Error: {exc}"})

    return {"results": results}
