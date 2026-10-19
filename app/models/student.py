from sqlalchemy import Column, String, Numeric, Integer, JSON, ForeignKey
from app.models.base import WajahniBaseModel

class Student(WajahniBaseModel):
    """
    Core persistent memory matrix for individual student entities.
    Eliminates conversational amnesia by maintaining an immutable academic state.
    """
    # Identity & Cryptographic Authentication
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False, comment="Strictly bcrypt hashed, never plaintext.")
    full_name = Column(String(150), nullable=False)
    
    # Relational Tie to the Institutional Tenant
    # Notice this overrides the abstract definition to enforce a strict Foreign Key constraint
    university_id = Column(Integer, ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False)

    # Academic State Engine
    major = Column(String(150), nullable=True, comment="e.g., Computer Science - Cyber Security")
    current_gpa = Column(Numeric(4, 2), nullable=True, comment="Tracks exact GPA, e.g., 81.70 or 3.85")
    total_credits_completed = Column(Integer, default=0, nullable=False)
    
    # Adaptive Logistical Targets (Drives Feature 20 - Life Copilot)
    target_country = Column(String(100), nullable=True, comment="Target for exchange semester or career")
    language_proficiency = Column(JSON, default=dict, comment="Tracks levels, e.g., {'German': 'B2', 'English': 'C1'}")
    
    # High-Velocity Course Memory
    completed_courses = Column(JSON, default=list, comment="Array of completed course codes for fast AI context injection")