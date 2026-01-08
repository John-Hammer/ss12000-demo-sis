"""
SS12000 Activity model.
Represents lessons/courses - links teachers to groups.
"""
from datetime import datetime, date
from typing import Optional, List
from uuid import uuid4
from sqlalchemy import String, ForeignKey, DateTime, Date, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


# Many-to-many for activity teachers
class ActivityTeacher(Base):
    """Teacher assignment to an activity."""
    __tablename__ = "activity_teachers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    activity_id: Mapped[str] = mapped_column(String(36), ForeignKey("activities.id"))
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("persons.id"))

    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    allocation_percent: Mapped[Optional[int]] = mapped_column(nullable=True)  # 0-100


# Many-to-many for activity groups
class ActivityGroup(Base):
    """Group assignment to an activity."""
    __tablename__ = "activity_groups"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    activity_id: Mapped[str] = mapped_column(String(36), ForeignKey("activities.id"))
    group_id: Mapped[str] = mapped_column(String(36), ForeignKey("groups.id"))


class Activity(Base):
    """
    SS12000 Activity entity.
    Represents a course/lesson - links teachers to groups.
    This establishes the teacher-student relationship via group memberships.
    """
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Required fields
    display_name: Mapped[str] = mapped_column(String(255))
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"))
    start_date: Mapped[date] = mapped_column(Date)

    # Optional fields
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    activity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Undervisning, etc.

    # Subject information
    subject_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # SV, MA, EN, etc.
    subject_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Svenska, Matematik, etc.

    # Parent activity (for hierarchical structure)
    parent_activity_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("activities.id"), nullable=True)

    # Relationships
    organisation: Mapped["Organisation"] = relationship("Organisation", backref="activities")
    teachers: Mapped[List["ActivityTeacher"]] = relationship("ActivityTeacher", backref="activity")
    groups: Mapped[List["ActivityGroup"]] = relationship("ActivityGroup", backref="activity")
    parent_activity: Mapped[Optional["Activity"]] = relationship("Activity", remote_side=[id], backref="child_activities")

    def to_dict(self, expand_teachers: bool = False, expand_groups: bool = False) -> dict:
        """Convert to SS12000 API response format."""
        result = {
            "id": self.id,
            "meta": {
                "created": self.created_at.isoformat(),
                "modified": self.modified_at.isoformat(),
            },
            "displayName": self.display_name,
            "startDate": self.start_date.isoformat(),
            "owner": {"id": self.organisation_id},
        }

        if self.end_date:
            result["endDate"] = self.end_date.isoformat()
        if self.activity_type:
            result["activityType"] = self.activity_type
        if self.parent_activity_id:
            result["parentActivity"] = {"id": self.parent_activity_id}

        # Subject
        if self.subject_code or self.subject_name:
            result["subject"] = {}
            if self.subject_code:
                result["subject"]["code"] = self.subject_code
            if self.subject_name:
                result["subject"]["displayName"] = self.subject_name

        # Teachers
        if expand_teachers and self.teachers:
            result["teachers"] = []
            for t in self.teachers:
                teacher = {"person": {"id": t.person_id}}
                if t.start_date:
                    teacher["startDate"] = t.start_date.isoformat()
                if t.end_date:
                    teacher["endDate"] = t.end_date.isoformat()
                if t.allocation_percent:
                    teacher["allocationPercent"] = t.allocation_percent
                result["teachers"].append(teacher)
        elif self.teachers:
            result["teachers"] = [{"person": {"id": t.person_id}} for t in self.teachers]

        # Groups
        if expand_groups and self.groups:
            result["groups"] = []
            for g in self.groups:
                result["groups"].append({"id": g.group_id})
        elif self.groups:
            result["groups"] = [{"id": g.group_id} for g in self.groups]

        return result


# Import for type hints
from .organisation import Organisation
