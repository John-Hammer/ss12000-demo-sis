"""
SS12000 Groups API endpoints.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.group import Group, GroupMembership
from ...auth.dependencies import get_current_client
from ...schemas.common import IdLookup

router = APIRouter(prefix="/groups", tags=["Grupper"])


@router.get("")
async def list_groups(
    organisation: Optional[List[str]] = Query(None),
    groupType: Optional[List[str]] = Query(None),
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    pageToken: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    List all groups with optional filters.

    expand options:
    - groupMemberships: Include group members
    """
    query = select(Group)

    # Apply filters
    if organisation:
        query = query.filter(Group.organisation_id.in_(organisation))
    if groupType:
        query = query.filter(Group.group_type.in_(groupType))

    # Eager load relationships if expanding
    if expand and "groupMemberships" in expand:
        query = query.options(selectinload(Group.memberships))

    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    groups = result.scalars().all()

    expand_members = expand and "groupMemberships" in expand

    return {
        "data": [
            g.to_dict(
                expand_members=expand_members,
                expand_organisation=expandReferenceNames
            )
            for g in groups
        ],
        "pageToken": None
    }


@router.get("/{id}")
async def get_group(
    id: str,
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    Get a single group by ID.
    """
    query = select(Group).filter(Group.id == id)

    if expand and "groupMemberships" in expand:
        query = query.options(selectinload(Group.memberships))

    result = await db.execute(query)
    group = result.scalar_one_or_none()

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")

    expand_members = expand and "groupMemberships" in expand

    return group.to_dict(
        expand_members=expand_members,
        expand_organisation=expandReferenceNames
    )


@router.post("/lookup")
async def lookup_groups(
    lookup: IdLookup,
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    Bulk lookup groups by IDs.
    """
    ids = [str(id) for id in lookup.ids]
    query = select(Group).filter(Group.id.in_(ids))

    if expand and "groupMemberships" in expand:
        query = query.options(selectinload(Group.memberships))

    result = await db.execute(query)
    groups = result.scalars().all()

    expand_members = expand and "groupMemberships" in expand

    return [
        g.to_dict(
            expand_members=expand_members,
            expand_organisation=expandReferenceNames
        )
        for g in groups
    ]
