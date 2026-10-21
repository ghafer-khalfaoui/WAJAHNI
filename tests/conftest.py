import os
import sys
from pathlib import Path

# Dummy settings so tests never need a real .env, database, or API key.
os.environ.update(
    JWT_SECRET_KEY="test-secret-not-real-0123456789abcdef-0123456789",
    POSTGRES_USER="u",
    POSTGRES_PASSWORD="p",
    POSTGRES_HOST="localhost",
    POSTGRES_PORT="5432",
    POSTGRES_DB="d",
    DATABASE_ASYNC_URL="postgresql+asyncpg://u:p@localhost:5432/d",
    GEMINI_API_KEY="dummy-not-real",
)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
