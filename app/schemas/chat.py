from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)

    @field_validator("message")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be empty")
        return value


class SourceRef(BaseModel):
    type: Literal["course", "instructor", "event", "plan"]
    label: str
    source: str | None = None  # where the data came from
    verified: bool = False


class ChatResponse(BaseModel):
    answer: str
    status: Literal["answered", "not_found", "needs_clarification", "unsupported"] = "answered"
    sources: list[SourceRef] = []
    data_verified: bool = True
