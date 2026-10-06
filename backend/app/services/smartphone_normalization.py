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
    ("VGOTEL", ("vgotel", "vgo tel")),
)


_BRAND_TOKENS: frozenset[str] = frozenset(
    token
    for _, aliases in BRAND_ALIASES
    for alias in aliases
    for token in alias.split()
)


# Words that only ever describe a shop or a sales pitch, never a phone.
# Daraz sellers prefix their store onto every title they publish
# ("Carrefour Samsung Galaxy A07 4+128GB Green-303662"), which reads as a
# different product from the same phone sold elsewhere.
STORE_NAME_WORDS: frozenset[str] = frozenset(
    {
        "accessories", "brand", "center", "centre", "co", "collection",
        "company", "corner", "deal", "deals", "digital", "electronic",
        "electronics", "enterprise", "enterprises", "flagship", "gadget",
        "gadgets", "gallery", "genuine", "house", "hub", "inc",
        "international", "ltd", "mall", "mart", "mobile", "mobiles",
        "official", "officials", "online", "original", "pakistan", "pk",
        "point", "pvt", "retail", "retailer", "sales", "seller", "shop",
        "shoppe", "shopping", "shops", "store", "stores", "tech",
        "technologies", "technology", "telecom", "trader", "traders",
        "trading", "world", "zone",
    }
)


# A marketplace stock code glued to the end of a title
# ("...Green-303662", "...Gold (306237)"). A four-digit model year
# such as "Nokia 130 (2023)" is part of the phone's name, not a code.
_STOCK_CODE = r"[a-z]{0,3}(?!(?:19|20)\d{2}\b)\d{4,}"

_TRAILING_STOCK_CODE = re.compile(
    r"[\s,:;|/]*(?:"
    rf"[-–—_]\s*{_STOCK_CODE}"
    rf"|\(\s*(?:sku[\s:#-]*)?{_STOCK_CODE}\s*\)"
    rf"|\[\s*(?:sku[\s:#-]*)?{_STOCK_CODE}\s*\]"
    r")\s*$",
    re.I,
)

_TRAILING_SEPARATORS = " -–—_|/,;:."


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


# Words that mark a value as the shop selling the phone rather than the
# company that made it. Daraz publishes the store in its ``brandName`` field
# ("OPPO Pakistan Official", "FAYWA TRADING (PVT) LTD", "Carrefour"), which
# filled the catalog's brand filter with sellers. "Mobile" is deliberately
# absent: it is part of real brand names such as "me Mobile".
BRAND_RESELLER_WORDS: frozenset[str] = frozenset(
    {
        "co", "collection", "corner", "enterprise", "enterprises",
        "flagship", "gallery", "hub", "inc", "ltd", "mall", "mart",
        "official", "officials", "pvt", "retail", "retailer", "seller",
        "shop", "shops", "store", "stores", "trader", "traders", "trading",
    }
)


def canonical_brand_name(value: str | None) -> str | None:
    """Return the manufacturer a piece of text names, if it names one.

    Marketplaces spell one manufacturer many ways - "OPPO Pakistan
    Official", "vivo .", "Redmi", "FAYWA TRADING (PVT) LTD" - and each
    spelling used to become its own catalog brand.
    """

    normalized = f" {normalize_text(value)} "

    if normalized.strip() == "":
        return None

    for canonical, aliases in BRAND_ALIASES:
        if any(f" {alias} " in normalized for alias in aliases):
            return canonical

    return None


def looks_like_reseller(value: str | None) -> bool:
    """Report whether a brand value names a shop instead of a maker."""

    tokens = set(normalize_text(value).split())

    return bool(tokens & BRAND_RESELLER_WORDS)


def infer_brand_name(
    model: str | None,
    provided_brand: str | None = None,
) -> str | None:
    """Return the manufacturer behind a listing, never the seller.

    The marketplace's own brand field is trusted only once it is recognised
    as a manufacturer. Anything else falls back to the title, and a value
    that merely names a shop is dropped rather than registered as a brand.
    """

    cleaned_brand = meaningful_text(provided_brand, max_length=120)

    if cleaned_brand is not None:
        # Marketplaces decorate the field itself (".No Brand.", "vivo ."),
        # so placeholders are re-checked once the decoration is gone.
        cleaned_brand = cleaned_brand.strip(" .,-|/_").strip() or None
        if is_placeholder(cleaned_brand):
            cleaned_brand = None

    from_brand = canonical_brand_name(cleaned_brand)
    if from_brand is not None:
        return from_brand

    from_title = canonical_brand_name(model)
    if from_title is not None:
        return from_title

    if cleaned_brand is None or looks_like_reseller(cleaned_brand):
        return None

    return cleaned_brand[:120]


def _comparison_token(token: object) -> str:
    """Fold one title token to the letters and digits used for comparison."""

    return re.sub(r"[^a-z0-9]+", "", str(token).lower())


def _store_name_tokens(seller_name: str | None) -> list[str]:
    """Return the identifying words of a seller's store name.

    "Carrefour Pakistan" identifies itself as "carrefour"; a store called
    "Mobile Zone" has nothing but shop words, so all of them are kept.
    """

    tokens = [
        token
        for token in (
            _comparison_token(part)
            for part in str(seller_name or "").split()
        )
        if token
    ]
    identifying = [
        token for token in tokens if token not in STORE_NAME_WORDS
    ]

    return identifying or tokens


def _strip_store_prefix(
    tokens: list[str],
    store_tokens: list[str],
) -> list[str]:
    """Drop a leading store name from a marketplace title's tokens.

    Sellers spell their own name inconsistently across their listings
    ("AL Fatah" and "AL-Fatah"), so the leading tokens are compared with the
    store name as one run of letters and digits. A brand token is never
    consumed: a store called "Samsung Official Store" must not eat the
    "Samsung" that identifies the phone.
    """

    target = "".join(store_tokens)

    if not target:
        return tokens

    matched = ""
    index = 0

    while index < len(tokens) and matched != target:
        token = _comparison_token(tokens[index])

        if not token:
            index += 1
            continue

        if token in _BRAND_TOKENS:
            break

        if target.startswith(matched + token):
            matched += token
            index += 1
        elif matched and token in STORE_NAME_WORDS:
            index += 1
        else:
            break

    if matched != target:
        return tokens

    while (
        index < len(tokens)
        and _comparison_token(tokens[index]) in STORE_NAME_WORDS
    ):
        index += 1

    remainder = tokens[index:]

    return remainder if len(remainder) >= 2 else tokens


def _strip_store_word_prefix(tokens: list[str]) -> list[str]:
    """Drop leading shop words when a real phone brand follows them."""

    index = 0

    while (
        index < len(tokens)
        and index < 3
        and _comparison_token(tokens[index]) in STORE_NAME_WORDS
    ):
        index += 1

    if not index:
        return tokens

    remainder = tokens[index:]

    if len(remainder) < 2 or not any(
        _comparison_token(token) in _BRAND_TOKENS for token in remainder
    ):
        return tokens

    return remainder


def clean_marketplace_title(
    title: str | None,
    seller_name: str | None = None,
) -> str:
    """Return a marketplace title reduced to the product it describes.

    Removes the seller's store name and the stock code Daraz glues to the
    end, so "Carrefour Samsung Galaxy A07 4+128GB Green-303662" becomes
    "Samsung Galaxy A07 4+128GB Green". Both marketplaces must reduce the
    same phone to the same text or it is registered twice. The original
    title is returned whenever cleaning would leave too little to identify a
    phone.
    """

    original = " ".join(str(title or "").split())

    if not original:
        return original

    cleaned = original

    for _ in range(2):
        shortened = _TRAILING_STOCK_CODE.sub("", cleaned)
        if shortened == cleaned:
            break
        cleaned = shortened.strip(_TRAILING_SEPARATORS)

    tokens = cleaned.split()
    tokens = _strip_store_prefix(tokens, _store_name_tokens(seller_name))
    tokens = _strip_store_word_prefix(tokens)

    cleaned = " ".join(" ".join(tokens).strip(_TRAILING_SEPARATORS).split())

    if len(cleaned) < 3 or not re.search(r"[a-z]", cleaned, re.I):
        return original

    return cleaned


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


# The Daraz smartphones category page also serves cables, chargers,
# covers and screen protectors. Taken at face value they became
# canonical products or filled the pending-match queue with items no
# administrator will ever map to a phone.
# The marketplace smartphones category also serves cables, chargers,
# covers and screen protectors, which reached the catalog as products.
# Some words never appear in a phone's own title. Others do, because a
# phone's copy says what is in the box ("with Free Powerbank", "Box
# Charger") or which accessories it supports ("Memory Card Support",
# "+SD Card Supported"). Those are read as an accessory only when no
# inclusion wording sits in front of them and no support wording
# follows, so a phone that advertises its bundled charger stays a
# phone.
HARD_ACCESSORY_PATTERN = re.compile(
    "|".join(
        (
            r"\botg\b",
            r"\bstickers?\b",
            r"\bselfie\s+stick\b",
            r"\btripod\b",
            r"\bring\s+light\b",
            r"\bsim\s+(?:ejector|tray)\b",
            r"\bcamera\s+lens\s+protector\b",
            r"\bwatch\s+strap\b",
            r"\bpack\s+of\s+\d+\b",
            r"\bspeaker\s+mesh\b",
            r"\bdust\s*proof\b",
            r"\bfaucet\b",
            r"\bkeyboard\b",
            r"\bmouse\b",
            r"\bneckband\b",
            r"\bairpods?\b",
        )
    ),
    re.I,
)

SOFT_ACCESSORY_PATTERN = re.compile(
    "|".join(
        (
            r"\bcables?\b",
            r"\bchargers?\b",
            r"\bcharging\s+(?:adapter|brick|dock|pad|station)\b",
            r"\badapter\b",
            r"\bconverter\b",
            r"\bpower\s*bank\b",
            r"\bmemory\s+card\b",
            r"\bsd\s+card\b",
            r"\bback\s*cover\b",
            r"\bphone\s+case\b",
            r"\bcover\s+for\b",
            r"\bpouch\b",
            r"\btempered\s+glass\b",
            r"\bscreen\s+(?:protector|guard)\b",
            r"\bprotector\s+(?:pack|film)\b",
            r"\bear\s*(?:buds?|phones?)\b",
            r"\bhead\s*(?:phones?|sets?)\b",
            r"\bhands?\s*free\b",
            r"\bcar\s+(?:holder|mount|charger)\b",
        )
    ),
    re.I,
)

# "Box Charger", "with Free Powerbank": the box, not the product.
ACCESSORY_INCLUSION_PATTERN = re.compile(
    r"(?:\b(?:free|with|incl|included|including|includes|bundle|bundled|box|boxed|plus|and|no|without|extra|gift)\b|[+&,])",
    re.I,
)

# "Memory Card Support": a feature of the phone, not the product.
ACCESSORY_FEATURE_PATTERN = re.compile(
    r"^\s*(?:supp\w*|slot|compatible|expandable|support\w*|included|option\w*|available|only)\b",
    re.I,
)

# How far either side of the keyword that wording may sit.
CONTEXT_WINDOW = 30


def is_accessory_title(title: str | None) -> bool:
    """Report whether a marketplace title describes an accessory."""

    text = " ".join(str(title or "").split())

    if not text:
        return False

    if HARD_ACCESSORY_PATTERN.search(text):
        return True

    for match in SOFT_ACCESSORY_PATTERN.finditer(text):
        before = text[max(0, match.start() - CONTEXT_WINDOW):match.start()]
        after = text[match.end():match.end() + CONTEXT_WINDOW]

        if ACCESSORY_INCLUSION_PATTERN.search(before):
            continue

        if ACCESSORY_FEATURE_PATTERN.search(after):
            continue

        return True

    return False

    if HARD_ACCESSORY_PATTERN.search(text):
        return True

    for match in SOFT_ACCESSORY_PATTERN.finditer(text):
        context = text[max(0, match.start() - CONTEXT_WINDOW):match.start()]

        if not ACCESSORY_INCLUSION_PATTERN.search(context):
            return True

    return False


# A product *name* is a short identity string, not marketing copy, so
# signals that would be ambiguous inside a listing title are decisive
# here: a phone is not named after its wattage or its charging
# standard, but a charger is ("Original Samsung 45W PD UK Pin PPS Super
# Fast GaN").
ACCESSORY_NAME_PATTERN = re.compile(
    "|".join(
        (
            r"\b\d{1,3}\s*w\b",
            r"\bgan\b",
            r"\buk\s+pin\b",
            r"\busb\b",
            r"\btype[-\s]?c\b",
        )
    ),
    re.I,
)


# Beyond this length a "name" is marketing copy that was never shortened,
# and a phone's copy legitimately mentions USB-C or 15W charging.
MAX_IDENTITY_NAME_LENGTH = 60


def is_accessory_product_name(name: str | None) -> bool:
    """Report whether a catalog product name describes an accessory."""

    text = " ".join(str(name or "").split())

    if not text:
        return False

    if is_accessory_title(text):
        return True

    if len(text) > MAX_IDENTITY_NAME_LENGTH:
        return False

    return bool(ACCESSORY_NAME_PATTERN.search(text))


# --------------------------------------------------------------------------
# Catalog display names and colours read out of seller titles
# --------------------------------------------------------------------------

# Where a seller title stops naming the phone and starts describing it.
_NAME_BOUNDARY = re.compile(
    r"(?:\b\d{1,4}\s*(?:gb|tb|mah|mp|hz|w)\b"
    r"|\b\d{1,2}\s*[+/]\s*\d{1,4}\b"
    r"|[,|(\[*\u2013\u2014]"
    r"|\s-\s"
    r"|\b(?:and get|with free|free gift|pta approved|official warranty)\b)",
    re.I,
)

_GENERIC_PRODUCT_NOUNS = re.compile(
    r"\b(?:mobiles?|smart\s*phones?|cell\s*phones?|handsets?)\b",
    re.I,
)

_LEADING_PROMOTION = re.compile(
    r"^\s*(?:buy now|new arrival|hot sale|flash sale|special offer)\b[\s:!-]*",
    re.I,
)

BASE_HUES = frozenset({
    "black", "white", "blue", "red", "green", "gold", "silver", "grey",
    "gray", "pink", "purple", "yellow", "orange", "brown", "violet", "cyan",
    "beige", "bronze", "copper", "maroon", "teal", "turquoise", "indigo",
    "magenta", "lavender", "lilac", "golden",
})

HUE_MODIFIERS = frozenset({
    "dark", "light", "deep", "sky", "midnight", "navy", "lime", "mint",
    "rose", "olive", "ocean", "aqua", "space", "jet", "matte", "pearl",
    "royal", "ice", "forest", "sunset", "starry", "titanium", "awesome",
    "phantom", "mystic", "cosmic", "glacier", "aurora", "racing",
})

_TITLE_COLOUR = re.compile(
    r"\b(?:(" + "|".join(sorted(HUE_MODIFIERS)) + r")\s+)?("
    + "|".join(sorted(BASE_HUES)) + r")\b",
    re.I,
)


def detect_title_color(title: str | None) -> str | None:
    """Return the colour a seller wrote into a title, if exactly one.

    A Daraz listing has no colour field, but sellers often end the title
    with it ("Samsung Galaxy A17 6+128 Blue"). A title naming two hues is a
    multi-colour listing and names none of them.
    """

    found = {
        " ".join(part for part in match.groups() if part).title()
        for match in _TITLE_COLOUR.finditer(str(title or ""))
    }
    hues = {name.split()[-1].lower() for name in found}

    if len(hues) != 1:
        return None

    # "Midnight Black" over plain "Black" when a title states both forms.
    return max(found, key=len)


def clean_model_name(title: str | None, brand_name: str | None = None) -> str:
    """Return the name a phone should carry in the catalog.

    The catalog names the phone; memory, colour, the seller's selling
    points and filler nouns belong to a variant or to nobody. "NOTE X 6+128
    BLACK SPARX" is the "Sparx Note X", and "Tecno Mobile Spark 40" is the
    "Tecno Spark 40". Returns the input, tidied, when nothing safer can be
    derived from it.
    """

    original = " ".join(str(title or "").split())

    if not original:
        return original

    name = _LEADING_PROMOTION.sub("", original)
    boundary = _NAME_BOUNDARY.search(name)

    if boundary is not None and boundary.start() >= 3:
        name = name[:boundary.start()]

    name = _GENERIC_PRODUCT_NOUNS.sub(" ", name)
    tokens = [token.strip(" -|=,;:.") for token in name.split()]
    tokens = [token for token in tokens if token]

    # A trailing colour describes one variant, not the phone.
    while len(tokens) > 2 and tokens[-1].lower() in (
        BASE_HUES | HUE_MODIFIERS
    ):
        tokens.pop()

    brand = " ".join(str(brand_name or "").split())
    brand_tokens = [part.lower() for part in brand.split()]

    if brand_tokens:
        lowered = [token.lower() for token in tokens]
        width = len(brand_tokens)
        # Keep the brand once, at the front, in the catalog's spelling.
        kept: list[str] = []
        index = 0
        while index < len(tokens):
            if lowered[index:index + width] == brand_tokens:
                index += width
                continue
            kept.append(tokens[index])
            index += 1
        tokens = brand.split() + kept

    def tidy(token: str) -> str:
        if not token.isalpha() or len(token) < 2:
            return token
        if token.isupper() and len(token) > 3:
            return token.capitalize()
        if token.islower():
            return token.capitalize()
        return token

    protected = len(brand_tokens)
    tokens = tokens[:protected] + [tidy(token) for token in tokens[protected:]]
    cleaned = " ".join(tokens)

    if len(tokens) < 2 or not re.search(r"[a-z]", cleaned, re.I):
        return original

    return cleaned
