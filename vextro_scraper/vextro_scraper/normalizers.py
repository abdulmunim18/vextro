"""Marketplace-specific text normalizers used by the smartphone spiders.

Daraz and PriceOye publish the same facts in different shapes. Daraz packs an
entire specification sheet into one unseparated string on each catalog item;
PriceOye publishes a JSON-LD ``Product`` block plus HTML tables. Turning both
into the same vocabulary is what makes product matching reliable, so the rules
live here rather than inside the spiders.
"""

import json
import re


# Daraz concatenates "<label><value>" pairs with no separator, grouped under
# section headers. Splitting on this vocabulary recovers the original pairs.
DARAZ_SPEC_SECTIONS = (
    "General Features",
    "Display",
    "Memory",
    "Performance",
    "Battery",
    "Camera",
    "Connectivity",
    "Design",
    "Other Features",
)

DARAZ_SPEC_LABELS = (
    "Release Date",
    "SIM Support",
    "Phone Dimensions",
    "Phone Weight",
    "Operating System",
    "Screen Size",
    "Screen Resolution",
    "Screen Type",
    "Screen Protection",
    "Internal Memory",
    "Card Slot",
    "RAM",
    "Processor",
    "GPU",
    "Front Camera",
    "Front Flash Light",
    "Front Video Recording",
    "Back Flash Light",
    "Back Camera",
    "Back Video Recording",
    "Bluetooth",
    "4G/LTE",
    "5G",
    "3G",
    "Radio",
    "WiFi",
    "NFC",
    "Type",
)


# Longest labels first so "Front Camera" is never split as "Type".
_DARAZ_TOKEN_PATTERN = re.compile(
    "|".join(
        re.escape(token)
        for token in sorted(
            DARAZ_SPEC_SECTIONS + DARAZ_SPEC_LABELS,
            key=len,
            reverse=True,
        )
    )
)

_PLACEHOLDER_VALUES = frozenset(
    {
        "",
        "-",
        "--",
        "n/a",
        "na",
        "none",
        "null",
        "unknown",
        "not available",
        "no brand",
        "unbranded",
        "standard",
        "yes",
        "no",
    }
)

PRICE_PATTERN = re.compile(
    r"(?:rs\.?|pkr)?\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)",
    re.I,
)


def optional_text(value, *, max_length=2000):
    """Return trimmed text, or ``None`` for marketplace placeholders."""

    if value is None:
        return None

    normalized = " ".join(str(value).split())

    if normalized.lower() in _PLACEHOLDER_VALUES:
        return None

    return normalized[:max_length]


def parse_price(value):
    """Return the first amount in a marketplace price string as a float.

    Daraz publishes ``"17499"`` and ``"Rs. 17,499"``; PriceOye publishes
    ``"Rs119,999"``. Returns ``None`` rather than a sentinel so the caller
    can treat a missing price as missing rather than as free.
    """

    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        amount = float(value)
        return amount if amount > 0 else None

    match = PRICE_PATTERN.search(str(value))

    if match is None:
        return None

    try:
        amount = float(match.group(1).replace(",", ""))
    except ValueError:
        return None

    return amount if amount > 0 else None


def parse_rating(value, *, maximum=5.0):
    """Return a marketplace rating inside ``0..maximum``, else ``None``."""

    text = optional_text(value, max_length=20)

    if text is None:
        return None

    try:
        rating = float(text)
    except ValueError:
        return None

    if rating <= 0 or rating > maximum:
        return None

    return round(rating, 2)


def parse_count(value):
    """Return a non-negative review/rating count, else ``None``."""

    text = optional_text(value, max_length=20)

    if text is None:
        return None

    digits = re.sub(r"[^\d]", "", text)

    if not digits:
        return None

    return int(digits)


def parse_daraz_specification_sheet(description):
    """Split one packed Daraz description string into label/value pairs.

    Daraz emits the whole sheet as
    ``"General FeaturesRelease Date05 Aug 2026SIM SupportDual Nano SIM..."``.
    Every section header and field label is known, so the text between one
    label and the next is that label's value.
    """

    if isinstance(description, (list, tuple)):
        description = " ".join(
            str(part) for part in description if part
        )

    text = optional_text(description, max_length=8000)

    if text is None:
        return {}

    matches = list(_DARAZ_TOKEN_PATTERN.finditer(text))

    if not matches:
        return {}

    specifications = {}

    for index, match in enumerate(matches):
        label = match.group(0)

        if label in DARAZ_SPEC_SECTIONS:
            continue

        value_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(text)
        )
        value = optional_text(text[match.end():value_end], max_length=300)

        if value is None:
            continue

        # "Type" only appears inside the Battery section on Daraz sheets.
        if label == "Type":
            label = "Battery Capacity"

        specifications.setdefault(label, value)

    return specifications


def extract_json_ld_products(page_source):
    """Yield every ``schema.org/Product`` object embedded in a page.

    PriceOye's product pages carry a JSON-LD ``Product`` block holding the
    current offer price, availability and the aggregate rating. It is the
    marketplace's own machine-readable statement of those facts, so it beats
    scraping presentation markup.
    """

    products = []

    for raw_block in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        page_source or "",
        re.S | re.I,
    ):
        try:
            parsed = json.loads(raw_block.strip())
        except (ValueError, TypeError):
            continue

        for candidate in parsed if isinstance(parsed, list) else [parsed]:
            if (
                isinstance(candidate, dict)
                and str(candidate.get("@type", "")).lower() == "product"
            ):
                products.append(candidate)

    return products


def json_ld_offer(product):
    """Return one ``Offer`` mapping from a JSON-LD product, if present."""

    offers = (product or {}).get("offers")

    if isinstance(offers, list):
        offers = next(
            (offer for offer in offers if isinstance(offer, dict)),
            None,
        )

    return offers if isinstance(offers, dict) else None


def json_ld_availability(product):
    """Return ``True``/``False`` for a JSON-LD availability, else ``None``."""

    offer = json_ld_offer(product)

    if offer is None:
        return None

    availability = optional_text(offer.get("availability"), max_length=120)

    if availability is None:
        return None

    normalized = availability.replace("\\/", "/").lower()

    if normalized.endswith("instock") or normalized.endswith("in stock"):
        return True

    if (
        "outofstock" in normalized
        or "soldout" in normalized
        or "discontinued" in normalized
    ):
        return False

    return None


# Daraz sellers prefix their own store name onto every listing title
# ("Carrefour Samsung Galaxy A07 4+128GB Green-303662"). The store name is
# not part of the phone's identity, so it has to come off before matching:
# a title carrying it reads as a different product from the same phone on
# PriceOye, and a canonical product created from it is a permanent duplicate.
BRAND_ALIASES = (
    ('Samsung', ('samsung', 'galaxy')),
    ('Apple', ('apple', 'iphone')),
    ('Xiaomi', ('xiaomi', 'redmi', 'poco')),
    ('Infinix', ('infinix',)),
    ('Tecno', ('tecno',)),
    ('Oppo', ('oppo',)),
    ('Vivo', ('vivo',)),
    ('Realme', ('realme',)),
    ('OnePlus', ('oneplus', 'one plus')),
    ('Huawei', ('huawei',)),
    ('Honor', ('honor',)),
    ('Nokia', ('nokia',)),
    ('Google', ('google pixel', 'pixel')),
    ('Motorola', ('motorola', 'moto')),
    ('Itel', ('itel',)),
    ('Sparx', ('sparx',)),
    ('Dcode', ('dcode', 'd-code')),
    ('QMobile', ('qmobile', 'q mobile')),
    ('Faywa', ('faywa',)),
    ('Nothing', ('nothing', 'cmf phone')),
    ('Sego', ('sego',)),
    ('Villaon', ('villaon',)),
    ('LG', ('lg',)),
    ('Balmuda', ('balmuda',)),
    ('Sony', ('sony', 'xperia')),
    ('Sharp', ('sharp', 'aquos')),
    ('ZTE', ('zte', 'nubia')),
    ('VGOTEL', ('vgotel', 'vgo tel')),
)


_BRAND_TOKENS = frozenset(
    token
    for _, aliases in BRAND_ALIASES
    for alias in aliases
    for token in alias.split()
)


# Words that only ever describe a shop or a sales pitch, never a phone.
# They are dropped from a seller name before it is compared with a title,
# and a title may start with them only when a real brand follows.
STORE_NAME_WORDS = frozenset(
    {
        'accessories', 'brand', 'center', 'centre', 'collection', 'company',
        'corner', 'co', 'deal', 'deals', 'digital', 'electronic',
        'electronics', 'enterprise', 'enterprises', 'flagship', 'gadget',
        'gadgets', 'gallery', 'genuine', 'house', 'hub', 'inc',
        'international', 'ltd', 'mall', 'mart', 'mobile', 'mobiles',
        'official', 'officials', 'online', 'original', 'pakistan', 'pk',
        'point', 'pvt', 'retail',
        'retailer', 'sales', 'seller', 'shop', 'shoppe', 'shopping', 'shops',
        'store', 'stores', 'tech', 'technologies', 'technology', 'telecom',
        'trader', 'traders', 'trading', 'world', 'zone',
    }
)


# A marketplace stock code glued to the end of a title
# ("...Green-303662", "...Gold (306237)"). A four-digit model year
# such as "Nokia 130 (2023)" is part of the phone's name, not a code.
_STOCK_CODE = r'[a-z]{0,3}(?!(?:19|20)\d{2}\b)\d{4,}'

_TRAILING_STOCK_CODE = re.compile(
    r'[\s,:;|/]*(?:'
    rf'[-–—_]\s*{_STOCK_CODE}'
    rf'|\(\s*(?:sku[\s:#-]*)?{_STOCK_CODE}\s*\)'
    rf'|\[\s*(?:sku[\s:#-]*)?{_STOCK_CODE}\s*\]'
    r')\s*$',
    re.I,
)

_TRAILING_SEPARATORS = ' -–—_|/,;:.'


def _title_tokens(value):
    """Split a title into display tokens, preserving their original text."""

    return [token for token in str(value or '').split() if token]


def _comparison_token(token):
    """Fold one token to the letters and digits used for comparisons."""

    return re.sub(r'[^a-z0-9]+', '', str(token).lower())


def _store_name_tokens(seller_name):
    """Return the identifying words of a seller's store name.

    "Carrefour Pakistan" identifies itself as "carrefour"; a store called
    "Mobile Zone" has nothing but shop words, so all of them are kept.
    """

    tokens = [
        token
        for token in (
            _comparison_token(part) for part in _title_tokens(seller_name)
        )
        if token
    ]
    identifying = [
        token for token in tokens if token not in STORE_NAME_WORDS
    ]

    return identifying or tokens


def _contains_brand_token(tokens):
    """Report whether a known phone brand appears among these tokens."""

    return any(
        _comparison_token(token) in _BRAND_TOKENS for token in tokens
    )


def _strip_store_prefix(tokens, store_tokens):
    """Drop a leading store name from a listing title's tokens.

    Sellers spell their own name inconsistently across their listings
    ("AL Fatah" and "AL-Fatah"), so the leading tokens are compared with the
    store name as one run of letters and digits. A brand token is never
    consumed: a store called "Samsung Official Store" must not eat the
    "Samsung" that identifies the phone.
    """

    target = ''.join(store_tokens)

    if not target:
        return tokens

    matched = ''
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
            # "Carrefour Official Store Samsung ..." - shop words inside the
            # store name are part of the prefix, not of the phone.
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


def _strip_store_word_prefix(tokens):
    """Drop leading shop words when a real brand follows them.

    Daraz titles such as "Official Store Infinix Hot 50" carry the shop in
    front of the phone even when the seller name is unknown.
    """

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

    if len(remainder) < 2 or not _contains_brand_token(remainder):
        return tokens

    return remainder


def clean_listing_title(title, seller_name=None):
    """Return a marketplace title reduced to the product it describes.

    Removes the seller's store name and the marketplace stock code that
    Daraz glues to the end, so "Carrefour Samsung Galaxy A07 4+128GB
    Green-303662" becomes "Samsung Galaxy A07 4+128GB Green". The original
    title is returned unchanged whenever cleaning would leave something too
    short to identify a phone.
    """

    original = ' '.join(str(title or '').split())

    if not original:
        return original

    cleaned = original

    # Marketplaces append at most one stock code, but a title may also end
    # with the separator that preceded it.
    for _ in range(2):
        shortened = _TRAILING_STOCK_CODE.sub('', cleaned)
        if shortened == cleaned:
            break
        cleaned = shortened.strip(_TRAILING_SEPARATORS)

    tokens = _title_tokens(cleaned)
    tokens = _strip_store_prefix(tokens, _store_name_tokens(seller_name))
    tokens = _strip_store_word_prefix(tokens)

    cleaned = ' '.join(tokens).strip(_TRAILING_SEPARATORS)
    cleaned = ' '.join(cleaned.split())

    if len(cleaned) < 3 or not re.search(r'[a-z]', cleaned, re.I):
        return original

    return cleaned


# The Daraz smartphones category page also serves cables, chargers,
# covers and screen protectors. Taken at face value they became
# canonical products ("Original Samsung 45W GaN Charger" is one in the
# catalog today) or filled the pending-match queue with items no
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
    '|'.join(
        (
            r'\botg\b',
            r'\bstickers?\b',
            r'\bselfie\s+stick\b',
            r'\btripod\b',
            r'\bring\s+light\b',
            r'\bsim\s+(?:ejector|tray)\b',
            r'\bcamera\s+lens\s+protector\b',
            r'\bwatch\s+strap\b',
            r'\bpack\s+of\s+\d+\b',
            r'\bspeaker\s+mesh\b',
            r'\bdust\s*proof\b',
            r'\bfaucet\b',
            r'\bkeyboard\b',
            r'\bmouse\b',
            r'\bneckband\b',
            r'\bairpods?\b',
        )
    ),
    re.I,
)

SOFT_ACCESSORY_PATTERN = re.compile(
    '|'.join(
        (
            r'\bcables?\b',
            r'\bchargers?\b',
            r'\bcharging\s+(?:adapter|brick|dock|pad|station)\b',
            r'\badapter\b',
            r'\bconverter\b',
            r'\bpower\s*bank\b',
            r'\bmemory\s+card\b',
            r'\bsd\s+card\b',
            r'\bback\s*cover\b',
            r'\bphone\s+case\b',
            r'\bcover\s+for\b',
            r'\bpouch\b',
            r'\btempered\s+glass\b',
            r'\bscreen\s+(?:protector|guard)\b',
            r'\bprotector\s+(?:pack|film)\b',
            r'\bear\s*(?:buds?|phones?)\b',
            r'\bhead\s*(?:phones?|sets?)\b',
            r'\bhands?\s*free\b',
            r'\bcar\s+(?:holder|mount|charger)\b',
        )
    ),
    re.I,
)

# "Box Charger", "with Free Powerbank": the box, not the product.
ACCESSORY_INCLUSION_PATTERN = re.compile(
    r'(?:\b(?:free|with|incl|included|including|includes|bundle|bundled|box|boxed|plus|and|no|without|extra|gift)\b|[+&,])',
    re.I,
)

# "Memory Card Support": a feature of the phone, not the product.
ACCESSORY_FEATURE_PATTERN = re.compile(
    r'^\s*(?:supp\w*|slot|compatible|expandable|support\w*|included|option\w*|available|only)\b',
    re.I,
)

# How far either side of the keyword that wording may sit.
CONTEXT_WINDOW = 30


def is_accessory_title(title):
    """Report whether a marketplace title describes an accessory."""

    text = ' '.join(str(title or '').split())

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


_WARRANTY_NUMBERS = {'one': '1', 'two': '2', 'three': '3'}

_WARRANTY_PHRASE = re.compile(
    r'(?:\b(?P<number>\d{1,2}|one|two|three)\s*-?\s*'
    r'(?P<unit>years?|yrs?|months?)\s+)?'
    r'(?P<kinds>(?:(?:official|brand|seller|local|shop|company)\s+){0,3})'
    r'warranty\b',
    re.I,
)


def warranty_from_text(*texts):
    """Return the warranty a seller states in free text, or ``None``.

    Reads "PTA Approved 1 Year Official Brand Warranty" as "1 Year Brand
    Warranty". Only what the text says is reported: a title that mentions
    no warranty yields nothing rather than a guess.
    """

    for text in texts:
        source = ' '.join(str(text or '').split())

        if not source:
            continue

        if re.search(r'\b(?:no|without)\s+warranty\b', source, re.I):
            return 'No Warranty'

        best = None
        for match in _WARRANTY_PHRASE.finditer(source):
            kinds = match.group('kinds').lower()
            parts = []

            if match.group('number'):
                number = _WARRANTY_NUMBERS.get(
                    match.group('number').lower(),
                    match.group('number'),
                )
                unit = 'Month' if match.group('unit').lower().startswith(
                    'month'
                ) else 'Year'
                parts.append(f'{number} {unit}' + ('' if number == '1' else 's'))

            if 'brand' in kinds or 'official' in kinds or 'company' in kinds:
                parts.append('Brand')
            elif 'seller' in kinds or 'shop' in kinds:
                parts.append('Seller')
            elif 'local' in kinds:
                parts.append('Local')

            phrase = ' '.join(parts + ['Warranty'])

            # Prefer the most specific statement in the text.
            if best is None or len(parts) > best[0]:
                best = (len(parts), phrase)

        if best is not None:
            return best[1]

    return None
