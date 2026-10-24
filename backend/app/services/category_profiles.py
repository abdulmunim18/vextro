"""What makes a product, and a variant of it, in each catalogue category.

VEXTRO began with smartphones only, and phone rules (RAM, storage, 4G/5G)
were applied to everything. A category profile states, per category:

* which attributes tell two variants of one product apart (a phone's RAM
  and storage, a tablet's Wi-Fi or cellular model, a watch's case size);
* how those attributes are read from a marketplace title and its
  specification sheet.

Colour and condition are variant attributes in every category and stay in
their own columns, so they are not repeated here.

The slugs are the categories seeded by migration ``230caa8e6095``. A
listing names its category; one that names none is a smartphone, which is
what every listing was before categories existed.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from dataclasses import dataclass

from app.services.smartphone_normalization import (
    BRAND_ALIASES,
    extract_memory_capacities,
    normalize_specifications,
)
from app.services.variant_identity import configuration_key


class UnknownCategoryError(ValueError):
    """A listing named a category VEXTRO has no profile for."""


Extractor = Callable[[str, dict[str, str], str], object | None]


@dataclass(frozen=True)
class IdentityAttribute:
    """One attribute that separates two variants of a product."""

    key: str
    label: str
    unit: str | None
    extract: Extractor


@dataclass(frozen=True)
class CategoryProfile:
    slug: str
    name: str
    identity: tuple[IdentityAttribute, ...]
    # Words that name a variant or the offer, not the product: "Wi-Fi" and
    # "11-inch" on a tablet, "44mm" and "GPS" on a watch, "1 Year Warranty".
    # They come off before a title becomes a product name or is compared
    # with one.
    variant_words: tuple[re.Pattern, ...] = ()
    # One model spelled two ways by two stores, written one way: "8th
    # Generation M4 Chip" and "M4 8th Gen", "SM-X400" and "X400".
    name_rewrites: tuple[
        tuple[re.Pattern, str | Callable[[re.Match], str]], ...
    ] = ()

    def product_title(self, title: str | None) -> str:
        """Return the title without the words that name a variant."""

        text = str(title or "")
        if self.name_rewrites:
            # PriceOye sends some titles HTML-escaped: "1.96&#039;&#039;".
            text = html.unescape(text)
        removed = 0
        for pattern, replacement in self.name_rewrites:
            text, count = pattern.subn(replacement, text)
            removed += count
        for pattern in self.variant_words:
            text, count = pattern.subn(" ", text)
            removed += count

        # "Wi-Fi + Cellular" leaves a lone "+"; brackets may be left empty.
        # A title that lost nothing (every phone title) is left as it was.
        if removed:
            text = re.sub(r"(?<!\S)[+&/,|-](?!\S)", " ", text)
            text = re.sub(r"\(\s*\)", " ", text)

        return " ".join(text.split())

    def identity_from(
        self,
        *,
        title: str | None,
        specifications: dict[str, object] | None = None,
        variant: str | None = None,
        stated: dict[str, object] | None = None,
    ) -> dict[str, object]:
        """Return the identity attributes a listing states, by key.

        ``stated`` holds values the source sent as fields of their own (the
        crawler's ``ram_gb`` and ``storage_gb``); they outrank anything read
        from text, as they always have in the matcher. Attributes nobody
        states are left out rather than guessed, so an unstated value never
        contradicts a stated one.
        """

        normalized = normalize_specifications(specifications)
        text = " ".join(part for part in (variant or "", title or "") if part)
        values: dict[str, object] = {}

        for attribute in self.identity:
            value = (stated or {}).get(attribute.key)
            if value is None:
                value = attribute.extract(text, normalized, title or "")
            if value is not None:
                values[attribute.key] = value

        return values

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(attribute.key for attribute in self.identity)

    @property
    def uses_memory(self) -> bool:
        """Whether RAM and storage tell this category's variants apart.

        A watch seller's "2GB 32GB" describes nothing a buyer chooses
        between; read as identity, it opened variants of its own.
        """

        return "ram_gb" in self.keys or "storage_gb" in self.keys


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------


def _memory(text: str, specifications: dict[str, str], title: str) -> tuple[int | None, int | None]:
    """RAM and storage read the way the matcher has always read them.

    The specification sheet first, then the title's own figures
    ("6GB 128GB"). Kept identical so phones resolve exactly as before.
    """

    # Imported here: the matcher will itself depend on category profiles.
    from app.services.product_matching_service import _extract_memory_values

    ram_gb, storage_gb = extract_memory_capacities(
        specifications=specifications,
        title=title,
        variant=text,
    )
    title_ram, title_storage = _extract_memory_values(text)

    return ram_gb or title_ram, storage_gb or title_storage


def _ram_gb(text: str, specifications: dict[str, str], title: str) -> int | None:
    return _memory(text, specifications, title)[0]


def _storage_gb(text: str, specifications: dict[str, str], title: str) -> int | None:
    return _memory(text, specifications, title)[1]


_CELLULAR = re.compile(r"\b(?:cellular|lte|3g|4g|5g|sim)\b", re.I)
_WIFI_ONLY = re.compile(r"\bwi[\s-]?fi\b", re.I)


def _connectivity(text: str, specifications: dict[str, str], title: str) -> str | None:
    """"cellular" or "wifi": an iPad Wi-Fi and Cellular are two prices.

    A model that names neither states nothing; most such tablets are
    Wi-Fi only, but that is a guess, and a guess must not split or join
    variants.
    """

    stated = " ".join(
        [text]
        + [
            value
            for key, value in specifications.items()
            if any(word in key for word in ("network", "connectivity", "sim"))
        ]
    )

    if _CELLULAR.search(stated):
        return "cellular"
    if _WIFI_ONLY.search(stated):
        return "wifi"
    return None


_CASE_SIZE = re.compile(r"\b(\d{2})\s*mm\b", re.I)


def _case_size_mm(text: str, specifications: dict[str, str], title: str) -> int | None:
    """A watch's case size: the 41 mm and 45 mm models are priced apart."""

    for source in (text, specifications.get("case_size", ""), specifications.get("display", "")):
        match = _CASE_SIZE.search(str(source))
        if match and 20 <= int(match.group(1)) <= 60:
            return int(match.group(1))
    return None


_SCREEN_SIZE = re.compile(
    # Stores write inches as a word, a quote, a double prime or two
    # apostrophes: 11-inch, 13", 14.6″, 8.3''.
    r"\b(\d{1,2}(?:\.\d{1,2})?)\s*-?\s*(?:inches|inch|\"|''|”|″)",
    re.I,
)


def _screen_inches(text: str, specifications: dict[str, str], title: str) -> int | float | None:
    """A tablet's screen size as the title states it: 11 or 13 inches.

    The 11- and 13-inch iPad Pro are one model at two prices. Only the
    title is read: a specification sheet's 10.95 against another store's
    "11-inch" would part one tablet into two.
    """

    for match in _SCREEN_SIZE.finditer(text):
        size = float(match.group(1))
        if 7 <= size <= 15:
            return int(size) if size.is_integer() else round(size, 1)
    return None


# "1 Year Warranty", "(1 Year Brand Warranty)": the seller's promise, not
# the product's name.
_WARRANTY_WORDS = re.compile(
    r"\b(?:with\s+)?(?:\d{1,2}|one|two|three)\s*(?:years?|yrs?|months?)\s+(?:of\s+)?"
    r"(?:(?:(?:brand|official|local)\s+)?warranty|brand|official)\b",
    re.I,
)

# "(2025)", "2026": a tablet is named by its chip and generation ("iPad Air
# M4", "Tab S10 FE"); stores add the year in different places, and the
# phone name cleaner cuts a name at its first bracket ("iPad Pro (2025) M5"
# became "iPad Pro").
_MODEL_YEAR = re.compile(r"\(\s*20\d{2}\s*\)|\b20\d{2}\b")


def _compact(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


# A brand written in two words ("VGO TEL", "One Plus") is the brand's own
# name, not part of the model: written as the brand, so the name cleaner
# does not keep both ("VGOTEL VGO TEL V Tab 2").
_BRAND_SPELLINGS = tuple(
    (
        re.compile(
            r"\b" + r"[\s-]+".join(map(re.escape, re.split(r"[\s-]+", alias))) + r"\b",
            re.I,
        ),
        canonical,
    )
    for canonical, aliases in BRAND_ALIASES
    for alias in aliases
    if re.search(r"[\s-]", alias) and _compact(alias) == _compact(canonical)
)


def _ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        return f"{number}th"
    return f"{number}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(number % 10, 'th') }"


_STORAGE_SIZES = {16, 32, 64, 128, 256, 512, 1024}

_TABLET_NAME_REWRITES = (
    # "Redmi Pad 2 8/256": memory without units. Left in, its "8" reads as
    # the model number of the "Pad 8". The listing states it separately.
    (
        re.compile(r"(?<![\d.])(\d{1,2})\s*(?:GB)?\s*[/+]\s*(\d{2,4})\s*(?:GB|TB)?(?![\d.])", re.I),
        lambda match: (
            " " if int(match.group(2)) in _STORAGE_SIZES else match.group(0)
        ),
    ),
    # "iPad 11 (A16)", "Tab M10 HD (2nd Gen)": the bracket holds the model,
    # and the name cleaner cuts a name at its first bracket. What else a
    # bracket holds (a year, a warranty) is removed on its own below.
    (re.compile(r"\(([^()]*)\)"), r" \1 "),
    *_BRAND_SPELLINGS,
    (re.compile(r"\bgeneration\b", re.I), "Gen"),
    # "12Th Gen" from title-cased titles.
    (
        re.compile(r"\b(\d{1,2})(st|nd|rd|th)\b", re.I),
        lambda match: match.group(1) + match.group(2).lower(),
    ),
    # Apple counts iPad generations; "iPad Air 7" is Shophive's "iPad Air
    # 7th Gen". A figure followed by a unit is a screen size and is left.
    (
        re.compile(
            r"\b(iPad(?:\s+(?:Air|Mini))?)\s+(\d{1,2})"
            r"(?![\d.])(?!\s*(?:inch|\"|''|”|″|st\b|nd\b|rd\b|th\b))",
            re.I,
        ),
        lambda match: f"{match.group(1)} {_ordinal(int(match.group(2)))} Gen",
    ),
    # Samsung names every tablet "Galaxy Tab"; stores drop or move it
    # ("Samsung S11 Ultra", "Samsung Galaxy A11 Tab").
    (
        re.compile(r"\bSamsung\s+(?:Galaxy\s+)?(?:Tab\s+)?(?=[AS]\d)", re.I),
        "Samsung Galaxy Tab ",
    ),
    (re.compile(r"(\bTab\b.*?)\s+\bTab\b", re.I), r"\1"),
    (re.compile(r"\bchip\b", re.I), " "),
    # The category's own noun says nothing about the model.
    (re.compile(r"\btablets?\b", re.I), " "),
    # Samsung's "SM-" model prefix, written by some stores only.
    (re.compile(r"\bSM-(?=[a-z]\d)", re.I), ""),
    # A Shophive typo on its Redmi Pad 2 listings.
    (re.compile(r"\bSSD\b"), " "),
)


_WATCH_CELLULAR = re.compile(r"\b(?:cellular|lte|4g|e-?sim)\b", re.I)
# Samsung calls its non-cellular models "Bluetooth" or "WiFi"; they have
# GPS too.
_WATCH_GPS = re.compile(r"\b(?:gps|wi-?fi|bluetooth(?!\s+call))\b", re.I)


def _watch_connectivity(text: str, specifications: dict[str, str], title: str) -> str | None:
    """"cellular" or "gps": the Apple Watch GPS + Cellular is a dearer model.

    Only the title is read; specification sheets list GPS as a sensor on
    watches that have no cellular model at all.
    """

    if _WATCH_CELLULAR.search(text):
        return "cellular"
    if _WATCH_GPS.search(text):
        return "gps"
    return None


_CASE_MATERIALS = (
    ("aluminium", re.compile(r"\balumini?um\b", re.I)),
    ("titanium", re.compile(r"\btitanium\b", re.I)),
    ("ceramic", re.compile(r"\bceramic\b", re.I)),
    ("steel", re.compile(r"\bstainless\s+steel\b", re.I)),
)


def _case_material(text: str, specifications: dict[str, str], title: str) -> str | None:
    """A watch case's material: the titanium Series 12 costs twice the aluminium."""

    found = [
        (match.start(), material)
        for material, pattern in _CASE_MATERIALS
        if (match := pattern.search(text)) is not None
    ]
    # The case is named before its band ("Titanium Case with Milanese Loop").
    return min(found)[1] if found else None


# "46mm Jet Black Aluminium Case With Black Sports Band (MF254)": the case's
# colour, material and band name one variant; the model ends before them.
_WATCH_CASE_AND_BAND = re.compile(
    r"(?:\b[A-Za-z]+\s+){0,3}"
    r"(?:(?:alumini?um|titanium|ceramic|stainless\s+steel)\s+)?case\b.*$",
    re.I,
)

_WATCH_NAME_REWRITES = (
    (re.compile(r"\(([^()]*)\)"), r" \1 "),
    *_BRAND_SPELLINGS,
    (
        re.compile(r"\b(\d{1,2})(st|nd|rd|th)\b", re.I),
        lambda match: match.group(1) + match.group(2).lower(),
    ),
    # One watch, as different stores (and PriceOye's own pages) name it.
    (re.compile(r"\bSE\s+Gen\s+(\d)\b", re.I), r"SE \1"),
    (re.compile(r"\bSamsung\s+(?:Galaxy\s+)?Watch\b", re.I), "Samsung Galaxy Watch"),
    (re.compile(r"\bHuawei\s+(?!Watch\b|Band\b)(?=GT|Fit)", re.I), "Huawei Watch "),
    # "GT 5", "Gt5", "GT5": Huawei writes GT5.
    (re.compile(r"\bGT\s*(\d)", re.I), r"GT\1"),
    (re.compile(r"\bMi\s+(?:Smart\s+)?Band\b", re.I), "Smart Band"),
    # Samsung's model codes encode size and LTE, which are read elsewhere.
    (re.compile(r"\bSM-?[A-Z]\d{3,4}[A-Z]{0,2}\b", re.I), " "),
    # "Nerv Smart Watch 2" is PriceOye's "Nerv Watch 2" too; once said.
    (re.compile(r"\bsmart\s*watch(?:es)?\b", re.I), "Watch"),
    (re.compile(r"(\bWatch\b.*?)\s+\bWatch\b", re.I), r"\1"),
    # A band is not a watch: "Smart Band 9 Active Smart Watch".
    (re.compile(r"(\bBand\b.*?)\s+\bWatch\b", re.I), r"\1"),
)


_AUDIO_NAME_REWRITES = (
    (re.compile(r"\(([^()]*)\)"), r" \1 "),
    *_BRAND_SPELLINGS,
    (
        re.compile(r"\b(\d{1,2})(st|nd|rd|th)\b", re.I),
        lambda match: match.group(1) + match.group(2).lower(),
    ),
    # "AirPods 4 Active Noise Cancellation" is the "AirPods 4 ANC": a model
    # of its own, written two ways.
    (re.compile(r"\bactive\s+noise\s+cancel+(?:ation|ing)\b", re.I), "ANC"),
    (re.compile(r"\bSamsung\s+(?:Galaxy\s+)?Buds\b", re.I), "Samsung Galaxy Buds"),
    # Anker's SKU ("A3953P11", "D1200H11") and Apple's part number
    # ("MKFW4LL/A") name a stock unit, not the model, and one store only
    # writes them. "Soundcore" is Anker's line, written or not.
    (re.compile(r"\b[A-D]\d{4}[A-Z0-9]{2,3}\b"), " "),
    (re.compile(r"\bM[A-Z0-9]{3,6}(?:LL|ZA|ZM|AM)(?:/A)?\b"), " "),
    (re.compile(r"\bsoundcore\b", re.I), " "),
)


RAM = IdentityAttribute("ram_gb", "RAM", "GB", _ram_gb)
STORAGE = IdentityAttribute("storage_gb", "Storage", "GB", _storage_gb)
CONNECTIVITY = IdentityAttribute("connectivity", "Connectivity", None, _connectivity)
CASE_SIZE = IdentityAttribute("case_size_mm", "Case size", "mm", _case_size_mm)
SCREEN_SIZE = IdentityAttribute("screen_in", "Screen", "inch", _screen_inches)
WATCH_CONNECTIVITY = IdentityAttribute("connectivity", "Connectivity", None, _watch_connectivity)
CASE_MATERIAL = IdentityAttribute("case_material", "Case", None, _case_material)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

DEFAULT_CATEGORY = "mobile-phones"

PROFILES: dict[str, CategoryProfile] = {
    profile.slug: profile
    for profile in (
        CategoryProfile("mobile-phones", "Mobile Phones", (RAM, STORAGE)),
        CategoryProfile(
            "tablets",
            "Tablets",
            (RAM, STORAGE, CONNECTIVITY, SCREEN_SIZE),
            variant_words=(
                re.compile(r"\bwi[\s-]?fi(?:\s+only)?\b", re.I),
                re.compile(r"\b(?:cellular|lte|3g|4g|5g)\b", re.I),
                _SCREEN_SIZE,
                _WARRANTY_WORDS,
                _MODEL_YEAR,
            ),
            name_rewrites=_TABLET_NAME_REWRITES,
        ),
        CategoryProfile(
            "smart-watches",
            "Smart Watches",
            (CASE_SIZE, WATCH_CONNECTIVITY, CASE_MATERIAL),
            variant_words=(
                _WATCH_CASE_AND_BAND,
                # Whatever a watch title adds "with" is a feature list. First,
                # so nothing else leaves a stray word of it behind.
                re.compile(r"\s+with\b.*$", re.I),
                re.compile(r"\b\d{2}\s*mm\b", re.I),
                re.compile(r"\b(?:gps|cellular|lte|4g|e-?sim|wi-?fi|bluetooth(?!\s+call))\b", re.I),
                # "With Two Straps", "With Marine Black Band": the box, not
                # the model.
                re.compile(r"\bwith\s+(?:[\w-]+\s+){0,3}(?:bands?|loops?|straps?)\b", re.I),
                # The case material is read as identity; the name drops it.
                re.compile(r"\b(?:alumini?um|titanium|ceramic|stainless[\s-]+steel)\b", re.I),
                # "With 1.96″ Amoled", "1.43'' HD Display": the screen.
                # 1.32" Inch: a unit can be written twice.
                re.compile(
                    r"\b\d(?:\.\d{1,2})?(?:\s*-?\s*(?:\"|''|”|″|inch(?:es)?))+"
                    r"(?:\s+(?:hd|fhd|amoled|amloed|lcd|tft|display|screen))*",
                    re.I,
                ),
                re.compile(r"\b(?:amoled|amloed|fhd|hd|lcd|tft)\b", re.I),
                # Selling points every second watch claims.
                re.compile(r"\b(?:bluetooth\s+)?calling\b", re.I),
                re.compile(r"\b(?:premium\s+)?fitness\s+(?:tracker|band)\b", re.I),
                re.compile(r"\bglobal(?:\s+version)?\b", re.I),
                re.compile(
                    r"\b(?:ip6[5-9]|water\s*-?proof|high-?quality|stylish|original)\b"
                    r"|\bfor\s+(?:men|women|boys|girls|kids)(?:\s+(?:and|&)\s+(?:men|women|boys|girls))?\b",
                    re.I,
                ),
                _WARRANTY_WORDS,
                _MODEL_YEAR,
            ),
            name_rewrites=_WATCH_NAME_REWRITES,
        ),
        # Earbuds and headphones come in colours only; the model name is
        # the product, and what titles add around it is removed.
        CategoryProfile(
            "audio-and-earbuds",
            "Audio and Earbuds",
            (),
            variant_words=(
                # "with Charging Case", "with ENC Mic": the box and its
                # selling points.
                re.compile(r"\s+with\b.*$", re.I),
                # The category's own nouns, which stores add or leave out.
                re.compile(
                    r"\b(?:true\s+)?wireless\b|\btws\b|\bbluetooth\b|\bear\s*buds?\b"
                    r"|\bearphones?\b|\bheadphones?\b|\bheadsets?\b|\bhandsfree\b"
                    r"|\bstereo\b|\bin-?ear\b",
                    re.I,
                ),
                # "Bluetooth 5.3", "40H Playtime", "IPX5", "ENC".
                re.compile(r"\b(?:v|bt)?\s?5\.\d\b", re.I),
                re.compile(r"\b\d+\s*(?:h|hrs?|hours?)\b(?:\s+playtime)?", re.I),
                re.compile(r"\bipx?\d\b|\benc\b|\bplaytime\b|\bgaming\b|\boriginal\b", re.I),
                # A feature; "Active Noise Cancellation" was written "ANC" above.
                re.compile(r"\bnoise[\s-]+cancel+(?:ation|ing)\b", re.I),
                # How it sits on the ear, which one store writes and one not.
                re.compile(
                    r"\b(?:on|over|open)[\s-]?ear\b|\bclip[\s-]?on\b|\bcomfortable\b|\btruly\b",
                    re.I,
                ),
                _WARRANTY_WORDS,
                _MODEL_YEAR,
            ),
            name_rewrites=_AUDIO_NAME_REWRITES,
        ),
    )
}

# Older names for a category, as some sources and records spell them.
ALIASES = {"smartphones": "mobile-phones"}


def profile_for(slug: str | None) -> CategoryProfile:
    """Return the profile for a category slug; no slug means a smartphone."""

    if not slug:
        return PROFILES[DEFAULT_CATEGORY]

    normalized = ALIASES.get(slug.strip().lower(), slug.strip().lower())

    try:
        return PROFILES[normalized]
    except KeyError:
        raise UnknownCategoryError(
            f"No category profile for {slug!r}; known: {', '.join(sorted(PROFILES))}."
        ) from None


__all__ = [
    "ALIASES",
    "DEFAULT_CATEGORY",
    "PROFILES",
    "CategoryProfile",
    "IdentityAttribute",
    "UnknownCategoryError",
    "configuration_key",
    "profile_for",
]
