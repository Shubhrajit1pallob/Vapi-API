from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from backend.app.core.pg_database import init_db
from backend.app.routes import health, data, vapi


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create PostgreSQL tables if they don't exist (fallback)
    yield


app = FastAPI(
    title="SoLAr / Vapi API",
    description="Survey session management and Vapi webhook handler",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(data.router)
app.include_router(vapi.router)

# ── Patient Portal static assets (vapi.js bundle, etc.) ──────────────
_portal_static_dir = Path(__file__).parent.parent / "patient_portal"
if _portal_static_dir.exists():
    app.mount(
        "/portal-static",
        StaticFiles(directory=str(_portal_static_dir)),
        name="portal-static",
    )

# ── Patient Portal HTML ───────────────────────────────────────────────
_portal_html = Path(__file__).parent.parent / "patient_portal" / "index.html"


@app.get("/portal", response_class=HTMLResponse, include_in_schema=False)
def patient_portal():
    """Serve the patient-facing login + Vapi call portal."""
    if not _portal_html.exists():
        return HTMLResponse("<h1>Patient portal not found.</h1>", status_code=404)
    return HTMLResponse(content=_portal_html.read_text(encoding="utf-8"))


# ── Serve built frontend (if dist/ exists) ────────────────────────────
_frontend_dir = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dir.exists():
    app.mount(
        "/app",
        StaticFiles(directory=str(_frontend_dir), html=True),
        name="frontend",
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
