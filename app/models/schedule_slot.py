"""
Weekly schedule slot for an activity.

SS12000 exposes schedules as CalendarEvents (one per dated occurrence).
Storing every occurrence would bloat the demo DB, so the fake SIS keeps
the *weekly pattern* per activity and the /calendarEvents endpoint
expands the pattern into dated events for the requested time window —
deterministically, so consumers can re-fetch and get identical data.
"""
from typing import Optional
from uuid import uuid4
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


class ActivityScheduleSlot(Base):
    """One weekly occurrence pattern of an activity (e.g. Mon 08:00-09:00)."""
    __tablename__ = "activity_schedule_slots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    activity_id: Mapped[str] = mapped_column(String(36), ForeignKey("activities.id"))

    day_of_week: Mapped[int] = mapped_column()  # ISO: 1=Monday .. 5=Friday
    start_time: Mapped[str] = mapped_column(String(5))  # "08:00"
    end_time: Mapped[str] = mapped_column(String(5))    # "09:00"
    room: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    activity: Mapped["Activity"] = relationship("Activity", backref="schedule_slots")


from .activity import Activity  # noqa: E402  (type-hint import, matches sibling models)
