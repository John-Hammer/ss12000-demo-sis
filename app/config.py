"""
Configuration settings for Fake SIS using Pydantic BaseSettings.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/fake_sis.db"

    # JWT Authentication
    jwt_secret: str = "dev-jwt-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # Demo credentials
    demo_client_id: str = "skolskold_demo"
    demo_client_secret: str = "demo_secret_123"

    # API Settings
    api_title: str = "Fake SIS - SS12000 v2.1"
    api_description: str = "Demo School Information System implementing SS12000 standard"
    api_version: str = "2.1.0"

    # Server
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
