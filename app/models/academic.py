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


class Program(WajahniBaseModel):
    """A degree program (or its dual-study variant) with one version of its official study plan."""

    __tablename__ = "programs"
    __table_args__ = (UniqueConstraint("university_id", "code", name="uq_programs_university_code"),)

    university_id = _university_fk()
    code = Column(String(60), nullable=False)  # short unique slug, e.g. "cs", "cs-dual", "nursing"
    name = Column(String(255), nullable=False)  # e.g. "Computer Science"
    school = Column(String(120), nullable=True)  # e.g. "School of Computing"
    degree = Column(String(30), nullable=True)  # e.g. "B.Sc."
    plan_version = Column(String(30), nullable=True)  # e.g. "2023-2024"
    kind = Column(String(20), nullable=False, default="regular")  # "regular" or "dual"
    source = Column(String(255), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)


class ProgramCourse(WajahniBaseModel):
    """Which requirement table of a program a course belongs to (the same course can be in many programs)."""

    __tablename__ = "program_courses"
    __table_args__ = (
        UniqueConstraint("program_id", "course_id", "group_title", name="uq_program_courses_entry"),
    )

    university_id = _university_fk()
    program_id = Column(Integer, ForeignKey("programs.id", ondelete="CASCADE"), index=True, nullable=False)
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), index=True, nullable=False)
    group_title = Column(String(255), nullable=False)  # the table heading, e.g. "Program Requirements (Compulsory)"
    scope = Column(String(20), nullable=True)  # "admission", "university", "school" or "program"
    kind = Column(String(20), nullable=False)  # "compulsory", "elective" or "remedial"
    track = Column(String(80), nullable=True)  # track slug when the table belongs to one track
    source = Column(String(255), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)

    program = relationship("Program", foreign_keys=[program_id])
    course = relationship("Course", foreign_keys=[course_id])


class PlanEntry(WajahniBaseModel):
    """One slot of a study-plan guide: which course (or elective placeholder) sits in which year and
    semester of which track of which program. A course may sit in different semesters on different tracks."""

    __tablename__ = "plan_entries"
    __table_args__ = (
        UniqueConstraint("university_id", "program_id", "track", "year", "semester", "position",
                         name="uq_plan_entries_slot"),
        CheckConstraint("course_id IS NOT NULL OR label IS NOT NULL", name="ck_plan_entry_has_content"),
    )

    university_id = _university_fk()
    program_id = Column(Integer, ForeignKey("programs.id", ondelete="CASCADE"), index=True, nullable=True)
    track = Column(String(80), nullable=False)  # "general", "cybersecurity"... or "all" when the program has no tracks
    year = Column(Integer, nullable=False)
    semester = Column(String(20), nullable=False)  # "first", "second" or "summer"
    position = Column(Integer, nullable=False)  # order inside the semester table
    course_id = Column(Integer, ForeignKey("courses.id", ondelete="CASCADE"), nullable=True)
    label = Column(String(100), nullable=True)  # e.g. "University Elective" when there is no course
    credit_hours = Column(Integer, nullable=False)
    source = Column(String(255), nullable=True)
    verified = Column(Boolean, nullable=False, default=False)

    program = relationship("Program", foreign_keys=[program_id])
    course = relationship("Course", foreign_keys=[course_id])
