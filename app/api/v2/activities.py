"""
SS12000 Activities API endpoints.
Activities represent lessons/courses that link teachers to groups.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.activity import Activity, ActivityTeacher, ActivityGroup
from ...auth.dependencies import get_current_client
from ...schemas.common import IdLookup

router = APIRouter(prefix="/activities", tags=["Aktiviteter"])


@router.get("")
async def list_activities(
    organisation: Optional[List[str]] = Query(None),
    activityType: Optional[List[str]] = Query(None),
    subject: Optional[str] = Query(None),
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    pageToken: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    List all activities (lessons/courses) with optional filters.

    expand options:
    - teachers: Include teacher assignments
    - groups: Include group assignments
    """
    query = select(Activity)

    # Apply filters
    if organisation:
        query = query.filter(Activity.organisation_id.in_(organisation))
    if activityType:
        query = query.filter(Activity.activity_type.in_(activityType))
    if subject:
        query = query.filter(Activity.subject_code == subject)

    # Eager load relationships if expanding
    if expand:
        if "teachers" in expand:
            query = query.options(selectinload(Activity.teachers))
        if "groups" in expand:
            query = query.options(selectinload(Activity.groups))

    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    activities = result.scalars().all()

    expand_teachers = expand and "teachers" in expand
    expand_groups = expand and "groups" in expand

    return {
        "data": [
            a.to_dict(
                expand_teachers=expand_teachers,
                expand_groups=expand_groups
            )
            for a in activities
        ],
        "pageToken": None
    }


@router.get("/{id}")
async def get_activity(
    id: str,
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    Get a single activity by ID.
    """
    query = select(Activity).filter(Activity.id == id)

    if expand:
        if "teachers" in expand:
            query = query.options(selectinload(Activity.teachers))
        if "groups" in expand:
            query = query.options(selectinload(Activity.groups))

    result = await db.execute(query)
    activity = result.scalar_one_or_none()

    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")

    expand_teachers = expand and "teachers" in expand
    expand_groups = expand and "groups" in expand

    return activity.to_dict(
        expand_teachers=expand_teachers,
        expand_groups=expand_groups
    )


@router.post("/lookup")
async def lookup_activities(
    lookup: IdLookup,
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    Bulk lookup activities by IDs.
    """
    ids = [str(id) for id in lookup.ids]
    query = select(Activity).filter(Activity.id.in_(ids))

    if expand:
        if "teachers" in expand:
            query = query.options(selectinload(Activity.teachers))
        if "groups" in expand:
            query = query.options(selectinload(Activity.groups))

    result = await db.execute(query)
    activities = result.scalars().all()

    expand_teachers = expand and "teachers" in expand
    expand_groups = expand and "groups" in expand

    return [
        a.to_dict(
            expand_teachers=expand_teachers,
            expand_groups=expand_groups
        )
        for a in activities
    ]
