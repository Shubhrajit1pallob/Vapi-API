from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # MongoDB Configuration (kept for legacy routes)
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "vapi_db"

    # PostgreSQL Configuration
    database_url: str = "postgresql://postgres:postgres@localhost:5432/vapi_db"
    
    # API Key Configuration
    api_key: str = "your-default-api-key-change-in-production"
    
    # Vapi Configuration
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""
    vapi_phone_number_id: str = ""
    vapi_server_url: str = ""
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
