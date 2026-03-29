"""
Global person registry for cross-system anonymization consistency.

Builds a unified view of all persons from a pg_dump, then computes
deterministic anonymized identities. The registry can be serialized
to JSON and reloaded by other scripts (e.g., Comvius anonymizer).
"""
import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

from .anonymizer import (
    anonymize_first_name, anonymize_last_name, anonymize_personnummer,
    anonymize_email_staff, anonymize_email_student, anonymize_email_guardian,
    anonymize_phone, anonymize_address, anonymize_signature, anonymize_username,
)
from .extract_from_dump import get_active_staff, get_staff_roles


@dataclass
class PersonRecord:
    """A single person's real and anonymized identity."""
    entity_type: str       # "student", "staff", "parent"
    django_pk: str         # Integer PK as string
    personnummer: Optional[str] = None
    first_name: str = ""
    last_name: str = ""
    email: Optional[str] = None
    gender: Optional[str] = None
    comvius_id: Optional[str] = None
    # Staff-specific
    user_id: Optional[str] = None  # auth_user FK for staff
    # Computed anonymized values
    anon_first: Optional[str] = None
    anon_last: Optional[str] = None
    anon_pnr: Optional[str] = None
    anon_email: Optional[str] = None
    anon_phone: Optional[str] = None
    anon_username: Optional[str] = None
    anon_signature: Optional[str] = None
    anon_street: Optional[str] = None
    anon_postal: Optional[str] = None
    anon_city: Optional[str] = None


class PersonRegistry:
    """Registry of all persons with consistent anonymization across systems."""

    def __init__(self):
        self.persons: dict[str, PersonRecord] = {}   # key: "{type}:{pk}"
        self._pnr_index: dict[str, str] = {}         # normalized_pnr -> person_key
        self._email_index: dict[str, str] = {}        # email -> person_key
        self._comvius_index: dict[str, str] = {}      # comvius_id -> person_key
        self._user_id_index: dict[str, str] = {}      # auth_user.id -> person_key (staff)

    @staticmethod
    def _normalize_pnr(pnr: str) -> str:
        """Normalize personnummer for consistent lookups."""
        return pnr.strip().replace(" ", "").replace("-", "")

    def _key(self, entity_type: str, pk: str) -> str:
        return f"{entity_type}:{pk}"

    def add_person(self, record: PersonRecord) -> None:
        key = self._key(record.entity_type, record.django_pk)
        self.persons[key] = record
        if record.personnummer:
            norm = self._normalize_pnr(record.personnummer)
            if norm:
                self._pnr_index[norm] = key
        if record.email:
            self._email_index[record.email.lower()] = key
        if record.comvius_id:
            self._comvius_index[str(record.comvius_id)] = key
        if record.user_id:
            self._user_id_index[str(record.user_id)] = key

    def build_from_dump_data(self, data: dict) -> None:
        """Populate registry from extract_tables() output."""
        # Staff (joined auth_user + users_staff)
        staff_roles = get_staff_roles(data)
        staff_by_user_id = {}
        for s in data.get("users_staff", []):
            staff_by_user_id[s["user_id"]] = s

        for u in data.get("auth_user", []):
            staff = staff_by_user_id.get(u["id"])
            if not staff:
                continue
            gender = self._guess_gender(u.get("first_name", ""))
            self.add_person(PersonRecord(
                entity_type="staff",
                django_pk=staff["id"],
                personnummer=staff.get("socialnumber"),
                first_name=u.get("first_name", ""),
                last_name=u.get("last_name", ""),
                email=u.get("email") or staff.get("email"),
                gender=gender,
                user_id=u["id"],
            ))

        # Students
        for s in data.get("students_student", []):
            gender = self._normalize_gender(s.get("gender"))
            self.add_person(PersonRecord(
                entity_type="student",
                django_pk=s["id"],
                personnummer=s.get("socialnumber"),
                first_name=s.get("first_name", ""),
                last_name=s.get("last_name", ""),
                email=s.get("email"),
                gender=gender,
                comvius_id=s.get("comvius_id"),
            ))

        # Parents/guardians
        for p in data.get("parents_parent", []):
            gender = self._guess_gender(p.get("first_name", ""))
            self.add_person(PersonRecord(
                entity_type="parent",
                django_pk=p["id"],
                personnummer=p.get("personnummer"),
                first_name=p.get("first_name", ""),
                last_name=p.get("last_name", ""),
                email=p.get("email"),
                gender=gender,
            ))

    def compute_anonymized_identities(self, seed: int) -> None:
        """Compute all anonymized fields for every person."""
        for key, p in self.persons.items():
            p.anon_first = anonymize_first_name(seed, p.django_pk, p.gender)
            p.anon_last = anonymize_last_name(seed, p.django_pk)
            p.anon_pnr = anonymize_personnummer(seed, p.django_pk, p.personnummer)

            if p.entity_type == "staff":
                p.anon_email = anonymize_email_staff(seed, p.anon_first, p.anon_last)
                p.anon_signature = anonymize_signature(p.anon_last)
            elif p.entity_type == "student":
                p.anon_email = anonymize_email_student(seed, p.anon_first, p.anon_last)
            else:
                p.anon_email = anonymize_email_guardian(seed, p.anon_first, p.anon_last)

            p.anon_username = anonymize_username(seed, p.anon_first, p.anon_last)
            p.anon_phone = anonymize_phone(seed, p.django_pk)
            street, postal, city = anonymize_address(seed, p.django_pk)
            p.anon_street = street
            p.anon_postal = postal
            p.anon_city = city

    def by_pnr(self, pnr: str) -> Optional[PersonRecord]:
        norm = self._normalize_pnr(pnr)
        key = self._pnr_index.get(norm)
        return self.persons.get(key) if key else None

    def by_comvius_id(self, cid: str) -> Optional[PersonRecord]:
        key = self._comvius_index.get(str(cid))
        return self.persons.get(key) if key else None

    def by_email(self, email: str) -> Optional[PersonRecord]:
        key = self._email_index.get(email.lower())
        return self.persons.get(key) if key else None

    def by_user_id(self, user_id: str) -> Optional[PersonRecord]:
        key = self._user_id_index.get(str(user_id))
        return self.persons.get(key) if key else None

    def by_key(self, entity_type: str, pk: str) -> Optional[PersonRecord]:
        return self.persons.get(self._key(entity_type, pk))

    def save_mapping(self, path: str) -> None:
        """Serialize to JSON for cross-script use."""
        out = {
            "persons": {},
            "pnr_index": {},
            "email_index": self._email_index,
            "comvius_index": self._comvius_index,
        }
        for key, p in self.persons.items():
            out["persons"][key] = {
                "entity_type": p.entity_type,
                "django_pk": p.django_pk,
                "anon_first": p.anon_first,
                "anon_last": p.anon_last,
                "anon_pnr": p.anon_pnr,
                "anon_email": p.anon_email,
                "anon_phone": p.anon_phone,
                "anon_username": p.anon_username,
                "anon_signature": p.anon_signature,
                "anon_street": p.anon_street,
                "anon_postal": p.anon_postal,
                "anon_city": p.anon_city,
                "comvius_id": p.comvius_id,
                "user_id": p.user_id,
            }
        # PNR index: orig_normalized_pnr -> anon_pnr
        for norm_pnr, pkey in self._pnr_index.items():
            p = self.persons[pkey]
            if p.anon_pnr:
                out["pnr_index"][norm_pnr] = p.anon_pnr
        with open(path, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    @classmethod
    def load_mapping(cls, path: str) -> 'PersonRegistry':
        """Deserialize from JSON."""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        reg = cls()
        for key, pdata in data["persons"].items():
            p = PersonRecord(
                entity_type=pdata["entity_type"],
                django_pk=pdata["django_pk"],
                anon_first=pdata.get("anon_first"),
                anon_last=pdata.get("anon_last"),
                anon_pnr=pdata.get("anon_pnr"),
                anon_email=pdata.get("anon_email"),
                anon_phone=pdata.get("anon_phone"),
                anon_username=pdata.get("anon_username"),
                anon_signature=pdata.get("anon_signature"),
                anon_street=pdata.get("anon_street"),
                anon_postal=pdata.get("anon_postal"),
                anon_city=pdata.get("anon_city"),
                comvius_id=pdata.get("comvius_id"),
                user_id=pdata.get("user_id"),
            )
            reg.persons[key] = p
            if p.comvius_id:
                reg._comvius_index[str(p.comvius_id)] = key
            if p.user_id:
                reg._user_id_index[str(p.user_id)] = key
        reg._email_index = data.get("email_index", {})
        # Rebuild PNR index from pnr_index data
        for norm_pnr, _ in data.get("pnr_index", {}).items():
            # Find person by scanning (PNR stored in anon form only in mapping)
            # We need original PNR -> person key, which we stored in pnr_index
            pass
        # Store raw pnr mapping for direct lookups
        reg._raw_pnr_map = data.get("pnr_index", {})
        return reg

    def get_pnr_mapping(self) -> dict[str, str]:
        """Return {original_normalized_pnr: anonymized_pnr}."""
        result = {}
        for norm_pnr, pkey in self._pnr_index.items():
            p = self.persons[pkey]
            if p.anon_pnr:
                result[norm_pnr] = p.anon_pnr
        return result

    def get_full_name_mapping(self) -> dict[str, str]:
        """Return {original_full_name: anonymized_full_name} for all persons."""
        result = {}
        for p in self.persons.values():
            if p.first_name and p.last_name:
                orig = f"{p.first_name} {p.last_name}"
                anon = f"{p.anon_first} {p.anon_last}"
                result[orig] = anon
        return result

    @staticmethod
    def _guess_gender(first_name: str) -> Optional[str]:
        """Guess gender from Swedish first name ending (heuristic)."""
        name = first_name.strip()
        if not name:
            return None
        if name.endswith(("a", "e")) and not name.endswith(("ste", "ke", "ge")):
            return "Kvinna"
        return "Man"

    @staticmethod
    def _normalize_gender(gender: Optional[str]) -> Optional[str]:
        if not gender:
            return None
        g = gender.strip().lower()
        if g in ("flicka", "f", "kvinna", "female", "woman"):
            return "Kvinna"
        if g in ("pojke", "m", "man", "male", "boy"):
            return "Man"
        return None


class NameScrubber:
    """Replaces real names in free text with anonymized equivalents."""

    def __init__(self, registry: PersonRegistry):
        self._replacements: list[tuple[re.Pattern, str]] = []
        self._build(registry)

    def _build(self, registry: PersonRegistry) -> None:
        """Build replacement patterns from the registry."""
        pairs: dict[str, str] = {}

        # Full names (highest priority — longest match first)
        for p in registry.persons.values():
            if p.first_name and p.last_name and p.anon_first and p.anon_last:
                orig_full = f"{p.first_name} {p.last_name}"
                anon_full = f"{p.anon_first} {p.anon_last}"
                if orig_full != anon_full:
                    pairs[orig_full] = anon_full

        # Individual last names (useful for "familjen Andersson" etc.)
        for p in registry.persons.values():
            if p.last_name and p.anon_last and p.last_name != p.anon_last:
                if p.last_name not in pairs:
                    pairs[p.last_name] = p.anon_last

        # Individual first names — only distinctive ones (skip very short/common)
        common_words = {
            "Per", "Eva", "Bo", "Åsa", "Åke", "Ulf", "Ali", "Pia",
            "Ann", "Jan", "Ida", "Ola", "Tor",
        }
        for p in registry.persons.values():
            if (p.first_name and p.anon_first
                    and p.first_name != p.anon_first
                    and len(p.first_name) >= 4
                    and p.first_name not in common_words
                    and p.first_name not in pairs):
                pairs[p.first_name] = p.anon_first

        # School name replacements
        pairs["Carlssons"] = "Demoskolan"
        pairs["carlssons"] = "demoskolan"
        pairs["Carlssonsskola"] = "Demoskolan"
        pairs["carlssonsskola"] = "demoskolan"
        pairs["carlssonsskola.se"] = "demoskolan.se"

        # Sort by length descending so "Anna Karlsson" matches before "Anna"
        sorted_pairs = sorted(pairs.items(), key=lambda x: len(x[0]), reverse=True)

        for real, fake in sorted_pairs:
            try:
                pattern = re.compile(re.escape(real), re.IGNORECASE)
                self._replacements.append((pattern, fake))
            except re.error:
                continue

    def scrub(self, text: str) -> str:
        """Replace all occurrences of real names with fake names."""
        if not text:
            return text
        for pattern, replacement in self._replacements:
            text = pattern.sub(replacement, text)
        return text
