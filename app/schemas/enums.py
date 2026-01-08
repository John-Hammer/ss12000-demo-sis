"""
SS12000 v2.1 Enumerations
Swedish school system standard enums.
"""
from enum import Enum


class OrganisationType(str, Enum):
    """Type of organisation in the school hierarchy."""
    HUVUDMAN = "Huvudman"  # School principal/authority
    VERKSAMHETSOMRADE = "Verksamhetsområde"  # Area of operations
    FORVALTNING = "Förvaltning"  # Administration
    REKTORSOMRADE = "Rektorsområde"  # Principal's area
    SKOLA = "Skola"  # School
    SKOLENHET = "Skolenhet"  # School unit
    VARUMARKE = "Varumärke"  # Brand
    BOLAG = "Bolag"  # Company
    OVRIGT = "Övrigt"  # Other


class SchoolType(str, Enum):
    """Types of schools in Swedish education system."""
    FS = "FS"  # Förskola (Preschool)
    FSK = "FSK"  # Förskoleklass
    GR = "GR"  # Grundskola (Primary school)
    GRS = "GRS"  # Grundsärskola
    SP = "SP"  # Specialskola
    SAM = "SAM"  # Sameskola
    GY = "GY"  # Gymnasium (Upper secondary)
    GYS = "GYS"  # Gymnasiesärskola
    VUX = "VUX"  # Vuxenutbildning (Adult education)
    SUV = "SUV"  # Särskild utbildning för vuxna
    YH = "YH"  # Yrkeshögskola
    FHS = "FHS"  # Folkhögskola
    FTH = "FTH"  # Fritidshem (After-school care)
    OPPFTH = "OPPFTH"  # Öppen fritidshem
    AU = "AU"  # Arbetsmarknadsutbildning


class DutyRole(str, Enum):
    """Staff roles in SS12000."""
    REKTOR = "Rektor"  # Principal
    LARARE = "Lärare"  # Teacher
    FORSKOLLARARE = "Förskollärare"  # Preschool teacher
    BARNSKOTARE = "Barnskötare"  # Childminder
    BIBLIOTEKARIE = "Bibliotekarie"  # Librarian
    LARARASSISTENT = "Lärarassistent"  # Teacher assistant
    FRITIDSPEDAGOG = "Fritidspedagog"  # Recreation instructor
    ANNAN_PERSONAL = "Annan personal"  # Other staff
    STUDIE_YRKESVAGLEDARE = "Studie- och yrkesvägledare"  # Career counselor
    FORSTELÄRARE = "Förstelärare"  # Senior teacher
    KURATOR = "Kurator"  # Counselor
    SKOLSKOTERSKA = "Skolsköterska"  # School nurse
    SKOLLAKARE = "Skolläkare"  # School doctor
    SKOLPSYKOLOG = "Skolpsykolog"  # School psychologist
    SPECIALLARARE = "Speciallärare/specialpedagog"  # Special education teacher
    SKOLADMINISTRATOR = "Skoladministratör"  # School administrator
    OVRIG_ARBETSLEDNING = "Övrig arbetsledning"  # Other management


class GroupType(str, Enum):
    """Types of groups in SS12000."""
    UNDERVISNING = "Undervisning"  # Teaching group
    KLASS = "Klass"  # Class
    MENTOR = "Mentor"  # Mentor group
    PROVGRUPP = "Provgrupp"  # Test group
    SCHEMA = "Schema"  # Schedule group
    AVDELNING = "Avdelning"  # Division
    PERSONALGRUPP = "Personalgrupp"  # Staff group
    OVRIGT = "Övrigt"  # Other


class Sex(str, Enum):
    """Biological sex."""
    MAN = "Man"
    KVINNA = "Kvinna"
    OKANT = "Okänt"


class SecurityMarking(str, Enum):
    """Security marking from population registry."""
    INGEN = "Ingen"  # None
    SEKRETESSMARKERING = "Sekretessmarkering"  # Confidential
    SKYDDAD_FOLKBOKFORING = "Skyddad folkbokföring"  # Protected registration


class PersonStatus(str, Enum):
    """Person's status."""
    AKTIV = "Aktiv"  # Active
    UTVANDRAD = "Utvandrad"  # Emigrated
    AVLIDEN = "Avliden"  # Deceased


class RelationType(str, Enum):
    """Guardian relationship types."""
    VARDNADSHAVARE = "Vårdnadshavare"  # Legal guardian
    FAMILJEHEMSFORALDER = "Familjehemsförälder"  # Foster parent
    GOD_MAN = "God man"  # Guardian ad litem
    BOENDEFORALDER = "Boendeförälder"  # Residential parent
    KONTAKTPERSON = "Kontaktperson"  # Contact person


class AssignmentRoleType(str, Enum):
    """Assignment role types for duties."""
    MENTOR = "Mentor"
    FORSTELÄRARE = "Förstelärare"  # Senior teacher
    STUDIEHANDLEDARE = "Studiehandledare"  # Study supervisor
    RESURSPERSON = "Resursperson"  # Resource person
