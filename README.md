# VAPI Survey API

FastAPI backend + Vite frontend for voice-based patient check-ins using Vapi.

This project currently includes:

- MongoDB-backed APIs for storing question sets and submitted answers.
- PostgreSQL-backed APIs for survey templates and Vapi call answer ingestion.
- A frontend client using `@vapi-ai/web`.

## Project Structure

```text
vapi_dev/
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   └── app/
│       ├── core/
│       │   ├── config.py
│       │   ├── database.py
│       │   ├── pg_database.py
│       │   └── security.py
│       ├── models/
│       │   ├── mongoDB_schemas.py
│       │   └── sql_models.py
│       └── routes/
│           ├── health.py
│           ├── data.py
│           └── vapi.py
├── frontend/
│   ├── index.html
│   ├── main.js
│   ├── style.css
│   ├── package.json
│   └── vite.config.js
├── Terraform/
└── README.md
```

## Prerequisites

- Python 3.10+
- Node.js 18+
- PostgreSQL 14+
- MongoDB 6+ (required for `/api/questions` and `/api/answers` routes)

## Backend Setup

1. Create and activate a virtual environment:

```bash
cd vapi_dev
python3 -m venv .venv
source .venv/bin/activate
```

2. Install backend dependencies:

```bash
pip install -r backend/requirements.txt
```

3. Create a `.env` file in the project root (`vapi_dev/.env`) and configure values:

```env
# MongoDB
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=vapi_db

# PostgreSQL
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/vapi_db

# API security
API_KEY=change-this-in-production

# Vapi
VAPI_API_KEY=
VAPI_ASSISTANT_ID=
VAPI_PHONE_NUMBER_ID=
VAPI_SERVER_URL=
```

4. Run the backend:

```bash
python -m backend.main
```

Backend runs on `http://localhost:8000` by default.

## Frontend Setup

1. Install frontend dependencies:

```bash
cd frontend
npm install
```

2. Run frontend dev server:

```bash
npm run dev
```

Vite runs on `http://localhost:3000` by default.

## API Docs

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## API Endpoints

### Health

- `GET /` - basic service metadata
- `GET /health` - health check

### Questions and Answers (MongoDB + API key)

All routes below require `X-API-Key` header.

- `POST /api/questions` - store parsed question list
- `GET /api/questions?limit=10&skip=0` - list question documents
- `GET /api/questions/{question_id}` - get one question document
- `DELETE /api/questions/{question_id}` - delete question document
- `POST /api/answers` - store a session's answers
- `GET /api/answers?limit=10&skip=0` - list answers
- `GET /api/answers/{answer_id}` - get one answer document
- `DELETE /api/answers/{answer_id}` - delete answer document

### Vapi Integration (PostgreSQL)

- `GET /start-session/{patient_id}`
  - returns Vapi launch config (`vapiApiKey`, `assistantId`, `assistantOverrides`) generated from latest `survey_templates` record.
- `POST /vapi-webhook`
  - receives Vapi tool-call payloads and records `record_answer` outputs into `patient_responses`.

## Quick cURL Examples

### Health check

```bash
curl http://localhost:8000/health
```

### Create questions

```bash
curl -X POST "http://localhost:8000/api/questions" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: change-this-in-production" \
  -d '{
    "questions": [
      {"type": "mcq", "Q": "How are you today?", "A": ["Good", "Okay", "Not great"]},
      {"type": "open", "Q": "Anything else to share?", "A": []}
    ],
    "metadata": {"source": "intake-form"}
  }'
```

### Get Vapi session config

```bash
curl "http://localhost:8000/start-session/patient-123"
```

## Notes and Known Gaps

- In `backend/main.py`, MongoDB connect/disconnect calls are currently commented out. If you use `/api/questions` or `/api/answers`, ensure MongoDB is initialized in startup (or re-enable those calls).
- Frontend currently proxies `/get-vapi-config`, while backend exposes `/start-session/{patient_id}`. Align either the frontend fetch path or backend route naming before full end-to-end use.
- CORS currently allows `*`; lock this down for production.

## Production Hardening Checklist

- Use strong secrets for `API_KEY` and Vapi credentials.
- Restrict CORS origins and methods.
- Put backend behind HTTPS.
- Add request validation/rate-limiting for public-facing endpoints.
- Add logging/monitoring around webhook handling.

## License

Add your license information here.
