"""
SS12000 Organisation model.
Represents schools, school units, and the organisational hierarchy.
"""
from datetime import datetime, date
from typing import Optional
from uuid import uuid4
from sqlalchemy import String, ForeignKey, DateTime, Date, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class Organisation(Base):
    """
    SS12000 Organisation entity.
    Represents: Huvudman, Skola, Skolenhet, etc.
    """
    __tablename__ = "organisations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Required fields
    display_name: Mapped[str] = mapped_column(String(255))
    organisation_type: Mapped[str] = mapped_column(String(50))  # OrganisationType enum value

    # Optional fields
    organisation_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    organisation_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Org nr (SE)
    school_unit_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Skolenhetskod
    municipality_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    # Contact info
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Address (simplified - could be a separate table)
    street_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    locality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Validity period
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # Parent organisation (self-referential)
    parent_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("organisations.id"), nullable=True)
    parent: Mapped[Optional["Organisation"]] = relationship("Organisation", remote_side=[id], backref="children")

    # School types (stored as comma-separated for simplicity)
    school_types: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    def to_dict(self, expand_references: bool = False) -> dict:
        """Convert to SS12000 API response format."""
        result = {
            "id": self.id,
            "meta": {
                "created": self.created_at.isoformat(),
                "modified": self.modified_at.isoformat(),
            },
            "displayName": self.display_name,
            "organisationType": self.organisation_type,
        }

        if self.organisation_code:
            result["organisationCode"] = self.organisation_code
        if self.organisation_number:
            result["organisationNumber"] = self.organisation_number
        if self.school_unit_code:
            result["schoolUnitCode"] = self.school_unit_code
        if self.municipality_code:
            result["municipalityCode"] = self.municipality_code
        if self.email:
            result["email"] = self.email
        if self.phone_number:
            result["phoneNumber"] = self.phone_number
        if self.url:
            result["url"] = self.url
        if self.start_date:
            result["startDate"] = self.start_date.isoformat()
        if self.end_date:
            result["endDate"] = self.end_date.isoformat()
        if self.school_types:
            result["schoolTypes"] = self.school_types.split(",")

        if self.parent_id:
            result["parentOrganisation"] = {"id": self.parent_id}
            if expand_references and self.parent:
                result["parentOrganisation"]["displayName"] = self.parent.display_name

        if self.street_address or self.postal_code or self.locality:
            result["address"] = {}
            if self.street_address:
                result["address"]["streetAddress"] = self.street_address
            if self.postal_code:
                result["address"]["postalCode"] = self.postal_code
            if self.locality:
                result["address"]["locality"] = self.locality

        return result
