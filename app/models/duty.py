"""
SS12000 Duty model.
Staff positions and roles at organisations.
"""
from datetime import datetime, date
from typing import Optional, List
from uuid import uuid4
from sqlalchemy import String, ForeignKey, DateTime, Date, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class DutyAssignment(Base):
    """Assignment of a duty to a group (e.g., mentor for a class)."""
    __tablename__ = "duty_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    duty_id: Mapped[str] = mapped_column(String(36), ForeignKey("duties.id"))
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"))

    assignment_role_type: Mapped[str] = mapped_column(String(50))  # Mentor, Förstelärare, etc.
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class Duty(Base):
    """
    SS12000 Duty entity.
    Represents a staff member's position at an organisation.
    """
    __tablename__ = "duties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Required fields
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("persons.id"))
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"))
    duty_role: Mapped[str] = mapped_column(String(50))  # DutyRole enum value
    start_date: Mapped[date] = mapped_column(Date)

    # Optional fields
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    signature: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # e.g., "GAN", "ELR"
    duty_percent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-100
    hours_per_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Relationships
    person: Mapped["Person"] = relationship("Person", backref="duties")
    organisation: Mapped["Organisation"] = relationship("Organisation", backref="duties")
    assignments: Mapped[List["DutyAssignment"]] = relationship("DutyAssignment", backref="duty")

    def to_dict(self, expand_person: bool = False, expand_organisation: bool = False) -> dict:
        """Convert to SS12000 API response format."""
        result = {
            "id": self.id,
            "meta": {
                "created": self.created_at.isoformat(),
                "modified": self.modified_at.isoformat(),
            },
            "person": {"id": self.person_id},
            "dutyAt": {"id": self.organisation_id},
            "dutyRole": self.duty_role,
            "startDate": self.start_date.isoformat(),
        }

        if self.end_date:
            result["endDate"] = self.end_date.isoformat()
        if self.description:
            result["description"] = self.description
        if self.signature:
            result["signature"] = self.signature
        if self.duty_percent is not None:
            result["dutyPercent"] = self.duty_percent
        if self.hours_per_year is not None:
            result["hoursPerYear"] = self.hours_per_year

        if expand_person and self.person:
            result["person"]["displayName"] = f"{self.person.given_name} {self.person.family_name}"

        if expand_organisation and self.organisation:
            result["dutyAt"]["displayName"] = self.organisation.display_name

        if self.assignments:
            result["assignmentRole"] = []
            for a in self.assignments:
                assignment = {
                    "group": {"id": a.group_id},
                    "assignmentRoleType": a.assignment_role_type
                }
                if a.start_date:
                    assignment["startDate"] = a.start_date.isoformat()
                if a.end_date:
                    assignment["endDate"] = a.end_date.isoformat()
                result["assignmentRole"].append(assignment)

        return result


# Import for type hints
from .person import Person
from .organisation import Organisation
