import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.university import University
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_router import answer_question

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/{domain}", response_model=ChatResponse)
async def ask(domain: str, request: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    """Answer a question about ONE university, chosen by its domain in the URL (e.g. gju.edu.jo).

    The university comes from the URL, never from the message text, and every lookup is
    restricted to it. This endpoint only reads public institutional data.
    """
    try:
        result = await db.execute(select(University).where(University.domain == domain.strip().lower()))
        university = result.scalars().first()
        if university is None:
            raise HTTPException(status_code=404, detail="Unknown university")
        return await answer_question(db, university.id, request.message)
    except (OSError, SQLAlchemyError):
        # Database not running or unreachable: answer cleanly instead of a 500 with a traceback.
        log.exception("database unavailable while answering a chat request")
        raise HTTPException(status_code=503, detail="The service is temporarily unavailable. Please try again soon.")
