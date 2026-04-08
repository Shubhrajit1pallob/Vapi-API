from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings — loaded from .env"""

    # PostgreSQL (fallback / legacy)
    database_url: str = "postgresql://postgres:postgres@localhost:5432/vapi_db"

    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""           # anon/publishable — not used server-side
    supabase_service_key: str = ""   # service role — backend only, bypasses RLS

    # Anthropic
    anthropic_api_key: str = ""

    # Vapi
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""
    vapi_server_url: str = ""

    # Legacy / misc
    api_key: str = "your-default-api-key-change-in-production"
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "vapi_db"
    admin_port: int = 7860

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"   # silently ignore any unknown keys in .env


settings = Settings()
