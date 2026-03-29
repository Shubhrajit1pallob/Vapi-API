from fastapi import APIRouter, HTTPException, Depends, status, Request
from sqlalchemy.orm import Session
from typing import Any, cast

from backend.app.core.config import settings
from backend.app.core.pg_database import get_db
from backend.app.models.sql_models import SurveyTemplate, PatientResponse

router = APIRouter(tags=["vapi"])


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
        "You are a friendly, patient, and supportive healthcare assistant "
        "conducting a well-being survey. The patient may have "
        "cognitive difficulties, so speak slowly, use simple language, and "
        "be encouraging.\n\n"
        "Ask the following questions one at a time. Wait for the patient's "
        "answer before moving to the next question. If the patient seems "
        "confused, gently rephrase the question.\n\n"
        f"Questions:\n{questions_block}\n\n"
        "After all questions are answered, thank the patient warmly and "
        "let them know the survey is complete."
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
        return {"success": True, "message": "Ignored – not a tool-calls message."}

    tool_calls = message.get("toolCallList", [])
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
            response_row.answers = response_row.answers + [new_answer]
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
