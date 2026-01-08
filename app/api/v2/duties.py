"""
SS12000 Duties API endpoints.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.duty import Duty, DutyAssignment
from ...auth.dependencies import get_current_client
from ...schemas.common import IdLookup

router = APIRouter(prefix="/duties", tags=["Duty"])


@router.get("")
async def list_duties(
    dutyAt: Optional[List[str]] = Query(None),
    dutyRole: Optional[List[str]] = Query(None),
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    pageToken: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    List all duties with optional filters.
    """
    query = select(Duty)

    # Apply filters
    if dutyAt:
        query = query.filter(Duty.organisation_id.in_(dutyAt))
    if dutyRole:
        query = query.filter(Duty.duty_role.in_(dutyRole))

    # Eager load relationships
    query = query.options(
        selectinload(Duty.person),
        selectinload(Duty.organisation),
        selectinload(Duty.assignments)
    )

    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    duties = result.scalars().all()

    return {
        "data": [
            d.to_dict(
                expand_person=expandReferenceNames,
                expand_organisation=expandReferenceNames
            )
            for d in duties
        ],
        "pageToken": None
    }


@router.get("/{id}")
async def get_duty(
    id: str,
    expandReferenceNames: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    Get a single duty by ID.
    """
    query = select(Duty).filter(Duty.id == id).options(
        selectinload(Duty.person),
        selectinload(Duty.organisation),
        selectinload(Duty.assignments)
    )

    result = await db.execute(query)
    duty = result.scalar_one_or_none()

    if not duty:
        raise HTTPException(status_code=404, detail="Duty not found")

    return duty.to_dict(
        expand_person=expandReferenceNames,
        expand_organisation=expandReferenceNames
    )


@router.post("/lookup")
async def lookup_duties(
    lookup: IdLookup,
    expandReferenceNames: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    Bulk lookup duties by IDs.
    """
    ids = [str(id) for id in lookup.ids]
    query = select(Duty).filter(Duty.id.in_(ids)).options(
        selectinload(Duty.person),
        selectinload(Duty.organisation),
        selectinload(Duty.assignments)
    )

    result = await db.execute(query)
    duties = result.scalars().all()

    return [
        d.to_dict(
            expand_person=expandReferenceNames,
            expand_organisation=expandReferenceNames
        )
        for d in duties
    ]
