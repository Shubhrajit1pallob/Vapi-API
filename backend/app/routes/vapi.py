from fastapi import APIRouter, HTTPException, Depends, status, Request
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from typing import Any, cast
from pydantic import BaseModel, Field

from backend.app.core.config import settings
from backend.app.core.pg_database import get_db
from backend.app.models.sql_models import SurveyTemplate, PatientResponse

router = APIRouter(tags=["vapi"])


class SurveyQuestionIn(BaseModel):
    """Input schema for one survey question."""

    id: str | None = Field(default=None, description="Stable question id, e.g. q1")
    type: str = Field(default="open", description="mcq | tf | open")
    Q: str = Field(..., min_length=1, description="Question text")
    A: list[Any] = Field(default_factory=list, description="Choices for mcq/tf; empty for open")


class SurveyTemplateCreatePayload(BaseModel):
    """Input schema for creating a new survey template in PostgreSQL."""

    questions: list[SurveyQuestionIn] = Field(..., min_length=1)
    version: int | None = Field(default=None, ge=1, description="Optional explicit template version")


# ---------------------------------------------------------------------------
# POST /survey-templates
#   Stores a new SurveyTemplate row in PostgreSQL from JSON payload.
# ---------------------------------------------------------------------------
@router.post("/survey-templates", status_code=status.HTTP_201_CREATED)
def create_survey_template(payload: SurveyTemplateCreatePayload, db: Session = Depends(get_db)):
    """Create and store a survey template in PostgreSQL."""

    latest = (
        db.query(SurveyTemplate)
        .order_by(SurveyTemplate.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1
    template_version = payload.version or next_version

    if payload.version is not None:
        existing = (
            db.query(SurveyTemplate)
            .filter(SurveyTemplate.version == payload.version)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Survey template version {payload.version} already exists.",
            )

    questions_payload = [q.model_dump(exclude_none=True) for q in payload.questions]

    template = SurveyTemplate(
        version=template_version,
        questions=questions_payload,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    return {
        "success": True,
        "message": "Survey template stored successfully.",
        "data": {
            "id": str(template.id),
            "version": template.version,
            "total_questions": len(template.questions),
            "created_at": template.created_at.isoformat(),
        },
    }


# ---------------------------------------------------------------------------
# GET /start-session/{patient_id}
#   Fetches the latest SurveyTemplate, builds a Vapi-compatible system prompt,
#   and returns assistantOverrides for the Vapi Web SDK.
# ---------------------------------------------------------------------------
@router.get("/start-session/{patient_id}")
def start_session(patient_id: str, db: Session = Depends(get_db)):
    """Return Vapi assistantOverrides with a system prompt built from the
    latest survey template questions."""

    if not settings.vapi_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Vapi API key is not configured on the server.",
        )

    # Grab the highest-version template
    template = (
        db.query(SurveyTemplate)
        .order_by(SurveyTemplate.version.desc())
        .first()
    )

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No survey template found. Please create one first.",
        )

    # Build numbered question lines for the system prompt
    raw_questions = template.questions or []
    questions = cast(list[dict[str, Any]], raw_questions)

    question_lines = []
    for idx, q in enumerate(questions, start=1):
        text = q.get("Q", "")
        q_type = q.get("type", "open")
        answers = q.get("A", [])

        if q_type == "mcq":
            choices = ", ".join(map(str, answers)) if isinstance(answers, list) else ""
            question_lines.append(f"{idx}. {text} (choices: {choices})")
        elif q_type == "tf":
            question_lines.append(f"{idx}. {text} (True or False)")
        else:
            question_lines.append(f"{idx}. {text}")

    questions_block = "\n".join(question_lines)

    system_prompt = (
        "You are Cameron, a friendly healthcare voice assistant conducting a survey. "
    "Speak slowly and be patient.\n\n"
    
    "## YOUR PROTOCOL:\n"
    "1. Ask the questions provided below one by one.\n"
    "2. IMPORTANT: After the patient provides an answer to a question, you MUST "
    "immediately call the 'record_answer' tool. Provide the 'question_id' and "
    "the 'patient_answer' in the tool call.\n"
    "3. Only after the tool has been called should you move to the next question.\n"
    "4. If the patient is confused, gently rephrase the question.\n\n"
    
    f"## QUESTIONS:\n{questions_block}\n\n"
    
    "## CALL ENDING:\n"
    "After the last question is recorded, ask the patient: 'Before we go, "
    "do you have any feedback on how this call went for you today?' "
    "Wait for their answer, then thank them and end the call."
    )

    overrides = {
        "assistantId": settings.vapi_assistant_id or None,
        "assistantOverrides": {
            "model": {
                "provider": "openai",
                "model": "gpt-5.2",
                "systemMessage": system_prompt,
            },
            "metadata": {
                "patientId": patient_id,
            },
        },
        "vapiApiKey": settings.vapi_api_key,
    }

    if settings.vapi_server_url:
        overrides["assistantOverrides"]["serverUrl"] = settings.vapi_server_url

    return {"success": True, "data": overrides}


# ---------------------------------------------------------------------------
# POST /vapi-webhook
#   Receives Vapi "Tool Call" payloads. When the function name is
#   "record_answer", it extracts question_id + patient_answer and upserts
#   them into the PatientResponse table.
# ---------------------------------------------------------------------------
@router.post("/vapi-webhook")
async def vapi_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle incoming Vapi server messages (tool calls)."""

    body = await request.json()

    # Vapi wraps tool calls inside a "message" object
    message = body.get("message", {})
    msg_type = message.get("type")

    # We only care about tool-calls requests
    if msg_type != "tool-calls":
        return {"success": True, "message": "Ignored - not a tool-calls message."}

    # tool_calls = message.get("toolCallList", [])
    tool_calls = message.get("toolCalls") or message.get("toolCallList") or []
    results = []

    for tool_call in tool_calls:
        func = tool_call.get("function", {})
        func_name = func.get("name")
        args = func.get("arguments", {})
        tool_call_id = tool_call.get("id")

        if func_name != "record_answer":
            results.append(
                {"toolCallId": tool_call_id, "result": "Unknown function."}
            )
            continue

        # Extract fields sent by the Vapi assistant
        question_id = args.get("question_id")
        patient_answer = args.get("patient_answer")
        call_id = message.get("call", {}).get("id")
        patient_id = (
            message.get("call", {})
            .get("assistantOverrides", {})
            .get("metadata", {})
            .get("patientId", "unknown")
        )

        if not call_id:
            results.append(
                {"toolCallId": tool_call_id, "result": "Missing call_id."}
            )
            continue

        # Upsert: find existing response for this call, or create one
        response_row = (
            db.query(PatientResponse)
            .filter(PatientResponse.call_id == call_id)
            .first()
        )

        new_answer = {"question_id": question_id, "answer": patient_answer}

        if response_row:
            # Append to the existing JSONB array
            if response_row.answers is None:
                response_row.answers = []
            
            # Create a new list to ensure the reference changes
            response_row.answers = list(response_row.answers) + [new_answer]
            
            # This tells SQLAlchemy "Hey, I actually changed this JSON!"
            flag_modified(response_row, "answers")
            # response_row.answers = response_row.answers + [new_answer]
        else:
            response_row = PatientResponse(
                patient_id=patient_id,
                call_id=call_id,
                answers=[new_answer],
            )
            db.add(response_row)

        db.commit()

        results.append(
            {
                "toolCallId": tool_call_id,
                "result": f"Recorded answer for {question_id}.",
            }
        )

    return {"results": results}
