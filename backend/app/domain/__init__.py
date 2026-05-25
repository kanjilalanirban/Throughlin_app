"""SQLAlchemy 2.0 domain models for the four primitives + supporting tables.

Re-export all model classes so Alembic's autogenerate can pick them up via
`target_metadata = Base.metadata` in alembic/env.py.
"""

from app.domain.base import Base
from app.domain.decisions import Decision
from app.domain.initiatives import Initiative
from app.domain.ingestion_runs import IngestionRun
from app.domain.people import Person, PersonInitiative
from app.domain.signals import Signal
from app.domain.audit_log import AuditLog

__all__ = [
    "Base",
    "Initiative",
    "Decision",
    "Person",
    "PersonInitiative",
    "Signal",
    "IngestionRun",
    "AuditLog",
]
