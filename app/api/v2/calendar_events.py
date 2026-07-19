"""
SS12000 CalendarEvents API endpoint.

Events are generated on the fly from each activity's weekly schedule
slots (see models/schedule_slot.py): for every date in the requested
window whose weekday matches a slot, one dated event is emitted. Event
ids are uuid5-derived from (slot, date) so repeated fetches return
byte-identical data. A small deterministic fraction of events is marked
cancelled so consumers exercise their cancelled-handling.

Spec note: startTime.onOrAfter / startTime.onOrBefore are REQUIRED on
this endpoint per SS12000 — requests without them are rejected, which
keeps consumer implementations honest.
"""
import hashlib
from datetime import date, datetime, time, timedelta
from typing import List, Optional
from uuid import uuid5, NAMESPACE_URL
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.schedule_slot import ActivityScheduleSlot
from ...auth.dependencies import get_current_client
from ...schemas.common import paginate

router = APIRouter(prefix="/calendarEvents", tags=["Kalenderhändelser"])

TZ = ZoneInfo("Europe/Stockholm")
MAX_WINDOW_DAYS = 400


def _parse_bound(value: str, param: str) -> date:
    """Accept RFC3339 date-times or plain dates for the window bounds."""
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        pass
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_parameter",
            "message": f"{param} is not a valid RFC3339 timestamp"})


def _is_cancelled(slot_id: str, on: date) -> bool:
    """Deterministic ~5% cancellation rate."""
    digest = hashlib.md5(f"{slot_id}:{on.isoformat()}".encode()).hexdigest()
    return int(digest, 16) % 19 == 0


def _slot_event(slot: ActivityScheduleSlot, on: date) -> dict:
    start_h, start_m = (int(x) for x in slot.start_time.split(":"))
    end_h, end_m = (int(x) for x in slot.end_time.split(":"))
    start_dt = datetime.combine(on, time(start_h, start_m), tzinfo=TZ)
    end_dt = datetime.combine(on, time(end_h, end_m), tzinfo=TZ)

    event = {
        "id": str(uuid5(NAMESPACE_URL, f"calendar-event:{slot.id}:{on.isoformat()}")),
        "meta": {
            "created": start_dt.isoformat(),
            "modified": start_dt.isoformat(),
        },
        "activity": {"id": slot.activity_id},
        "startTime": start_dt.isoformat(),
        "endTime": end_dt.isoformat(),
    }
    if _is_cancelled(slot.id, on):
        event["cancelled"] = True
    if slot.room:
        event["rooms"] = [{
            "id": str(uuid5(NAMESPACE_URL, f"room:{slot.room}")),
            "displayName": slot.room,
        }]
    return event


@router.get("")
async def list_calendar_events(
    start_on_or_after: str = Query(..., alias="startTime.onOrAfter"),
    start_on_or_before: str = Query(..., alias="startTime.onOrBefore"),
    activity: Optional[List[str]] = Query(None),
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    pageToken: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """List calendar events (dated schedule occurrences) in a window."""
    window_start = _parse_bound(start_on_or_after, "startTime.onOrAfter")
    window_end = _parse_bound(start_on_or_before, "startTime.onOrBefore")
    if window_end < window_start:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_parameter",
            "message": "startTime window is inverted"})
    if (window_end - window_start).days > MAX_WINDOW_DAYS:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_parameter",
            "message": f"startTime window exceeds {MAX_WINDOW_DAYS} days"})

    query = select(ActivityScheduleSlot)
    if activity:
        query = query.filter(ActivityScheduleSlot.activity_id.in_(activity))
    result = await db.execute(query)
    slots = result.scalars().all()

    by_weekday: dict = {}
    for slot in slots:
        by_weekday.setdefault(slot.day_of_week, []).append(slot)

    events = []
    current = window_start
    while current <= window_end:
        for slot in by_weekday.get(current.isoweekday(), ()):
            events.append(_slot_event(slot, current))
        current += timedelta(days=1)

    events.sort(key=lambda e: (e["startTime"], e["id"]))
    page, next_token = paginate(events, limit, pageToken)
    return {"data": page, "pageToken": next_token}
