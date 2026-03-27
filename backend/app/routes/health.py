from fastapi import APIRouter, Depends
from datetime import datetime

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "VAPI - JSON Data Processing API",
        "version": "1.0.0",
        "docs": "/docs"
    }
