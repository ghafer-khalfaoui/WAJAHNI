from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm import declared_attr
from app.core.database import Base

class WajahniBaseModel(Base):
    """
    Abstract declarative base class acting as the master relational matrix.
    Injects mandatory structural audit trails and enables multi-tenant isolation.
    """
    __abstract__ = True

    @declared_attr
    def __tablename__(cls) -> str:
        """
        Dynamically infers and applies relational table names using pluralized lower-case naming.
        """
        name = cls.__name__.lower()
        if name.endswith("y"):
            return f"{name[:-1]}ies"
        elif name.endswith("s"):
            return f"{name}es"
        return f"{name}s"

    # Core Sequential Identity Boundary
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # Global Multi-Tenant Partition Key
    # Crucial for enforcing multi-tenant isolation walls across the database cluster
    university_id = Column(
        Integer, 
        index=True, 
        nullable=True,  # Set to True only for truly global application lookup matrices
        comment="Multi-tenant tenant partition identifier."
    )

    # Declarative Temporal Auditing Ledger Fields
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Cryptographic audit record generation timestamp."
    )
    
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
        comment="Timestamp tracking data entry alteration vectors."
    )