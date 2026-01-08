"""
SS12000 Organisations API endpoints.
"""
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.organisation import Organisation
from ...auth.dependencies import get_current_client
from ...schemas.common import IdLookup

router = APIRouter(prefix="/organisations", tags=["Organisation"])


@router.get("")
async def list_organisations(
    parent: Optional[List[str]] = Query(None),
    schoolUnitCode: Optional[List[str]] = Query(None),
    organisationCode: Optional[List[str]] = Query(None),
    type: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    pageToken: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    List all organisations with optional filters.
    """
    query = select(Organisation)

    # Apply filters
    if parent:
        query = query.filter(Organisation.parent_id.in_(parent))
    if schoolUnitCode:
        query = query.filter(Organisation.school_unit_code.in_(schoolUnitCode))
    if organisationCode:
        query = query.filter(Organisation.organisation_code.in_(organisationCode))
    if type:
        query = query.filter(Organisation.organisation_type.in_(type))

    # Apply limit
    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    organisations = result.scalars().all()

    return {
        "data": [org.to_dict(expand_references=expandReferenceNames) for org in organisations],
        "pageToken": None  # Simple implementation - no pagination for demo
    }


@router.get("/{id}")
async def get_organisation(
    id: str,
    expandReferenceNames: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    Get a single organisation by ID.
    """
    result = await db.execute(select(Organisation).filter(Organisation.id == id))
    organisation = result.scalar_one_or_none()

    if not organisation:
        raise HTTPException(status_code=404, detail="Organisation not found")

    return organisation.to_dict(expand_references=expandReferenceNames)


@router.post("/lookup")
async def lookup_organisations(
    lookup: IdLookup,
    expandReferenceNames: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    Bulk lookup organisations by IDs.
    """
    ids = [str(id) for id in lookup.ids]
    result = await db.execute(select(Organisation).filter(Organisation.id.in_(ids)))
    organisations = result.scalars().all()

    return [org.to_dict(expand_references=expandReferenceNames) for org in organisations]
