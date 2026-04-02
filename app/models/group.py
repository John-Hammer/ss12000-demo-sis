"""
SS12000 Group model.
Classes, mentor groups, teaching groups, etc.
"""
from datetime import datetime, date
from typing import Optional, List
from uuid import uuid4
from sqlalchemy import String, ForeignKey, DateTime, Date, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


# Many-to-many for group memberships
class GroupMembership(Base):
    """Group membership with dates."""
    __tablename__ = "group_memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"))
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("persons.id"))

    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class Group(Base):
    """
    SS12000 Group entity.
    Represents classes, mentor groups, teaching groups.
    """
    __tablename__ = "groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Required fields
    display_name: Mapped[str] = mapped_column(String(255))
    group_type: Mapped[str] = mapped_column(String(50))  # GroupType enum value
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"))
    start_date: Mapped[date] = mapped_column(Date)

    # Optional fields
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    school_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Group code (e.g., "4A", "GY1")
    group_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Relationships
    organisation: Mapped["Organisation"] = relationship("Organisation", backref="groups")
    memberships: Mapped[List["GroupMembership"]] = relationship("GroupMembership", backref="group")

    def to_dict(self, expand_members: bool = False, expand_organisation: bool = False) -> dict:
        """Convert to SS12000 API response format."""
        result = {
            "id": self.id,
            "meta": {
                "created": self.created_at.isoformat(),
                "modified": self.modified_at.isoformat(),
            },
            "displayName": self.display_name,
            "groupType": self.group_type,
            "startDate": self.start_date.isoformat(),
            "organisation": {"id": self.organisation_id},
        }

        if self.group_code:
            result["groupCode"] = self.group_code
        if self.end_date:
            result["endDate"] = self.end_date.isoformat()
        if self.school_type:
            result["schoolType"] = self.school_type

        if expand_organisation and self.organisation:
            result["organisation"]["displayName"] = self.organisation.display_name

        if expand_members and self.memberships:
            result["groupMemberships"] = []
            for m in self.memberships:
                member = {"person": {"id": m.person_id}}
                if m.start_date:
                    member["startDate"] = m.start_date.isoformat()
                if m.end_date:
                    member["endDate"] = m.end_date.isoformat()
                result["groupMemberships"].append(member)

        return result


# Import Organisation for type hints
from .organisation import Organisation
