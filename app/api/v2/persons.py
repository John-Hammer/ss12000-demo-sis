"""
SS12000 Persons API endpoints.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.person import Person, Enrolment
from ...auth.dependencies import get_current_client
from ...schemas.common import IdLookup

router = APIRouter(prefix="/persons", tags=["Person"])


@router.get("")
async def list_persons(
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    pageToken: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    List all persons with optional expand.

    expand options:
    - enrolments: Include student enrolments
    - responsibles: Include guardian relationships
    """
    query = select(Person)

    # Eager load relationships if expanding
    if expand:
        if "enrolments" in expand:
            query = query.options(selectinload(Person.enrolments))
        if "responsibles" in expand:
            query = query.options(selectinload(Person.responsibles))

    if limit:
        query = query.limit(limit)

    result = await db.execute(query)
    persons = result.scalars().all()

    expand_enrolments = expand and "enrolments" in expand
    expand_responsibles = expand and "responsibles" in expand

    return {
        "data": [
            p.to_dict(
                expand_enrolments=expand_enrolments,
                expand_responsibles=expand_responsibles
            )
            for p in persons
        ],
        "pageToken": None
    }


@router.get("/{id}")
async def get_person(
    id: str,
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    Get a single person by ID.
    """
    query = select(Person).filter(Person.id == id)

    if expand:
        if "enrolments" in expand:
            query = query.options(selectinload(Person.enrolments))
        if "responsibles" in expand:
            query = query.options(selectinload(Person.responsibles))

    result = await db.execute(query)
    person = result.scalar_one_or_none()

    if not person:
        raise HTTPException(status_code=404, detail="Person not found")

    expand_enrolments = expand and "enrolments" in expand
    expand_responsibles = expand and "responsibles" in expand

    return person.to_dict(
        expand_enrolments=expand_enrolments,
        expand_responsibles=expand_responsibles
    )


@router.post("/lookup")
async def lookup_persons(
    lookup: IdLookup,
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    Bulk lookup persons by IDs.
    """
    ids = [str(id) for id in lookup.ids]
    query = select(Person).filter(Person.id.in_(ids))

    if expand:
        if "enrolments" in expand:
            query = query.options(selectinload(Person.enrolments))
        if "responsibles" in expand:
            query = query.options(selectinload(Person.responsibles))

    result = await db.execute(query)
    persons = result.scalars().all()

    expand_enrolments = expand and "enrolments" in expand
    expand_responsibles = expand and "responsibles" in expand

    return [
        p.to_dict(
            expand_enrolments=expand_enrolments,
            expand_responsibles=expand_responsibles
        )
        for p in persons
    ]
