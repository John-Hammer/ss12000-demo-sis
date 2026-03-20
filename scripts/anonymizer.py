"""
Deterministic field-level anonymization functions.
All functions are hash-seeded so re-running produces identical output.
"""
import hashlib
import uuid
from typing import Optional

from .swedish_names import (
    MALE_FIRST_NAMES, FEMALE_FIRST_NAMES, LAST_NAMES,
    STREET_NAMES, POSTAL_CODE_CITY,
)

# Namespace UUID for deterministic UUID5 generation
SEED_NAMESPACE = uuid.UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")


def _hash_index(seed: int, key: str, pool_size: int) -> int:
    """Get a deterministic index into a pool based on seed + key."""
    h = hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()
    return int(h, 16) % pool_size


def _hash_digits(seed: int, key: str, count: int) -> str:
    """Generate deterministic digits from seed + key."""
    h = hashlib.sha256(f"{seed}:{key}:digits".encode()).hexdigest()
    # Convert hex to decimal digits
    num = int(h, 16)
    digits = ""
    for _ in range(count):
        digits += str(num % 10)
        num //= 10
    return digits


def make_uuid(seed: int, entity_type: str, original_id: str) -> str:
    """Generate a deterministic UUID5 from entity type and original ID."""
    ns = uuid.uuid5(SEED_NAMESPACE, str(seed))
    return str(uuid.uuid5(ns, f"{entity_type}:{original_id}"))


def anonymize_first_name(seed: int, original_id: str, gender: Optional[str] = None) -> str:
    """Anonymize a first name using gender-aware Swedish name pool."""
    # Determine gender pool
    if gender and gender.lower() in ("kvinna", "f", "female", "flicka"):
        pool = FEMALE_FIRST_NAMES
    elif gender and gender.lower() in ("man", "m", "male", "pojke"):
        pool = MALE_FIRST_NAMES
    else:
        # Mix both pools for unknown gender
        pool = MALE_FIRST_NAMES + FEMALE_FIRST_NAMES

    idx = _hash_index(seed, f"first:{original_id}", len(pool))
    return pool[idx]


def anonymize_last_name(seed: int, original_id: str) -> str:
    """Anonymize a last name using Swedish name pool."""
    idx = _hash_index(seed, f"last:{original_id}", len(LAST_NAMES))
    return LAST_NAMES[idx]


def anonymize_personnummer(seed: int, original_id: str, original_pnr: Optional[str]) -> Optional[str]:
    """
    Anonymize a Swedish personnummer.
    Keeps birth date portion (YYMMDD or YYYYMMDD), scrambles last 4 digits.
    """
    if not original_pnr:
        return None

    # Strip whitespace
    pnr = original_pnr.strip()
    if not pnr:
        return None

    # Parse: could be YYMMDD-XXXX or YYYYMMDD-XXXX
    if "-" in pnr:
        date_part, _ = pnr.split("-", 1)
        sep = "-"
    elif len(pnr) >= 10:
        date_part = pnr[:-4]
        sep = "-"
    else:
        return None

    # Generate new last 4 digits
    new_digits = _hash_digits(seed, f"pnr:{original_id}", 4)
    return f"{date_part}{sep}{new_digits}"


def anonymize_email_staff(seed: int, anon_first: str, anon_last: str) -> str:
    """Generate anonymized staff email."""
    first = anon_first.lower().replace(" ", "").replace("-", "")
    last = anon_last.lower().replace(" ", "").replace("-", "")
    # Handle Swedish chars
    for old, new in [("å", "a"), ("ä", "a"), ("ö", "o"), ("é", "e"), ("ü", "u")]:
        first = first.replace(old, new)
        last = last.replace(old, new)
    return f"{first}.{last}@demoskolan.se"


def anonymize_email_student(seed: int, anon_first: str, anon_last: str) -> str:
    """Generate anonymized student email."""
    first = anon_first.lower().replace(" ", "").replace("-", "")[:3]
    last = anon_last.lower().replace(" ", "").replace("-", "")[:3]
    for old, new in [("å", "a"), ("ä", "a"), ("ö", "o"), ("é", "e"), ("ü", "u")]:
        first = first.replace(old, new)
        last = last.replace(old, new)
    return f"{first}{last}@student.demoskolan.se"


def anonymize_email_guardian(seed: int, anon_first: str, anon_last: str) -> str:
    """Generate anonymized guardian email."""
    first = anon_first.lower().replace(" ", "").replace("-", "")
    last = anon_last.lower().replace(" ", "").replace("-", "")
    for old, new in [("å", "a"), ("ä", "a"), ("ö", "o"), ("é", "e"), ("ü", "u")]:
        first = first.replace(old, new)
        last = last.replace(old, new)
    return f"{first}.{last}@example.se"


def anonymize_phone(seed: int, original_id: str) -> str:
    """Generate anonymized Swedish mobile number."""
    d = _hash_digits(seed, f"phone:{original_id}", 8)
    prefix = _hash_index(seed, f"phone_prefix:{original_id}", 8) + 70  # 070-078
    return f"0{prefix}-{d[:3]} {d[3:5]} {d[5:7]}"


def anonymize_address(seed: int, original_id: str) -> tuple[str, str, str]:
    """
    Generate anonymized Swedish street address.
    Returns (street_address, postal_code, city).
    """
    street_idx = _hash_index(seed, f"street:{original_id}", len(STREET_NAMES))
    house_num = _hash_index(seed, f"house:{original_id}", 120) + 1
    pc_idx = _hash_index(seed, f"postal:{original_id}", len(POSTAL_CODE_CITY))

    street = f"{STREET_NAMES[street_idx]} {house_num}"
    postal_code, city = POSTAL_CODE_CITY[pc_idx]
    return street, postal_code, city


def anonymize_signature(anon_last_name: str) -> str:
    """Generate signature from anonymized last name (first 3 chars, uppercased)."""
    clean = anon_last_name.replace(" ", "").replace("-", "")
    return clean[:3].upper()


def anonymize_username(seed: int, anon_first: str, anon_last: str) -> str:
    """Generate anonymized username (first 3 of first + first 3 of last)."""
    first = anon_first.lower().replace(" ", "").replace("-", "")[:3]
    last = anon_last.lower().replace(" ", "").replace("-", "")[:3]
    for old, new in [("å", "a"), ("ä", "a"), ("ö", "o"), ("é", "e"), ("ü", "u")]:
        first = first.replace(old, new)
        last = last.replace(old, new)
    return f"{first}{last}"
