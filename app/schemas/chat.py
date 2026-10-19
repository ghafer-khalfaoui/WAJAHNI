from pydantic import BaseModel

class ChatRequest(BaseModel):
    user_query: str
    university_id: int = 1  # Defaults to 1 so we can test easily

class ChatResponse(BaseModel):
    answer: str
    status: str = "success"