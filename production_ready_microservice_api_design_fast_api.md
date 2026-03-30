# Production-Ready Microservice API Design (FastAPI)

## Overview
This document outlines how to design a production-grade microservice API using FastAPI. It incorporates best practices for versioning, authentication, authorization, validation, structure, and security.

---

## 1. API Versioning

### Why Versioning?
- Prevents breaking existing clients
- Allows iterative improvements
- Supports backward compatibility

### Recommended Pattern
```
/api/v1/survey-templates
```

### Example Endpoints
- POST /api/v1/survey-templates
- GET /api/v1/survey-templates/{id}
- GET /api/v1/survey-templates?version=2

---

## 2. Authentication (JWT)

### Approach
Use Bearer Token Authentication with JWT.

### Example
```
Authorization: Bearer <token>
```

### FastAPI Dependency
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer

security = HTTPBearer()

def get_current_user(token=Depends(security)):
    if token.credentials != "valid-token":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return {"user_id": "123", "role": "admin"}
```

---

## 3. Authorization (RBAC)

### Role-Based Access Control
```python
def require_admin(user=Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Forbidden")
    return user
```

---

## 4. Data Validation (Pydantic)

### Strict Schema
```python
from pydantic import BaseModel, Field
from typing import Literal

class SurveyQuestionIn(BaseModel):
    id: str | None = None
    type: Literal["mcq", "tf", "open"] = "open"
    Q: str = Field(..., min_length=1, max_length=500)
    A: list[str] = Field(default_factory=list)
```

### Custom Validation
```python
from pydantic import model_validator

class SurveyQuestionIn(BaseModel):
    ...

    @model_validator(mode="after")
    def validate_answers(self):
        if self.type in ["mcq", "tf"] and len(self.A) < 2:
            raise ValueError("MCQ/TF must have at least 2 options")
        if self.type == "open" and self.A:
            raise ValueError("Open questions should not have answers")
        return self
```

---

## 5. Response Models

### Define Output Schema
```python
class SurveyTemplateResponse(BaseModel):
    id: str
    version: int
    total_questions: int
    created_at: str
```

---

## 6. Clean Project Structure

```
backend/
├── app/
│   ├── api/
│   │   └── v1/
│   │       └── survey.py
│   ├── core/
│   │   ├── auth.py
│   │   └── config.py
│   ├── models/
│   ├── schemas/
│   ├── db/
│   └── services/
```

---

## 7. Service Layer Pattern

### Business Logic Separation
```python
def create_template(db, payload):
    latest = db.query(SurveyTemplate).order_by(SurveyTemplate.version.desc()).first()
    next_version = (latest.version + 1) if latest else 1

    version = payload.version or next_version

    template = SurveyTemplate(
        version=version,
        questions=[q.model_dump() for q in payload.questions]
    )

    db.add(template)
    db.commit()
    db.refresh(template)

    return template
```

---

## 8. Route Implementation

```python
@router.post("", response_model=SurveyTemplateResponse, status_code=201)
def create_survey_template(
    payload: SurveyTemplateCreatePayload,
    db: Session = Depends(get_db),
    user = Depends(require_admin)
):
    template = create_template(db, payload)

    return SurveyTemplateResponse(
        id=str(template.id),
        version=template.version,
        total_questions=len(template.questions),
        created_at=template.created_at.isoformat()
    )
```

---

## 9. Security Best Practices

- Use HTTPS only
- Validate all inputs
- Implement authentication and RBAC
- Avoid hardcoding secrets
- Use environment variables

---

## 10. Observability

### Logging
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Creating survey template")
```

### Metrics & Monitoring
- Prometheus
- Grafana

### Tracing
- OpenTelemetry

---

## 11. Rate Limiting

- Use Redis-based rate limiting
- Protect endpoints from abuse

---

## 12. Future Enhancements

- Pagination for GET endpoints
- Soft deletes
- Audit logs
- API gateway integration
- CI/CD pipelines

---

## Summary

A production-ready microservice API should include:
- Versioned endpoints
- Secure authentication and authorization
- Strong validation
- Clean architecture (routes + services)
- Observability and logging
- Scalability and security practices

---

This design can be extended with containerization (Docker), orchestration (Kubernetes), and infrastructure as code (Terraform) for a complete DevSecOps pipeline.

