"""Deletion tracking for /deletedEntities (SS12000 incremental sync).

The demo dataset is static, so rows only appear here if something
deletes entities at runtime (admin UI) — but the ENDPOINT contract
exists so clients can build and test their incremental-sync path.
"""
from datetime import datetime, timezone

from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class DeletedEntity(Base):
    __tablename__ = "deleted_entities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entity_type: Mapped[str] = mapped_column(String(50))   # Person, Group, Duty, ...
    entity_id: Mapped[str] = mapped_column(String(36))
    deleted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        return {
            "entityType": self.entity_type,
            "id": self.entity_id,
            "deletedAt": self.deleted_at.isoformat(),
        }
