from pydantic import BaseModel
from typing import Optional

class DocumentIngestRequest(BaseModel):
    university_id: int
    title: str
    content: str
    source_url: Optional[str] = None

class DocumentIngestResponse(BaseModel):
    document_id: int
    status: str = "success"
    message: str