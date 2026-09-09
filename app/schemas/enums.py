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
    """Staff roles — Code_DutyRole v2.1.0 (corrigendum Aug 2022): NINETEEN
    values, aligned with Skolverket's code-duty-role vocabulary. v2.0 had
    six; the health-team roles are duty roles since 2.1, and the two
    v2.0 leftovers are deprecated. EHT-ness ALSO travels as an
    assignmentRole (Elevhälsopersonal / Specialpedagog) on the duty, the
    way a v2.0-shaped source sends it.
    """
    REKTOR = "Rektor"
    LARARE = "Lärare"
    FORSKOLLARARE = "Förskollärare"
    BARNSKOTARE = "Barnskötare"
    BIBLIOTEKARIE = "Bibliotekarie"
    LARARASSISTENT = "Lärarassistent"
    FRITIDSPEDAGOG = "Fritidspedagog"
    ANNAN_PERSONAL = "Annan personal"
    STUDIE_OCH_YRKESVAGLEDARE = "Studie- och yrkesvägledare"
    FORSTELARARE = "Förstelärare"
    KURATOR = "Kurator"
    SKOLSKOTERSKA = "Skolsköterska"
    SKOLLAKARE = "Skolläkare"
    SKOLPSYKOLOG = "Skolpsykolog"
    SPECIALLARARE_SPECIALPEDAGOG = "Speciallärare/specialpedagog"
    SKOLADMINISTRATOR = "Skoladministratör"
    OVRIG_ARBETSLEDNING = "Övrig arbetsledning"
    OVRIG_PEDAGOGISK_PERSONAL = "Övrig pedagogisk personal"   # deprecated in 2.1
    FORSKOLECHEF = "Förskolechef"                             # deprecated in 2.1


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
    """Assignment role types — the spec's Code_AssignmentRole values."""
    MENTOR = "Mentor"
    FORSKOLLARARE = "Förskollärare"
    BARNSKOTARE = "Barnskötare"
    FRITIDSPEDAGOG = "Fritidspedagog"
    SPECIALPEDAGOG = "Specialpedagog"
    ELEVHALSOPERSONAL = "Elevhälsopersonal"
    PEDAGOGISK_LEDARE = "Pedagogisk ledare"
    SCHEMALAGGARE = "Schemaläggare"
