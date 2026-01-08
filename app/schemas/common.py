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
