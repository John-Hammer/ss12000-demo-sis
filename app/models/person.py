"""
SS12000 Person model.
Unified model for students, staff, and guardians.
"""
from datetime import datetime, date
from typing import Optional, List
from uuid import uuid4
from sqlalchemy import String, ForeignKey, DateTime, Date, Text, Boolean, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..database import Base


# Many-to-many relationship for guardians (responsibles)
person_responsibles = Table(
    "person_responsibles",
    Base.metadata,
    Column("person_id", String(36), ForeignKey("persons.id"), primary_key=True),
    Column("responsible_id", String(36), ForeignKey("persons.id"), primary_key=True),
    Column("relation_type", String(50)),  # Vårdnadshavare, etc.
)


# Many-to-many for enrolments (students -> organisations)
class Enrolment(Base):
    """Student enrolment at a school unit."""
    __tablename__ = "enrolments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    person_id: Mapped[str] = mapped_column(String(36), ForeignKey("persons.id"))
    organisation_id: Mapped[str] = mapped_column(String(36), ForeignKey("organisations.id"))

    school_type: Mapped[str] = mapped_column(String(20))  # GR, GY, etc.
    school_year: Mapped[Optional[int]] = mapped_column(nullable=True)  # 1-9 for grundskola
    programme_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    specification: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    education_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cancelled: Mapped[bool] = mapped_column(Boolean, default=False)


class Person(Base):
    """
    SS12000 Person entity.
    Unified model for students, staff, and guardians.
    """
    __tablename__ = "persons"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    modified_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Required fields
    given_name: Mapped[str] = mapped_column(String(100))
    family_name: Mapped[str] = mapped_column(String(100))

    # Optional name fields
    middle_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Identity
    civic_no: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Personnummer
    civic_no_nationality: Mapped[str] = mapped_column(String(2), default="SE")
    birth_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sex: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # Man, Kvinna, Okänt

    # Security and status
    security_marking: Mapped[str] = mapped_column(String(50), default="Ingen")
    person_status: Mapped[str] = mapped_column(String(20), default="Aktiv")

    # Contact info (simplified - could be separate tables for multiple emails/phones)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Skola, Privat
    phone_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    phone_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Address (simplified)
    street_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    locality: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Photo URL
    photo: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # EduPersonPrincipalName (for login)
    edu_person_principal_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # External identifiers (simplified - one per person for demo)
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_id_context: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    enrolments: Mapped[List["Enrolment"]] = relationship("Enrolment", backref="person")

    # Guardians (self-referential many-to-many)
    responsibles: Mapped[List["Person"]] = relationship(
        "Person",
        secondary=person_responsibles,
        primaryjoin=id == person_responsibles.c.person_id,
        secondaryjoin=id == person_responsibles.c.responsible_id,
        backref="dependents"
    )

    def to_dict(self, expand_enrolments: bool = False, expand_responsibles: bool = False) -> dict:
        """Convert to SS12000 API response format."""
        result = {
            "id": self.id,
            "meta": {
                "created": self.created_at.isoformat(),
                "modified": self.modified_at.isoformat(),
            },
            "givenName": self.given_name,
            "familyName": self.family_name,
        }

        if self.middle_name:
            result["middleName"] = self.middle_name
        if self.birth_date:
            result["birthDate"] = self.birth_date.isoformat()
        if self.sex:
            result["sex"] = self.sex
        if self.security_marking:
            result["securityMarking"] = self.security_marking
        if self.person_status:
            result["personStatus"] = self.person_status

        if self.civic_no:
            result["civicNo"] = {
                "value": self.civic_no,
                "nationality": self.civic_no_nationality
            }

        if self.email:
            result["emails"] = [{"value": self.email, "type": self.email_type or "Skola"}]

        if self.phone_number:
            result["phoneNumbers"] = [{
                "value": self.phone_number,
                "type": self.phone_type or "Hem",
                "mobile": True
            }]

        if self.street_address or self.postal_code or self.locality:
            result["addresses"] = [{
                "type": "Folkbokföring",
                "streetAddress": self.street_address,
                "postalCode": self.postal_code,
                "locality": self.locality
            }]

        if self.photo:
            result["photo"] = self.photo

        if self.edu_person_principal_name:
            result["eduPersonPrincipalNames"] = [self.edu_person_principal_name]

        if self.external_id:
            result["externalIdentifiers"] = [{
                "value": self.external_id,
                "context": self.external_id_context or "http://fake-sis.local",
                "globallyUnique": True
            }]

        if expand_enrolments and self.enrolments:
            result["enrolments"] = []
            for e in self.enrolments:
                enrol = {
                    "enroledAt": {"id": e.organisation_id},
                    "schoolType": e.school_type,
                    "cancelled": e.cancelled
                }
                if e.school_year:
                    enrol["schoolYear"] = e.school_year
                if e.start_date:
                    enrol["startDate"] = e.start_date.isoformat()
                if e.end_date:
                    enrol["endDate"] = e.end_date.isoformat()
                result["enrolments"].append(enrol)

        if expand_responsibles and self.responsibles:
            result["responsibles"] = []
            for r in self.responsibles:
                result["responsibles"].append({
                    "person": {"id": r.id, "displayName": f"{r.given_name} {r.family_name}"},
                    "relationType": "Vårdnadshavare"
                })

        return result
