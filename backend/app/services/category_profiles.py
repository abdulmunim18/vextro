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

import re
from collections.abc import Callable
from dataclasses import dataclass

from app.services.smartphone_normalization import (
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


_CELLULAR = re.compile(r"\b(?:cellular|lte|4g|5g|sim)\b", re.I)
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


RAM = IdentityAttribute("ram_gb", "RAM", "GB", _ram_gb)
STORAGE = IdentityAttribute("storage_gb", "Storage", "GB", _storage_gb)
CONNECTIVITY = IdentityAttribute("connectivity", "Connectivity", None, _connectivity)
CASE_SIZE = IdentityAttribute("case_size_mm", "Case size", "mm", _case_size_mm)


# ---------------------------------------------------------------------------
# Profiles
# ---------------------------------------------------------------------------

DEFAULT_CATEGORY = "mobile-phones"

PROFILES: dict[str, CategoryProfile] = {
    profile.slug: profile
    for profile in (
        CategoryProfile("mobile-phones", "Mobile Phones", (RAM, STORAGE)),
        CategoryProfile("tablets", "Tablets", (RAM, STORAGE, CONNECTIVITY)),
        CategoryProfile("smart-watches", "Smart Watches", (CASE_SIZE, CONNECTIVITY)),
        # Earbuds come in colours only; the model name is the product.
        CategoryProfile("audio-and-earbuds", "Audio and Earbuds", ()),
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
