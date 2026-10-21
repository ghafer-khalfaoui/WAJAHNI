from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.models.base import WajahniBaseModel


class Document(WajahniBaseModel):
    """A source document for one university. Table `documents` (migration 8770692a9cc5)."""

    __tablename__ = "documents"

    university_id = Column(
        Integer, ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title = Column(String(255), nullable=False)
    source_url = Column(String(500), nullable=True)

    university = relationship("University", back_populates="documents")
    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(WajahniBaseModel):
    """A searchable passage. Table `documentchunks`.

    `university_id` is copied from the parent document so every search can be
    restricted to one tenant (made NOT NULL by migration a3c5e7f91b24).
    """

    __tablename__ = "documentchunks"

    document_id = Column(
        Integer, ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False
    )
    university_id = Column(
        Integer, ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content = Column(Text, nullable=False)
    embedding = Column(Vector(768), nullable=False)

    document = relationship("Document", back_populates="chunks")
