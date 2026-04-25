"""
app/models/__init__.py — Import all models so Alembic can detect them.

These imports are intentional re-exports (noqa: F401).
Alembic's env.py imports this module to ensure all tables are registered
in Base.metadata before running autogenerate.
"""

from app.models.organization import Organization  # noqa: F401
from app.models.user import User  # noqa: F401
from app.models.household import Household  # noqa: F401
from app.models.person import Person  # noqa: F401
from app.models.case import Case, CasePerson  # noqa: F401
from app.models.volunteer import Volunteer, VolunteerAvailability  # noqa: F401
from app.models.assignment import Assignment  # noqa: F401
from app.models.inventory import InventoryItem, StockMovement  # noqa: F401
from app.models.upload import Upload, AIExtractionResult  # noqa: F401
from app.models.alert import Alert  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.report import ReportJob  # noqa: F401
from app.models.form_template import FormTemplate  # noqa: F401

__all__ = [
    "Organization",
    "User",
    "Household",
    "Person",
    "Case",
    "CasePerson",
    "Volunteer",
    "VolunteerAvailability",
    "Assignment",
    "InventoryItem",
    "StockMovement",
    "Upload",
    "AIExtractionResult",
    "Alert",
    "AuditLog",
    "ReportJob",
    "FormTemplate",
]
