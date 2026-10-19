import os
from typing import Literal
from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Validates environment configurations at system boot.
    Implements a strict fail-fast operational architecture pattern.
    """
    # System Operational Mode
    ENV_MODE: Literal["development", "production", "testing"] = "development"
    PROJECT_NAME: str = "Wajahni"
    
    # Cryptographic Configuration Boundary
    JWT_SECRET_KEY: str = Field(..., description="High-entropy key for signing token payloads.")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Relational Multi-Tenant Storage Connection Parameters
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    DATABASE_ASYNC_URL: str
    
    # External Cognitive Orchestration Gateway
    GEMINI_API_KEY: str
    
    # Pydantic Configuration Sub-Object Setup
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Discards unexpected environment mutations gracefully
        case_sensitive=True
    )

# Instantiate a single immutable global reference state
settings = Settings()