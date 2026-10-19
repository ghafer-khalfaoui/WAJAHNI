from fastapi import APIRouter
from app.api.v1.endpoints import chat

# Aggregates all v1 API routes into a single master router
api_router = APIRouter()

# Attach the chat endpoint
api_router.include_router(chat.router, prefix="/chat", tags=["Wajahni AI Router"])