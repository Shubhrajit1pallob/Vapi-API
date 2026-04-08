"""
Supabase operations for the admin UI.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

_client: Optional[Client] = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", "")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")
        _client = create_client(url, key)
    return _client


# ── Survey Templates ──────────────────────────────────────────────────

def list_survey_templates() -> List[Dict]:
    resp = (
        get_client()
        .table("survey_templates")
        .select("id, version, name, is_active, created_at, system_prompt")
        .order("version", desc=True)
        .execute()
    )
    return resp.data or []


def get_active_template() -> Optional[Dict]:
    resp = (
        get_client()
        .table("survey_templates")
        .select("*")
        .eq("is_active", True)
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    return data[0] if data else None


def save_survey_template(
    name: str,
    questions: List[Dict[str, Any]],
    system_prompt: str,
    set_active: bool = True,
) -> Dict:
    """Insert new template with questions + system prompt. Returns created row."""
    client = get_client()

    resp = (
        client.table("survey_templates")
        .select("version")
        .order("version", desc=True)
        .limit(1)
        .execute()
    )
    existing = resp.data or []
    next_version = (existing[0]["version"] + 1) if existing else 1

    content_hash = hashlib.sha256(
        json.dumps(questions, sort_keys=True).encode()
    ).hexdigest()[:16]

    if set_active:
        client.table("survey_templates").update({"is_active": False}).neq(
            "id", "00000000-0000-0000-0000-000000000000"
        ).execute()

    row = {
        "id": str(uuid.uuid4()),
        "version": next_version,
        "name": name,
        "questions": questions,
        "system_prompt": system_prompt,
        "is_active": set_active,
        "content_hash": content_hash,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = client.table("survey_templates").insert(row).execute()
    return (resp.data or [{}])[0]


def update_system_prompt(template_id: str, system_prompt: str) -> None:
    """Update only the system_prompt of an existing template."""
    get_client().table("survey_templates").update(
        {"system_prompt": system_prompt}
    ).eq("id", template_id).execute()


def set_template_active(template_id: str) -> None:
    client = get_client()
    client.table("survey_templates").update({"is_active": False}).neq(
        "id", template_id
    ).execute()
    client.table("survey_templates").update({"is_active": True}).eq(
        "id", template_id
    ).execute()


# ── Patients ──────────────────────────────────────────────────────────

def _hash_pin(pin: str) -> str:
    return hashlib.sha256(pin.encode()).hexdigest()


def verify_patient(patient_id: str, pin: str) -> Optional[Dict]:
    resp = (
        get_client()
        .table("patients")
        .select("id, patient_id, name, pin_hash")
        .eq("patient_id", patient_id)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    if not data:
        return None
    patient = data[0]
    if patient.get("pin_hash") != _hash_pin(pin):
        return None
    return {"patient_id": patient["patient_id"], "name": patient["name"]}


def create_patient(patient_id: str, name: str) -> Dict:
    """Returns row + plain PIN (shown once only). Raises ValueError if ID exists."""
    client = get_client()
    existing = (
        client.table("patients").select("id").eq("patient_id", patient_id).execute()
    )
    if existing.data:
        raise ValueError(f"Patient ID '{patient_id}' already exists.")

    pin = f"{secrets.randbelow(10000):04d}"
    row = {
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "name": name,
        "pin_hash": _hash_pin(pin),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    resp = client.table("patients").insert(row).execute()
    return {**(resp.data or [{}])[0], "pin": pin}


def list_patients() -> List[Dict]:
    resp = (
        get_client()
        .table("patients")
        .select("id, patient_id, name, created_at")
        .order("created_at", desc=True)
        .execute()
    )
    return resp.data or []


def delete_patient(patient_id: str) -> None:
    get_client().table("patients").delete().eq("patient_id", patient_id).execute()


# ── Patient Responses ─────────────────────────────────────────────────

def list_patient_responses(patient_id: Optional[str] = None) -> List[Dict]:
    q = (
        get_client()
        .table("patient_responses")
        .select("id, patient_id, call_id, answers, created_at")
        .order("created_at", desc=True)
    )
    if patient_id:
        q = q.eq("patient_id", patient_id)
    return q.execute().data or []
