"""
SS12000 Persons API endpoints.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...models.person import Person, Enrolment, PersonResponsible
from ...auth.dependencies import get_current_client
from ...schemas.common import IdLookup, paginate, apply_modified_after

router = APIRouter(prefix="/persons", tags=["Person"])


@router.get("")
async def list_persons(
    expand: Optional[List[str]] = Query(None),
    expandReferenceNames: bool = Query(False),
    limit: Optional[int] = Query(None, ge=1),
    pageToken: Optional[str] = Query(None),
    meta_modified_after: Optional[str] = Query(None, alias="meta.modified.after"),
    db: AsyncSession = Depends(get_db),
    client: dict = Depends(get_current_client),
):
    """
    List all persons with optional expand.

    expand options:
    - enrolments: Include student enrolments
    - responsibles: Include guardian relationships
    """
    # Spec: enrolments and responsibles are BASE Person fields (the
    # expand mechanism is for _embedded objects like duties/placements),
    # so they are always loaded and always returned. expand is tolerated.
    query = (select(Person)
             .options(selectinload(Person.enrolments),
                      selectinload(Person.responsible_links)
                      .selectinload(PersonResponsible.responsible_person))
             .order_by(Person.id))
    query = apply_modified_after(query, Person, meta_modified_after)

    result = await db.execute(query)
    persons = result.scalars().all()

    page, next_token = paginate(persons, limit, pageToken)
    return {
        "data": [
            p.to_dict(expand_enrolments=True, expand_responsibles=True)
            for p in page
        ],
        "pageToken": next_token
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
            query = query.options(selectinload(Person.responsible_links)
                                  .selectinload(PersonResponsible.responsible_person))

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
            query = query.options(selectinload(Person.responsible_links)
                                  .selectinload(PersonResponsible.responsible_person))

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
