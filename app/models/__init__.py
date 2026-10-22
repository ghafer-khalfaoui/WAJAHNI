"""Import every model so SQLAlchemy can resolve relationships by name.

Without this, a script that imports only `University` fails with
"expression 'Document' failed to locate a name".
"""
from app.models.academic import AcademicEvent, Course, CoursePrerequisite, Instructor
from app.models.document import Document, DocumentChunk
from app.models.student import Student
from app.models.university import AdminUser, University

__all__ = [
    "AcademicEvent", "AdminUser", "Course", "CoursePrerequisite", "Document", "DocumentChunk",
    "Instructor", "Student", "University",
]
