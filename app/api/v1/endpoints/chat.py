from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.chat import ChatRequest, ChatResponse
from app.core.database import get_db

router = APIRouter()

@router.post("/", response_model=ChatResponse)
async def process_chat_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Primary ingestion endpoint for the Layered Thinking Engine.
    Validates payload, injects DB session, and triggers the AI Router.
    """
    # -------------------------------------------------------------------------
    # PHASE 3 STUB: The Layered Thinking Engine (Multi-Agent Router) will go here.
    # For now, we return a strict mock matching our schema contract to verify the I/O pipeline.
    # -------------------------------------------------------------------------
    
    return ChatResponse(
        response=f"Message received: '{request.message}'. The Wajahni Agent Swarm is currently compiling.",
        confidence_score=100,
        reasoning_steps=[
            "Intercepted request at API Gateway.",
            "Validated payload structure via Pydantic.",
            "Injected isolated PostgreSQL transactional context.",
            "Generated static structural response."
        ],
        ui_shift=None
    )