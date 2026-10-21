from sqlalchemy import JSON, Column, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.models.base import WajahniBaseModel


class University(WajahniBaseModel):
    """One tenant. Matches the `universities` table created by migration f9d17912649f."""

    __tablename__ = "universities"

    name = Column(String(150), nullable=False, unique=True)
    domain = Column(String(100), nullable=False, unique=True)  # e.g. "gju.edu.jo"
    primary_color = Column(String(7), nullable=False, default="#003366")
    secondary_color = Column(String(7), nullable=False, default="#e6f2ff")
    logo_url = Column(String(255), nullable=True)
    suggestion_chips = Column(JSON, nullable=False, default=list)

    documents = relationship("Document", back_populates="university", cascade="all, delete-orphan")
    admins = relationship("AdminUser", back_populates="university", cascade="all, delete-orphan")


class AdminUser(WajahniBaseModel):
    """University administrator. Created by migration a3c5e7f91b24."""

    __tablename__ = "admin_users"

    university_id = Column(
        Integer, ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False
    )
    username = Column(String(100), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)

    university = relationship("University", back_populates="admins")
