"""Compatibility exports for the modern course and grade workspaces.

The original inline CRUD pages were replaced by dedicated list/detail/edit screens.
"""

from .courses import CoursesPage as CoursePage
from .grades import GradesPage as GradePage

__all__ = ["CoursePage", "GradePage"]
