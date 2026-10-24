from sqlalchemy import JSON, Boolean, CheckConstraint, Column, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship

from app.models.base import WajahniBaseModel


def _university_fk() -> Column:
    return Column(Integer, ForeignKey("universities.id", ondelete="CASCADE"), index=True, nullable=False)


class Course(WajahniBaseModel):
    """A course offered by one university. `verified` stays False until checked against an official source."""

    __tablename__ = "courses"
    __table_args__ = (UniqueConstraint("university_id", "code", name="uq_courses_university_code"),)

    university_id = _university_fk()
    code = Column(String(20), nullable=False)
    name = Column(String(255), nullable=False)
    credit_hours = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    plan_groups = Column(JSON, nullable=True)  # e.g. ["program-common"], ["track-cybersecurity"]
    prerequisite_note = Column(Text, nullable=True)  # non-course conditions, e.g. "Placement test"
    source = Column(String(255), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)


class CoursePrerequisite(WajahniBaseModel):
    __tablename__ = "course_prerequisites"
    __table_args__ = (
        UniqueConstraint("course_id", "prerequisite_id", name="uq_course_prerequisite_pair"),
        CheckConstraint("course_id <> prerequisite_id", name="ck_course_not_own_prerequisite"),
    )

    university_id = _university_fk()
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False)
    prerequisite_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False)
    corequisite = Column(Boolean, nullable=False, default=False)  # may be taken at the same time
    alt_group = Column(Integer, nullable=True)  # rows of one course sharing a number: any ONE of them is enough
    source = Column(String(255), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)

    course = relationship("Course", foreign_keys=[course_id])
    prerequisite = relationship("Course", foreign_keys=[prerequisite_id])


class Instructor(WajahniBaseModel):
    """Staff directory entry (contact details come from the university)."""

    __tablename__ = "instructors"
    __table_args__ = (UniqueConstraint("university_id", "email", name="uq_instructors_university_email"),)

    university_id = _university_fk()
    name = Column(String(150), nullable=False, index=True)
    title = Column(String(150), nullable=True)
    office_location = Column(String(50), nullable=True)
    phone = Column(String(60), nullable=True)
    email = Column(String(255), nullable=False)
    status = Column(String(30), nullable=True)  # e.g. "on leave"
    source = Column(String(255), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)


class AcademicEvent(WajahniBaseModel):
    """A dated entry of the official academic calendar (registration, exams, holidays...)."""

    __tablename__ = "academic_events"
    __table_args__ = (
        UniqueConstraint("university_id", "semester", "start_date", "title", name="uq_academic_events_entry"),
        CheckConstraint("end_date >= start_date", name="ck_academic_event_dates"),
    )

    university_id = _university_fk()
    semester = Column(String(20), nullable=False)  # "first", "second" or "summer"
    start_date = Column(Date, nullable=False, index=True)
    end_date = Column(Date, nullable=False)
    title = Column(String(255), nullable=False)
    source = Column(String(255), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)
