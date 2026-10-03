"""Shared smartphone brand, model and specification normalization.

Both the legacy ``/ingest`` route and the active internal acquisition
pipeline normalize the same marketplace vocabulary, so the rules live here
once. Daraz and PriceOye spell the same facts very differently
("8 GB", "8GB RAM", "RAM: 8 GB", "256GB ROM"), and product matching is only
as accurate as this layer.
"""

from __future__ import annotations

import re
import unicodedata


BRAND_ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Samsung", ("samsung", "galaxy")),
    ("Apple", ("apple", "iphone")),
    ("Xiaomi", ("xiaomi", "redmi", "poco")),
    ("Infinix", ("infinix",)),
    ("Tecno", ("tecno",)),
    ("Oppo", ("oppo",)),
    ("Vivo", ("vivo",)),
    ("Realme", ("realme",)),
    ("OnePlus", ("oneplus", "one plus")),
    ("Huawei", ("huawei",)),
    ("Honor", ("honor",)),
    ("Nokia", ("nokia",)),
    ("Google", ("google pixel", "pixel")),
    ("Motorola", ("motorola", "moto")),
    ("Itel", ("itel",)),
    ("Sparx", ("sparx",)),
    ("Dcode", ("dcode", "d-code")),
    ("QMobile", ("qmobile", "q mobile")),
    ("Faywa", ("faywa",)),
    ("Nothing", ("nothing", "cmf phone")),
    ("Sego", ("sego",)),
    ("Villaon", ("villaon",)),
    ("LG", ("lg",)),
    ("Balmuda", ("balmuda",)),
    ("Sony", ("sony", "xperia")),
    ("Sharp", ("sharp", "aquos")),
    ("ZTE", ("zte", "nubia")),
    ("VGOTEL", ("vgotel",)),
)


PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "-",
        "--",
        "n/a",
        "na",
        "n.a",
        "none",
        "null",
        "nil",
        "unknown",
        "not available",
        "not specified",
        "no brand",
        "unbranded",
        "standard",
        "tbd",
        "?",
    }
)


# Canonical specification keys, with every marketplace spelling that maps
# onto them. Daraz publishes "Internal Memory"/"RAM" inside one packed
# description string; PriceOye publishes table rows with its own labels.
SPEC_KEY_ALIASES: dict[str, tuple[str, ...]] = {
    "ram": (
        "ram",
        "ram_capacity",
        "memory_ram",
        "memory",
    ),
    "storage_capacity": (
        "storage_capacity",
        "storage",
        "rom",
        "internal_memory",
        "internal_storage",
        "built_in_storage",
        "built_in_memory",
    ),
    "battery_capacity": (
        "battery_capacity",
        "battery",
        "battery_type",
        "battery_capacity_mah",
    ),
    "display": (
        "display",
        "screen_size",
        "display_size",
        "screen",
    ),
    "display_resolution": (
        "display_resolution",
        "screen_resolution",
        "resolution",
    ),
    "display_type": (
        "display_type",
        "screen_type",
        "panel_type",
    ),
    "chipset": (
        "chipset",
        "processor",
        "cpu",
        "soc",
    ),
    "gpu": ("gpu", "graphics"),
    "operating_system": (
        "operating_system",
        "os",
        "software",
    ),
    "front_camera": (
        "front_camera",
        "selfie_camera",
        "front_cam",
    ),
    "back_camera": (
        "back_camera",
        "rear_camera",
        "main_camera",
        "primary_camera",
        "back_cam",
    ),
    "network": (
        "network",
        "network_technology",
        "5g",
        "4g_lte",
        "connectivity_network",
    ),
    "sim": ("sim", "sim_support", "sim_slots", "card_slot"),
    "color": ("color", "colour", "color_family"),
    "release_date": ("release_date", "released", "announced"),
    "weight": ("weight", "phone_weight"),
    "dimensions": ("dimensions", "phone_dimensions"),
    "charging": ("charging", "fast_charging", "charger"),
    "nfc": ("nfc",),
    "bluetooth": ("bluetooth",),
    "wifi": ("wifi", "wi_fi"),
    "pta_status": ("pta_status", "pta", "pta_approved"),
    "warranty": ("warranty",),
}


_ALIAS_TO_CANONICAL_KEY: dict[str, str] = {
    alias: canonical_key
    for canonical_key, aliases in SPEC_KEY_ALIASES.items()
    for alias in aliases
}


def normalize_spec_key(label: object) -> str:
    """Return a compact ``snake_case`` specification key."""

    key = re.sub(
        r"[^a-z0-9]+",
        "_",
        str(label or "").strip().lower(),
    ).strip("_")

    return key[:80]


def canonical_spec_key(label: object) -> str:
    """Map a marketplace specification label onto a canonical key."""

    key = normalize_spec_key(label)

    return _ALIAS_TO_CANONICAL_KEY.get(key, key)


def is_placeholder(value: object) -> bool:
    """Report whether a scraped value carries no real information."""

    if value is None:
        return True

    if isinstance(value, bool):
        return False

    return str(value).strip().lower() in PLACEHOLDER_VALUES


def meaningful_text(value: object, *, max_length: int = 2000) -> str | None:
    """Return trimmed text, or ``None`` for marketplace placeholders."""

    if is_placeholder(value):
        return None

    return " ".join(str(value).split())[:max_length]


def normalize_text(value: object) -> str:
    """Fold text to lowercase ASCII words for identity comparisons."""

    if value is None:
        return ""

    normalized = unicodedata.normalize("NFKD", str(value))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized.lower())

    return " ".join(normalized.split())


def infer_brand_name(
    model: str | None,
    provided_brand: str | None = None,
) -> str | None:
    """Normalize an explicit brand or infer a known brand from a title."""

    cleaned_brand = meaningful_text(provided_brand, max_length=120)
    if cleaned_brand is not None:
        return cleaned_brand

    normalized_model = f" {str(model or '').lower()} "

    for canonical_name, aliases in BRAND_ALIASES:
        if any(
            re.search(
                rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])",
                normalized_model,
            )
            for alias in aliases
        ):
            return canonical_name

    return None


def capacity_gb(value: object) -> int | None:
    """Extract a RAM/storage capacity in GB from free marketplace text.

    Handles ``8GB``, ``8 GB``, ``8 gb RAM``, ``256GB ROM`` and ``1TB``, and
    ignores extended/virtual RAM claims such as ``3GB+5GB Extended RAM``
    beyond their physical first value.
    """

    text = meaningful_text(value, max_length=200)
    if text is None:
        return None

    match = re.search(r"(\d{1,4})\s*(gb|tb)\b", text, re.I)
    if match is None:
        return None

    capacity = int(match.group(1))
    if match.group(2).lower() == "tb":
        capacity *= 1024

    if capacity <= 0 or capacity > 8192:
        return None

    return capacity


def format_capacity(capacity: int | None) -> str | None:
    """Render a GB capacity using one consistent display form."""

    if capacity is None or capacity <= 0:
        return None

    if capacity >= 1024 and capacity % 1024 == 0:
        return f"{capacity // 1024}TB"

    return f"{capacity}GB"


def normalize_color(value: object) -> str | None:
    """Return a title-cased marketplace colour, or ``None``."""

    text = meaningful_text(value, max_length=80)
    if text is None:
        return None

    # Marketplace colour pickers sometimes carry the memory option in the
    # same list ("256GB - 8GB RAM"); that is a variant, not a colour.
    if re.search(r"\d\s*(gb|tb)\b", text, re.I):
        return None

    return text.title()[:80]


_TITLE_SPEC_PATTERNS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    (
        "ram",
        (
            r"\b(\d{1,2})\s*GB\s*RAM\b",
            r"\bRAM\s*[:\-]?\s*(\d{1,2})\s*GB\b",
        ),
        "GB",
    ),
    (
        "storage_capacity",
        (
            r"\b(\d{2,4})\s*GB\s*(?:ROM|Storage|Memory)\b",
            r"\b(?:ROM|Storage|Memory)\s*[:\-]?\s*(\d{2,4})\s*GB\b",
        ),
        "GB",
    ),
    ("battery_capacity", (r"\b(\d{3,5})\s*mAh\b",), " mAh"),
    (
        "display",
        (
            r"\b(\d{1,2}(?:\.\d{1,2})?)\s*"
            r"(?:inches|inch|\")\s*(?:display|screen)?",
        ),
        " inches",
    ),
    (
        "front_camera",
        (
            r"\b(\d{1,3})\s*MP\s*Front\s*Camera\b",
            r"\bFront\s*Camera\s*[:\-]?\s*(\d{1,3})\s*MP\b",
        ),
        "MP",
    ),
)


def infer_title_specifications(model: str | None) -> dict[str, str]:
    """Extract common technical values embedded in marketplace titles."""

    title = str(model or "")
    inferred: dict[str, str] = {}

    for key, patterns, suffix in _TITLE_SPEC_PATTERNS:
        for pattern in patterns:
            match = re.search(pattern, title, re.I)
            if match:
                inferred[key] = f"{match.group(1)}{suffix}"
                break

    capacity_pair = re.search(
        r"\b(\d{1,2})\s*(?:GB)?\s*[/+|]\s*(\d{2,4})\s*GB\b",
        title,
        re.I,
    )
    if capacity_pair:
        inferred.setdefault("ram", f"{capacity_pair.group(1)}GB")
        inferred.setdefault(
            "storage_capacity",
            f"{capacity_pair.group(2)}GB",
        )

    storage_options = list(
        dict.fromkeys(
            match.group(1)
            for match in re.finditer(r"\b(\d{2,4})\s*GB\b", title, re.I)
            if int(match.group(1)) >= 32
        )
    )
    if storage_options:
        inferred.setdefault(
            "storage_options",
            ", ".join(f"{value}GB" for value in storage_options),
        )
    if re.search(r"\bPTA\s*Approved\b", title, re.I):
        inferred.setdefault("pta_status", "PTA Approved")
    if re.search(r"\bDual\s*SIM\b|\b2\s*SIM\b", title, re.I):
        inferred.setdefault("sim", "Dual SIM")
    if re.search(r"\bType[ -]?C\b|\bUSB[ -]?C\b", title, re.I):
        inferred.setdefault("charging", "USB Type-C")
    if re.search(r"\bBluetooth\b", title, re.I):
        inferred.setdefault("connectivity", "Bluetooth")

    warranty = re.search(r"\b(\d+\s*Year\s*Warranty)\b", title, re.I)
    if warranty:
        inferred.setdefault("warranty", warranty.group(1))

    return inferred


def normalize_specifications(
    specifications: dict[str, object] | None,
) -> dict[str, str]:
    """Map scraped label/value pairs onto canonical keys and values.

    Keys are folded through :data:`SPEC_KEY_ALIASES`, placeholder values are
    dropped, and RAM/storage capacities are rewritten to one display form so
    ``8 GB`` and ``8GB RAM`` cannot look like different variants.
    """

    normalized: dict[str, str] = {}

    for raw_label, raw_value in (specifications or {}).items():
        key = canonical_spec_key(raw_label)
        if not key:
            continue

        if isinstance(raw_value, (list, tuple, set)):
            value = ", ".join(
                str(part).strip()
                for part in raw_value
                if meaningful_text(part) is not None
            )
        else:
            value = raw_value

        text = meaningful_text(value)
        if text is None:
            continue

        if key in {"ram", "storage_capacity"}:
            text = format_capacity(capacity_gb(text)) or text

        normalized.setdefault(key, text)

    return normalized


def merge_specifications(
    existing: dict[str, object] | None,
    incoming: dict[str, object] | None,
) -> dict[str, str]:
    """Merge scraped specifications without losing good stored values.

    A new scrape that simply failed to read a field must never blank a
    specification VEXTRO already holds, so stored values win whenever the
    incoming value is missing or a placeholder.
    """

    merged = normalize_specifications(
        {
            key: value
            for key, value in (existing or {}).items()
        }
    )

    for key, value in normalize_specifications(incoming).items():
        merged[key] = value

    return merged


def extract_memory_capacities(
    *,
    specifications: dict[str, object] | None = None,
    title: str | None = None,
    variant: str | None = None,
) -> tuple[int | None, int | None]:
    """Derive ``(ram_gb, storage_gb)`` from the most reliable source first.

    Structured specifications outrank the title, because marketplace titles
    mix extended-RAM marketing with physical capacity.
    """

    normalized = normalize_specifications(specifications)

    ram_gb = capacity_gb(normalized.get("ram"))
    storage_gb = capacity_gb(normalized.get("storage_capacity"))

    combined_text = " ".join(
        part for part in (variant or "", title or "") if part
    )

    if ram_gb is None or storage_gb is None:
        title_specifications = infer_title_specifications(combined_text)

        if ram_gb is None:
            ram_gb = capacity_gb(title_specifications.get("ram"))

        if storage_gb is None:
            storage_gb = capacity_gb(
                title_specifications.get("storage_capacity")
            )

    if ram_gb is None or storage_gb is None:
        capacity_pair = re.search(
            r"\b(\d{1,3})\s*GB\s*(?:RAM)?\s*[-/+|]\s*(\d{2,4})\s*GB\b",
            combined_text,
            re.I,
        )
        if capacity_pair:
            ram_gb = ram_gb or int(capacity_pair.group(1))
            storage_gb = storage_gb or int(capacity_pair.group(2))

    # Guard against a storage figure being read as RAM and vice versa.
    if ram_gb is not None and ram_gb > 32:
        if storage_gb is None:
            ram_gb, storage_gb = None, ram_gb
        else:
            ram_gb = None

    if storage_gb is not None and storage_gb < 8:
        storage_gb = None

    return ram_gb, storage_gb
