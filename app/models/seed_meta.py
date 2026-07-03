"""
Seed metadata — records which dataset (and version) the database was
seeded with, so the seeder can wipe and reseed automatically when the
deployed seed data changes.
"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from ..database import Base


class SeedMeta(Base):
    __tablename__ = "seed_meta"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(255), nullable=False)
