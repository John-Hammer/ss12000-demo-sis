"""
Common Pydantic schemas for SS12000 API.
Meta, pagination, errors, and references.
"""
from datetime import datetime
from typing import Optional, List, Any
from uuid import UUID
from pydantic import BaseModel, Field


class Meta(BaseModel):
    """Metadata for all SS12000 entities."""
    created: datetime = Field(description="When the entity was created")
    modified: datetime = Field(description="When the entity was last modified")


class ObjectReference(BaseModel):
    """Reference to another SS12000 object."""
    id: UUID
    displayName: Optional[str] = None


class OrganisationReference(ObjectReference):
    """Reference to an organisation."""
    pass


class PersonReference(ObjectReference):
    """Reference to a person."""
    pass


class GroupReference(ObjectReference):
    """Reference to a group."""
    pass


class PaginatedResponse(BaseModel):
    """Base for paginated responses."""
    pageToken: Optional[str] = Field(
        None,
        description="Token for next page, null if no more data"
    )


class Error(BaseModel):
    """Error response."""
    code: int
    message: str
    details: Optional[str] = None


class IdLookup(BaseModel):
    """Request body for bulk ID lookups."""
    ids: List[UUID]


class Enrolment(BaseModel):
    """Student enrolment at a school unit."""
    enroledAt: OrganisationReference
    schoolType: str
    schoolYear: Optional[int] = None
    programme: Optional[ObjectReference] = None
    specification: Optional[str] = None
    educationCode: Optional[str] = None
    startDate: Optional[str] = None
    endDate: Optional[str] = None
    cancelled: bool = False


class Responsible(BaseModel):
    """Guardian/responsible person for a student."""
    person: PersonReference
    relationType: str


class GroupMember(BaseModel):
    """Member of a group with optional role."""
    person: PersonReference
    startDate: Optional[str] = None
    endDate: Optional[str] = None


class AssignmentRole(BaseModel):
    """Staff assignment to a group."""
    group: GroupReference
    assignmentRoleType: str
    startDate: Optional[str] = None
    endDate: Optional[str] = None


# SS12000 pagination. A real SIS pages at ~100 records; the demo doing the
# same is what forces clients to implement pageToken correctly — returning
# everything in one response hid a truncation bug in every consumer.
# 50 (not a real SIS's ~100) so the demo dataset ALWAYS spans multiple
# pages — every nightly demo sync then exercises the client's pageToken loop.
DEFAULT_PAGE_SIZE = 50


def paginate(items, limit, page_token):
    """Slice an ORDERED item list per SS12000 {data, pageToken} semantics.

    Returns (page_items, next_page_token). The token is an opaque offset
    cursor; None means no more data.
    """
    from fastapi import HTTPException
    page_size = limit or DEFAULT_PAGE_SIZE
    try:
        offset = int(page_token) if page_token else 0
        if offset < 0:
            raise ValueError
    except ValueError:
        raise HTTPException(status_code=400, detail={
            "code": "invalid_page_token", "message": "pageToken is not valid"})
    page = items[offset:offset + page_size]
    next_offset = offset + page_size
    next_token = str(next_offset) if next_offset < len(items) else None
    return page, next_token
