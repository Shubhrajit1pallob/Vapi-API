from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from pathlib import Path
from backend.app.core.database import connect_to_mongo, close_mongo_connection
from backend.app.core.pg_database import init_db
from backend.app.routes import health, data, vapi


# Lifespan context manager for startup and shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handle startup and shutdown events"""
    # Startup
    # connect_to_mongo()
    init_db()  # create PostgreSQL tables if they don't exist
    yield
    # Shutdown
    # close_mongo_connection()


# Create FastAPI application
app = FastAPI(
    title="VAPI - JSON Data Processing API",
    description="API for receiving, processing, and storing JSON data",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(data.router)
app.include_router(vapi.router)

# Serve the frontend
frontend_dir = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dir.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
