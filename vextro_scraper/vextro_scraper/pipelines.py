import hashlib
import logging
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from math import isfinite
from urllib.parse import urljoin, urlparse

import requests
from itemadapter import ItemAdapter
from scrapy.exceptions import DropItem

from vextro_scraper.normalizers import (
    BRAND_ALIASES,
    clean_listing_title,
    is_accessory_title,
)


BULK_ITEM_QUEUED = object()
BULK_ITEM_DELIVERED = object()
BULK_ITEM_FAILED = object()
CANONICAL_PRODUCT_CREATED = object()
REVIEWS_INGESTED = object()


MARKETPLACE_PRICE_PATTERN = re.compile(
    r'^\s*(?:(?:rs\.?|pkr)\s*)?'
    r'([+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)\s*$',
    re.I,
)


class NonSmartphoneItemError(DropItem):
    """Reject a catalog item that is an accessory rather than a phone.

    The marketplace's smartphones category also serves cables, chargers and
    covers. Delivering them registered accessories as catalog products and
    filled the pending-match queue with items nobody can map to a phone.
    """

    error_type = 'non_smartphone_item'
    error_stage = 'validation'
    # Turned away on purpose, not lost: it must not mark the run partial.
    outcome = 'rejected'


class ReviewsOfTurnedAwayListingError(DropItem):
    """Pass over the reviews of a listing this run turned away."""

    error_type = 'review_of_turned_away_listing'
    error_stage = 'validation'
    outcome = 'rejected'


class UnbrandedItemError(DropItem):
    """Pass over a non-phone listing that names no manufacturer."""

    error_type = 'unbranded_item'
    error_stage = 'validation'
    outcome = 'rejected'


# The matcher's MEDIUM tier: close enough for an administrator to confirm.
MATCH_ONLY_REVIEW_CONFIDENCE = 75


class NotInCatalogueError(DropItem):
    """Pass over a match-only listing that names no catalogue product.

    Daraz's tablet and watch listings are mostly unbranded. They may join a
    product another marketplace catalogued; one that resembles nothing is
    not queued for an administrator, who could not map it either.
    """

    error_type = 'not_in_catalogue'
    error_stage = 'matching'
    outcome = 'rejected'


class InvalidMarketplacePriceError(DropItem):
    """Reject an item whose marketplace price is not a positive amount."""

    error_type = 'invalid_price'
    error_stage = 'validation'

    def __init__(self, message, *, raw_value=None):
        super().__init__(message)
        self.raw_value = raw_value


def normalize_marketplace_price(raw_price):
    """Parse one finite, positive Daraz/PriceOye price as a float."""

    if raw_price is None:
        raise ValueError('price is missing')

    if isinstance(raw_price, bool):
        raise ValueError('boolean values are not prices')

    if isinstance(raw_price, str):
        match = MARKETPLACE_PRICE_PATTERN.fullmatch(raw_price)
        if match is None:
            raise ValueError('price format is not supported')
        numeric_value = match.group(1).replace(',', '')
    elif isinstance(raw_price, (int, float, Decimal)):
        if isinstance(raw_price, float) and not isfinite(raw_price):
            raise ValueError('price must be finite')
        numeric_value = str(raw_price)
    else:
        raise ValueError('price type is not supported')

    try:
        price = Decimal(numeric_value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError('price is not numeric') from exc

    if not price.is_finite():
        raise ValueError('price must be finite')

    if price <= 0:
        raise ValueError('price must be greater than zero')

    normalized_price = float(price)
    if not isfinite(normalized_price):
        raise ValueError('price must be finite')

    return normalized_price


PLACEHOLDER_IMAGE_HOSTS = frozenset(
    {
        'placehold.co',
        'via.placeholder.com',
        'placeholder.com',
        'dummyimage.com',
    }
)

# Marketplace galleries are served as real image files. Tracking
# pixels, inline data URIs and lazy-loading spacers are not product
# photography. Daraz and PriceOye both append resize directives after
# the extension ("...jpg_720x720q80.jpg_.webp"), so the extension is
# searched for anywhere in the path rather than only at its end.
IMAGE_FILE_PATTERN = re.compile(
    r'\.(?:jpe?g|png|webp|avif|gif|bmp)(?![a-z0-9])',
    re.I,
)


def is_usable_image_url(image_url):
    """Report whether a normalized gallery URL points at a real photo."""

    if not image_url.startswith(('http://', 'https://')):
        return False

    parsed = urlparse(image_url)

    if parsed.netloc.lower() in PLACEHOLDER_IMAGE_HOSTS:
        return False

    return bool(IMAGE_FILE_PATTERN.search(parsed.path))


# Words that mark a value as the shop selling the phone rather than the
# company that made it. Daraz publishes the store in its ``brandName``
# field ("OPPO Pakistan Official", "FAYWA TRADING (PVT) LTD"), which filled
# the catalog's brand filter with sellers. "Mobile" is deliberately absent:
# it is part of real brand names such as "me Mobile".
BRAND_RESELLER_WORDS = frozenset(
    {
        'co', 'collection', 'corner', 'enterprise', 'enterprises',
        'flagship', 'gallery', 'hub', 'inc', 'ltd', 'mall', 'mart',
        'official', 'officials', 'pvt', 'retail', 'retailer', 'seller',
        'shop', 'shops', 'store', 'stores', 'trader', 'traders', 'trading',
    }
)

BRAND_PLACEHOLDERS = frozenset(
    {
        'n/a', 'na', 'none', 'no brand', 'nobrand', 'unbranded', 'unknown',
        # PriceOye's brand for unbranded goods, and Daraz's refurbished
        # programme, which is a seller, not a maker.
        'assorted', 'generic', 'daraz like new', '',
        # Appliance stores that put their own name where a brand goes.
        'telemart', 'jalal electronics',
    }
)


def _brand_words(value):
    """Return the comparable words inside a brand value."""

    return re.sub(r'[^a-z0-9]+', ' ', str(value or '').lower()).split()


def canonical_brand(value):
    """Return the manufacturer a piece of text names, if it names one."""

    words = _brand_words(value)

    if not words:
        return None

    normalized = f" {' '.join(words)} "

    for canonical_name, aliases in BRAND_ALIASES:
        if any(f' {alias} ' in normalized for alias in aliases):
            return canonical_name

    return None


def brands_named(value):
    """Return every manufacturer a piece of text names, in alias order."""

    words = _brand_words(value)
    if not words:
        return []

    normalized = f" {' '.join(words)} "
    return [
        canonical_name
        for canonical_name, aliases in BRAND_ALIASES
        if any(f' {alias} ' in normalized for alias in aliases)
    ]


def infer_brand(model, provided_brand=None, *, prefer_provided=False):
    """Return the manufacturer behind a listing, never the seller.

    The marketplace's own brand field is trusted only once it is recognised
    as a manufacturer; otherwise the title decides, and a value that merely
    names a shop is dropped instead of becoming a catalog brand.

    ``prefer_provided`` trusts a store that catalogues its own goods: its
    "Xinji" brand stands for the "Xinji Nothing N1", which the title alone
    reads as a Nothing watch.
    """

    cleaned_brand = ' '.join(str(provided_brand or '').split())
    cleaned_brand = cleaned_brand.strip(' .,-|/_').strip()

    if ' '.join(_brand_words(cleaned_brand)) in BRAND_PLACEHOLDERS:
        cleaned_brand = ''

    from_brand = canonical_brand(cleaned_brand)

    if prefer_provided and from_brand is not None:
        # Shophive files Mibro and Imilab watches under "Xiaomi" (and some
        # titles say both, "Xiaomi Imilab"); a title naming another known
        # maker names the product's own.
        others = [brand for brand in brands_named(model) if brand != from_brand]
        if len(others) == 1:
            return others[0]

    if from_brand is not None:
        return from_brand

    if (
        prefer_provided
        and cleaned_brand
        and not set(_brand_words(cleaned_brand)) & BRAND_RESELLER_WORDS
    ):
        return cleaned_brand[:120]

    from_title = canonical_brand(model)
    if from_title is not None:
        return from_title

    if not cleaned_brand:
        return None

    if set(_brand_words(cleaned_brand)) & BRAND_RESELLER_WORDS:
        return None

    return cleaned_brand[:120]


def infer_title_specifications(model, specifications=None, *, bare_memory_pairs=False):
    """Fill common smartphone specifications encoded in listing titles.

    ``bare_memory_pairs`` also reads "12/256" (no unit) as RAM and storage,
    when the second figure is a storage size a device is sold in.
    """

    title = str(model or '')
    inferred = dict(specifications or {})

    patterns = (
        ('ram', (
            r'\b(\d{1,2})\s*GB\s*RAM\b',
            r'\bRAM\s*[:\-]?\s*(\d{1,2})\s*GB\b',
        ), lambda value: f'{value}GB'),
        ('storage_capacity', (
            r'\b(\d{2,4})\s*GB\s*(?:ROM|Storage|Memory)\b',
            r'\b(?:ROM|Storage|Memory)\s*[:\-]?\s*(\d{2,4})\s*GB\b',
        ), lambda value: f'{value}GB'),
        ('battery_capacity', (
            r'\b(\d{3,5})\s*mAh\b',
        ), lambda value: f'{value} mAh'),
        ('display', (
            r'\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:inches|inch|\")\s*(?:display|screen)?',
        ), lambda value: f'{value} inches'),
        ('front_camera', (
            r'\b(\d{1,3})\s*MP\s*Front\s*Camera\b',
            r'\bFront\s*Camera\s*[:\-]?\s*(\d{1,3})\s*MP\b',
        ), lambda value: f'{value}MP'),
    )

    for key, key_patterns, formatter in patterns:
        if key in inferred:
            continue
        for pattern in key_patterns:
            match = re.search(pattern, title, re.I)
            if match:
                inferred[key] = formatter(match.group(1))
                break

    capacity_pair = re.search(
        r'\b(\d{1,2})\s*(?:GB)?\s*[/+|]\s*(\d{2,4})\s*GB\b',
        title,
        re.I,
    )
    if capacity_pair is None and bare_memory_pairs:
        capacity_pair = next(
            (
                match
                for match in re.finditer(
                    r'(?<![\d.])(\d{1,2})\s*[/+]\s*(\d{2,4})(?![\d.])',
                    title,
                )
                if int(match.group(1)) <= 24
                and int(match.group(2)) in {16, 32, 64, 128, 256, 512}
            ),
            None,
        )
    if capacity_pair:
        inferred.setdefault('ram', f'{capacity_pair.group(1)}GB')
        inferred.setdefault(
            'storage_capacity',
            f'{capacity_pair.group(2)}GB',
        )

    storage_options = list(dict.fromkeys(
        match.group(1)
        for match in re.finditer(r'\b(\d{2,4})\s*GB\b', title, re.I)
        if int(match.group(1)) >= 32
    ))
    if storage_options:
        inferred.setdefault(
            'storage_options',
            ', '.join(f'{value}GB' for value in storage_options),
        )
    if re.search(r'\bPTA\s*Approved\b', title, re.I):
        inferred.setdefault('pta_status', 'PTA Approved')
    if re.search(r'\bDual\s*SIM\b|\b2\s*SIM\b', title, re.I):
        inferred.setdefault('sim', 'Dual SIM')
    if re.search(r'\bType[ -]?C\b|\bUSB[ -]?C\b', title, re.I):
        inferred.setdefault('charging', 'USB Type-C')
    if re.search(r'\bBluetooth\b', title, re.I):
        inferred.setdefault('connectivity', 'Bluetooth')
    warranty = re.search(r'\b(\d+\s*Year\s*Warranty)\b', title, re.I)
    if warranty:
        inferred.setdefault('warranty', warranty.group(1))

    return inferred

PHONE_CATEGORY = 'mobile-phones'

# The backend stores at most 150 characters of a listing's marketplace id.
EXTERNAL_ID_LIMIT = 150


def bounded_external_id(value):
    """Return a listing id the backend can store, the same on every crawl.

    PriceOye builds ids from page slugs, and a few slugs carry a whole
    sales pitch ("xinji-stone-m2-...-for-men-and-women--black", 190
    characters). Those keep their start and gain a short hash of the whole.
    """

    if value is None:
        return None

    text = str(value)
    if len(text) <= EXTERNAL_ID_LIMIT:
        return text

    digest = hashlib.sha1(text.encode('utf-8')).hexdigest()[:12]
    return f'{text[:100].rstrip("-")}--{digest}'

# What a tablet category also serves: drawing pads and pen displays,
# children's LCD writing boards, e-paper notebooks, and tablet accessories
# and keyboard bundles, which are priced apart from the tablet itself.
NOT_A_TABLET = re.compile(
    r'\b(?:'
    r'drawing|graphics?\s+(?:pen\s+)?tablet|pen\s+(?:display|tablet)'
    r'|digital\s+paper|e-?reader|writing\s+(?:tablet|pad|board)'
    r'|stylus|pen\s+for|nibs?|screen\s+protector|tempered\s+glass'
    r'|keyboard|(?:tablet|ipad)\s+(?:bag|sleeve|stand|holder|case|cover)'
    r'|(?:case|cover)\s+for'
    r')\b',
    re.I,
)


# What a watch category also serves: straps and strap sets, chargers,
# screen guards and bumper cases, and screen-less trackers (WHOOP, Fitbit
# Air), which are subscriptions rather than watches. A "Smart Band" is a
# wearable sold beside watches and is kept.
NOT_A_WATCH = re.compile(
    r'\b(?:'
    r'straps?|strap\s+set|replacement\s+band|bands?\s+for|watch\s+band\s+for'
    r'|charg(?:er|ing\s+(?:cable|dock|stand|base))|magnetic\s+cable'
    r'|screen\s+protector|tempered\s+glass|protective\s+film'
    r'|(?:case|cover|bumper)\s+for|screen-?less|whoop|fitbit\s+air'
    r')\b',
    re.I,
)


# What sellers write on copies of branded goods: "Samsung Logo Smart Watch
# Ultra", "Super Master Copy". Phones have their own accessory rules.
COPY_MARKERS = re.compile(
    r'\b(?:logo|(?:super\s+|first\s+|high\s+|master\s+|aaa\s+)?copy'
    r'|super\s+master|replica|clone'
    # A listing kept up at an absurd price so nobody buys it.
    r'|do\s+not\s+(?:buy|purchase|order)|not\s+for\s+sale)\b',
    re.I,
)


# What an earbud category also serves: cases and covers for AirPods and
# their kin, ear tips, cables and chargers, and the speakers, soundbars
# and microphones some audio stores file beside earbuds.
NOT_AUDIO = re.compile(
    r'\b(?:'
    r'(?:case|cover|skin|pouch|sleeve)\s+for|(?:silicone|protective|leather)\s+(?:case|cover)'
    r'|ear\s*tips?|ear\s*hooks?|replacement|charging\s+cable|cable\s+for|charger|adapter'
    r'|speakers?|sound\s*bar|amplifier|microphone|lavalier|karaoke'
    r')\b',
    re.I,
)


# What a laptop category also serves: bags and sleeves, chargers and
# adapters, cooling pads, stands and skins, and machines sold used, which
# are not the new laptop the stores price.
NOT_A_LAPTOP = re.compile(
    r'\b(?:'
    r'bags?|backpack|sleeve|carry\s*case|charger|adapter|power\s+supply'
    r'|cooling\s+pad|cooler|stand|skin|keyboard\s+(?:cover|protector|skin)'
    r'|screen\s+protector|battery\s+for'
    r'|used|refurbished|renewed|second\s*hand|pre-?owned|like\s+new|open\s+box'
    r')\b',
    re.I,
)


# What an AC category also serves: covers, stands and pipe kits, air
# coolers and fans, and at a marketplace, whatever a seller filed there.
NOT_AN_AC = re.compile(
    r'\b(?:'
    r'covers?|stands?|brackets?|copper|pipe|installation|remote|stabili[sz]ers?'
    r'|air\s*coolers?|coolers?|fans?|purifiers?|dehumidifiers?'
    r'|pumps?|shoes?|sandals?|for\s+(?:women|men|girls|boys|kids)'
    r'|used|refurbished|second\s*hand'
    r')\b',
    re.I,
)


def is_out_of_category(category, title):
    """Return whether a title names something its category does not sell."""

    if category == PHONE_CATEGORY:
        return is_accessory_title(title)
    if COPY_MARKERS.search(title or ''):
        return True
    if category == 'tablets':
        return bool(NOT_A_TABLET.search(title or ''))
    if category == 'laptops':
        return bool(NOT_A_LAPTOP.search(title or ''))
    if category == 'air-conditioners':
        # "... AC with Official Warranty" and "with Free Installation" are
        # the offer, not what is sold.
        sold = re.split(r'\bwith\b', title or '', maxsplit=1, flags=re.I)[0]
        return bool(NOT_AN_AC.search(sold))
    if category == 'audio-and-earbuds':
        # What follows "with" lists features ("with Dual Speaker Drivers",
        # "with Mic"), not what is sold.
        sold = re.split(r'\bwith\b', title or '', maxsplit=1, flags=re.I)[0]
        return bool(NOT_AUDIO.search(sold))
    if category == 'smart-watches':
        # "... Smart Watch with 2 Straps" is a watch with a spare strap.
        watch = re.sub(r'\bwith\b[^|,]{0,25}?\bstraps?\b', ' ', title or '', flags=re.I)
        return bool(NOT_A_WATCH.search(watch))
    return False


class VextroCleaningPipeline:
    def __init__(self):
        # Listings this run turned away. A spider asks for a listing's
        # reviews as it reads the listing, so their reviews still arrive
        # and would be sent for a listing the catalogue never received.
        self.turned_away = set()

    def turn_away(self, adapter, error):
        external_id = adapter.get('external_id')
        if external_id:
            self.turned_away.add(str(external_id))
        raise error

    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # Review batches use the dedicated backend review contract and do not
        # contain listing prices.
        if adapter.get('reviews') is not None:
            adapter['external_listing_id'] = bounded_external_id(
                adapter.get('external_listing_id')
            )
            if str(adapter.get('external_listing_id')) in self.turned_away:
                raise ReviewsOfTurnedAwayListingError(
                    'Reviews of a listing this run did not deliver.'
                )
            return item

        # Community opinions describe a phone, not an offer: there is no
        # price to validate and no seller title to clean.
        if adapter.get('opinions') is not None:
            return item

        # 1. Accept only finite, positive marketplace prices. A failed parse
        # is an invalid item state, never a numeric sentinel such as zero.
        raw_price = adapter.get('price')
        try:
            adapter['price'] = normalize_marketplace_price(raw_price)
        except ValueError as exc:
            platform = str(adapter.get('platform') or 'unknown').lower()
            external_id = str(
                adapter.get('external_id') or 'unknown'
            )
            product_url = str(
                adapter.get('product_url') or 'unknown'
            )[:500]
            raw_price_context = repr(raw_price)[:200]
            logging.warning(
                'Rejected marketplace item: platform=%s '
                'external_id=%s product_url=%s reason=invalid_price '
                'raw_price=%s detail=%s',
                platform,
                external_id,
                product_url,
                raw_price_context,
                str(exc),
            )
            raise InvalidMarketplacePriceError(
                'Invalid marketplace price '
                f'(platform={platform} external_id={external_id}).',
                raw_value=raw_price_context,
            ) from exc

        # 1b. An original/list price is optional. A malformed one is simply
        # dropped: a missing discount must never reject a valid price update.
        try:
            original_price = normalize_marketplace_price(
                adapter.get('original_price')
            )
        except ValueError:
            original_price = None

        if (
            original_price is not None
            and original_price <= adapter['price']
        ):
            original_price = None

        adapter['original_price'] = original_price

        # 1c. Marketplace review aggregates, bounded to their valid ranges.
        try:
            rating = float(adapter.get('rating'))
        except (TypeError, ValueError):
            rating = None

        adapter['rating'] = (
            round(rating, 2)
            if rating is not None and 0 < rating <= 5
            else None
        )

        try:
            review_count = int(adapter.get('review_count') or 0)
        except (TypeError, ValueError):
            review_count = 0

        adapter['review_count'] = max(0, review_count)

        # 2. Reduce the marketplace title to the product it describes. The
        # seller's store name and the stock code Daraz appends belong to the
        # offer, not to the phone, and every brand, specification and match
        # below is derived from this title.
        seller = adapter.get('seller')
        seller_name = (
            seller.get('name')
            if isinstance(seller, dict)
            else seller
        )
        cleaned_title = clean_listing_title(
            adapter.get('model'),
            seller_name=seller_name,
        )

        if cleaned_title != adapter.get('model'):
            logging.debug(
                'Cleaned marketplace title: platform=%s external_id=%s '
                'original=%r cleaned=%r',
                adapter.get('platform'),
                adapter.get('external_id'),
                str(adapter.get('model'))[:200],
                cleaned_title[:200],
            )

        adapter['model'] = cleaned_title

        category = (
            adapter.get('category')
            or getattr(spider, 'catalog_category', None)
            or PHONE_CATEGORY
        )
        adapter['category'] = category
        if getattr(spider, 'match_only', False):
            adapter['match_only'] = True

        # Each category has its own rules for what it does not sell; a
        # phone's accessory rules would drop an earbud's "charging case".
        if is_out_of_category(category, cleaned_title):
            platform = str(adapter.get('platform') or 'unknown').lower()
            external_id = str(adapter.get('external_id') or 'unknown')
            logging.info(
                'Dropped marketplace item outside its category: '
                'platform=%s external_id=%s category=%s title=%r',
                platform,
                external_id,
                category,
                cleaned_title[:200],
            )
            self.turn_away(adapter, NonSmartphoneItemError(
                f'Marketplace item is not sold as {category} '
                f'(platform={platform} external_id={external_id}).'
            ))

        # 3. Clean Availability: Convert 'In Stock' to Boolean (True/False)
        avail = adapter.get('availability', '')
        adapter['is_available'] = True if 'In Stock' in avail else False

        # 4. Generate External ID: Extract the unique slug from the URL
        url = adapter.get('product_url', '')
        if url and not adapter.get('external_id'):
            # Example: grabs "xiaomi-redmi-note-14-pro" from the end of the URL
            adapter['external_id'] = url.rstrip('/').split('/')[-1]
        adapter['external_id'] = bounded_external_id(adapter.get('external_id'))

        # 5. Normalize and deduplicate gallery URLs while preserving order.
        # A listing without a usable image reaches the catalog as a blank
        # card, so an empty gallery is reported rather than passed silently.
        normalized_images = []
        for image_url in adapter.get('image_urls') or []:
            if not isinstance(image_url, str) or not image_url.strip():
                continue

            normalized_url = urljoin(url, image_url.strip())
            if (
                is_usable_image_url(normalized_url)
                and normalized_url not in normalized_images
            ):
                normalized_images.append(normalized_url)

        adapter['image_urls'] = normalized_images

        if not normalized_images:
            logging.warning(
                'Marketplace item carries no usable image: platform=%s '
                'external_id=%s product_url=%s',
                str(adapter.get('platform') or 'unknown').lower(),
                str(adapter.get('external_id') or 'unknown'),
                str(url or 'unknown')[:500],
            )

        adapter['brand'] = infer_brand(
            adapter.get('model'),
            adapter.get('brand'),
            # PriceOye and Shophive name their own goods; outside phones a
            # model is often named after another brand's line.
            prefer_provided=bool(adapter.get('exact_model_title'))
            and category != PHONE_CATEGORY,
        )

        # Outside phones the catalogue holds only goods a manufacturer
        # stands behind: PriceOye files unbranded kids' tablets under
        # "Assorted", Daraz under "No Brand". Phones keep their own handling.
        if category != PHONE_CATEGORY and not adapter['brand']:
            logging.info(
                'Dropped an unbranded marketplace item: platform=%s '
                'external_id=%s category=%s title=%r',
                str(adapter.get('platform') or 'unknown').lower(),
                str(adapter.get('external_id') or 'unknown'),
                category,
                cleaned_title[:200],
            )
            self.turn_away(adapter, UnbrandedItemError(
                f'Marketplace item names no manufacturer ({category}).'
            ))

        # 6. Keep API-safe, consistently named specification pairs.
        normalized_specifications = {}
        source_specifications = infer_title_specifications(
            adapter.get('model'),
            adapter.get('specifications'),
            # "12/256" names RAM and storage on tablets; on phones the
            # crawlers already state memory and the matcher was tuned
            # without it.
            bare_memory_pairs=category != PHONE_CATEGORY,
        )
        for label, value in source_specifications.items():
            normalized_label = re.sub(
                r'[^a-z0-9]+',
                '_',
                str(label).strip().lower(),
            ).strip('_')
            if not normalized_label or value in (None, ''):
                continue

            if isinstance(value, (list, tuple, set)):
                normalized_value = ', '.join(
                    str(part).strip()
                    for part in value
                    if str(part).strip()
                )
            else:
                normalized_value = str(value).strip()

            if normalized_value:
                normalized_specifications[normalized_label[:80]] = (
                    normalized_value[:2000]
                )

        adapter['specifications'] = normalized_specifications

        return item


def _optional_text(value):
    """Return meaningful optional text without marketplace placeholders."""

    if value is None:
        return None

    normalized = str(value).strip()

    if not normalized or normalized.lower() in {
        'n/a', 'na', 'none', 'unknown', 'standard',
    }:
        return None

    return normalized


def _capacity_gb(value):
    """Extract a RAM/storage capacity in GB from normalized scraper text."""

    normalized = _optional_text(value)
    if normalized is None:
        return None

    match = re.search(r'\b(\d{1,4})\s*(gb|tb)\b', normalized, re.I)
    if match is None:
        return None

    capacity = int(match.group(1))
    if match.group(2).lower() == 'tb':
        capacity *= 1024

    return capacity


def _normalize_scraped_at(value):
    """Return an ISO-8601 timestamp with timezone information."""

    if isinstance(value, datetime):
        captured_at = value
    elif value:
        normalized = str(value).strip()
        if normalized.endswith('Z'):
            normalized = f'{normalized[:-1]}+00:00'
        captured_at = datetime.fromisoformat(normalized)
    else:
        captured_at = datetime.now(timezone.utc)

    if captured_at.tzinfo is None:
        captured_at = captured_at.astimezone()

    return captured_at.isoformat()


class AcquisitionDeliveryError(DropItem):
    """Stop an item whose secure acquisition delivery did not succeed."""

    def __init__(
        self,
        message,
        *,
        error_type='delivery_failure',
        error_stage='delivery',
        metadata=None,
        outcome='failed',
    ):
        super().__init__(message)
        self.error_type = error_type
        self.error_stage = error_stage
        self.metadata = metadata or {}
        self.outcome = outcome

class VextroApiIngestionPipeline:
    MATCH_PATH = '/api/v1/internal/acquisition/match-product'
    RESOLVE_PATH = '/api/v1/internal/acquisition/resolve-product'
    PENDING_MATCHES_PATH = '/api/v1/internal/acquisition/pending-matches'
    LISTINGS_PATH = '/api/v1/internal/acquisition/listings'
    BULK_LISTINGS_PATH = '/api/v1/internal/acquisition/listings/bulk'
    REVIEWS_PATH = '/api/v1/internal/acquisition/reviews'

    def __init__(
        self,
        base_api_url,
        ingestion_key,
        request_timeout=5,
        session=None,
        batch_size=25,
        crawler=None,
    ):
        self.base_api_url = str(base_api_url).rstrip('/')
        self.ingestion_key = ingestion_key
        self.request_timeout = float(request_timeout)
        self.session = session or requests.Session()
        self.batch_size = max(1, min(int(batch_size), 100))
        self.crawler = crawler
        self.listing_buffer = []
        # Listings this run queued for review or passed over: the catalogue
        # holds no listing their reviews could attach to.
        self.unplaced_listing_ids = set()

    @classmethod
    def from_crawler(cls, crawler):
        ingestion_key = crawler.settings.get('INGESTION_API_KEY')
        if not ingestion_key:
            raise RuntimeError(
                'INGESTION_API_KEY is required for secure acquisition.'
            )

        return cls(
            base_api_url=crawler.settings.get(
                'VEXTRO_API_URL',
                'http://127.0.0.1:8000',
            ),
            ingestion_key=ingestion_key,
            request_timeout=crawler.settings.getfloat(
                'VEXTRO_API_TIMEOUT',
                5,
            ),
            batch_size=crawler.settings.getint(
                'VEXTRO_INGESTION_BATCH_SIZE',
                25,
            ),
            crawler=crawler,
        )

    @property
    def headers(self):
        return {
            'X-Ingestion-Key': self.ingestion_key,
            'Accept': 'application/json',
        }

    @staticmethod
    def _context(payload):
        platform = str(payload.get('platform') or 'unknown').lower()
        external_id = str(
            payload.get('external_id')
            or payload.get('external_listing_id')
            or 'unknown'
        )
        return f'platform={platform} external_id={external_id}'

    def _post_json(self, path, payload, context):
        try:
            response = self.session.post(
                f'{self.base_api_url}{path}',
                headers=self.headers,
                json=payload,
                timeout=self.request_timeout,
            )
        except requests.Timeout as exc:
            logging.error(
                'Secure acquisition timed out (%s, stage=%s).',
                context,
                path,
            )
            raise AcquisitionDeliveryError(
                f'Secure acquisition timed out ({context}).',
                error_type='backend_timeout',
                error_stage='delivery',
            ) from exc
        except requests.RequestException as exc:
            logging.error(
                'Secure acquisition backend is unavailable '
                '(%s, stage=%s, error=%s).',
                context,
                path,
                type(exc).__name__,
            )
            raise AcquisitionDeliveryError(
                f'Secure acquisition delivery failed ({context}).',
                error_type='backend_unavailable',
                error_stage='delivery',
            ) from exc

        if response.status_code not in {200, 201}:
            if response.status_code in {401, 403}:
                reason = 'authentication rejected'
            elif response.status_code in {400, 422}:
                reason = 'payload validation rejected'
            elif response.status_code >= 500:
                reason = 'backend failure'
            else:
                reason = 'unexpected response'

            logging.error(
                'Secure acquisition %s (%s, stage=%s, status=%s).',
                reason,
                context,
                path,
                response.status_code,
            )
            if response.status_code in {401, 403}:
                error_type = 'authentication_failure'
            elif response.status_code in {400, 422}:
                error_type = 'backend_validation_failure'
            elif response.status_code >= 500:
                error_type = 'backend_server_error'
            else:
                error_type = 'unexpected_backend_response'

            raise AcquisitionDeliveryError(
                f'Secure acquisition {reason} ({context}).',
                error_type=error_type,
                error_stage=(
                    'matching'
                    if path == self.MATCH_PATH
                    else 'ingestion'
                ),
                metadata={'http_status': response.status_code},
            )

        try:
            response_payload = response.json()
        except ValueError as exc:
            logging.error(
                'Secure acquisition returned malformed JSON '
                '(%s, stage=%s).',
                context,
                path,
            )
            raise AcquisitionDeliveryError(
                f'Secure acquisition returned malformed JSON ({context}).',
                error_type='malformed_backend_response',
                error_stage='delivery',
            ) from exc

        if not isinstance(response_payload, dict):
            raise AcquisitionDeliveryError(
                f'Secure acquisition returned an invalid body ({context}).',
                error_type='malformed_backend_response',
                error_stage='delivery',
            )

        return response_payload

    def _send_signal(self, signal, **kwargs):
        if self.crawler is not None:
            self.crawler.signals.send_catch_log(signal, **kwargs)

    def _emit_bulk_failure(self, record, error, spider):
        metadata = {
            **getattr(error, 'metadata', {}),
            'batch_index': record['batch_index'],
            'platform': record['payload'].get('platform_code'),
            'external_listing_id': record['payload'].get('external_id'),
        }
        item_error = AcquisitionDeliveryError(
            str(error),
            error_type=getattr(error, 'error_type', 'delivery_failure'),
            error_stage=getattr(error, 'error_stage', 'delivery'),
            metadata=metadata,
            outcome=getattr(error, 'outcome', 'failed'),
        )
        self._send_signal(
            BULK_ITEM_FAILED,
            item=record['item'],
            exception=item_error,
            spider=spider,
        )

    def _flush_listing_buffer(self, spider):
        if not self.listing_buffer:
            return

        records = self.listing_buffer
        self.listing_buffer = []
        context = f'bulk_size={len(records)}'
        request_payload = {
            'items': [record['payload'] for record in records],
        }
        try:
            response = self._post_json(
                self.BULK_LISTINGS_PATH,
                request_payload,
                context,
            )
        except AcquisitionDeliveryError as exc:
            for record in records:
                self._emit_bulk_failure(record, exc, spider)
            return

        results = response.get('results')
        if (
            response.get('received') != len(records)
            or not isinstance(results, list)
            or len(results) != len(records)
        ):
            error = AcquisitionDeliveryError(
                f'Secure bulk acquisition returned an invalid body ({context}).',
                error_type='malformed_backend_response',
                error_stage='delivery',
            )
            for record in records:
                self._emit_bulk_failure(record, error, spider)
            return

        results_by_index = {
            result.get('index'): result
            for result in results
            if isinstance(result, dict)
        }
        for record in records:
            result = results_by_index.get(record['batch_index'])
            if result is None:
                self._emit_bulk_failure(
                    record,
                    AcquisitionDeliveryError(
                        'Bulk acquisition omitted an item result.',
                        error_type='malformed_backend_response',
                        error_stage='delivery',
                    ),
                    spider,
                )
                continue
            item_status = result.get('status')
            if item_status in {'created', 'updated', 'duplicate'}:
                self._send_signal(
                    BULK_ITEM_DELIVERED,
                    item=record['item'],
                    result=result,
                    spider=spider,
                )
                continue
            outcome = 'rejected' if item_status == 'rejected' else 'failed'
            self._emit_bulk_failure(
                record,
                AcquisitionDeliveryError(
                    str(result.get('message') or 'Bulk listing ingestion failed.'),
                    error_type=str(result.get('error_code') or 'listing_ingestion_failed'),
                    error_stage=str(result.get('error_stage') or 'ingestion'),
                    metadata={
                        'validation_errors': result.get(
                            'validation_errors',
                            [],
                        ),
                    },
                    outcome=outcome,
                ),
                spider,
            )

        logging.info(
            'Secure bulk acquisition delivered batch '
            '(received=%s, succeeded=%s, duplicates=%s, rejected=%s, failed=%s).',
            response.get('received'),
            response.get('succeeded'),
            response.get('duplicates'),
            response.get('rejected'),
            response.get('failed'),
        )

    def close_spider(self, spider):
        """Deliver the final partial batch during normal pipeline shutdown."""
        self._flush_listing_buffer(spider)

    @staticmethod
    def _build_match_payload(payload):
        specifications = payload.get('specifications') or {}
        if not isinstance(specifications, dict):
            specifications = {}

        ram_gb = _capacity_gb(
            specifications.get('ram')
            or specifications.get('ram_capacity')
        )
        storage_gb = _capacity_gb(
            specifications.get('storage_capacity')
            or specifications.get('storage')
            or specifications.get('rom')
        )

        # Daraz packs a phone's whole description into its "RAM" field
        # ("+ 256GB UFS 3.1 storage ..."), so the first capacity found
        # there is often the storage. No phone has that much RAM, and
        # sending it made the backend refuse the listing outright. A laptop
        # does carry 64 GB and more, but not 512.
        ram_limit = 256 if payload.get('category') == 'laptops' else 32
        if ram_gb is not None and ram_gb > ram_limit:
            if storage_gb is None:
                storage_gb = ram_gb
            ram_gb = None

        match_payload = {
            'platform_code': str(
                payload.get('platform') or ''
            ).strip().lower() or None,
            'external_id': _optional_text(
                payload.get('external_id')
            ),
            'title': str(payload.get('model') or '').strip(),
            'brand': _optional_text(payload.get('brand')),
            'model': None,
            'ram_gb': ram_gb,
            'storage_gb': storage_gb,
            'color': _optional_text(payload.get('color')),
            'sku': _optional_text(payload.get('sku')),
            # The store name is sent so the backend can recognise, and
            # discard, a seller prefix the spider did not know about.
            'seller_name': _optional_text(
                (payload.get('seller') or {}).get('name')
                if isinstance(payload.get('seller'), dict)
                else payload.get('seller')
            ),
            # The normalized specification sheet lets the backend register a
            # genuinely new phone with real specs instead of guessing from
            # the title alone.
            'specifications': {
                str(label)[:80]: str(value)[:2000]
                for label, value in list(specifications.items())[:60]
            },
        }

        if payload.get('exact_model_title'):
            match_payload['exact_model_title'] = True

        category = _optional_text(payload.get('category'))
        if category:
            match_payload['category_slug'] = category

        if payload.get('match_only'):
            match_payload['allow_new_product'] = False
            # Lets the backend tell a copy wearing a product's name (a
            # "Galaxy Watch Ultra" at a tenth of its price) from the product.
            if payload.get('price'):
                match_payload['listing_price'] = payload['price']

        return match_payload

    @staticmethod
    def _build_seller(payload):
        seller = payload.get('seller')

        if isinstance(seller, str):
            name = _optional_text(seller)
            return {'name': name} if name else None

        if not isinstance(seller, dict):
            return None

        name = _optional_text(seller.get('name'))
        if name is None:
            return None

        return {
            'external_seller_id': _optional_text(
                seller.get('external_seller_id')
            ),
            'name': name,
            'profile_url': _optional_text(seller.get('profile_url')),
            'rating': seller.get('rating'),
            'review_count': seller.get('review_count', 0),
            'is_verified': bool(seller.get('is_verified', False)),
        }

    @staticmethod
    def _build_listing_payload(payload, product_variant_id=None):
        platform_code = str(payload.get('platform') or '').strip().lower()
        raw_payload = {
            'source': platform_code,
            'brand': payload.get('brand'),
            'model': payload.get('model'),
            'variant': payload.get('variant'),
            'color': payload.get('color'),
            'sku': payload.get('sku'),
            'availability': payload.get('availability'),
            'specifications': payload.get('specifications') or {},
            'image_urls': payload.get('image_urls') or [],
            'raw_html_path': payload.get('raw_html_path'),
        }

        listing_payload = {
            'platform_code': platform_code,
            'external_id': str(payload.get('external_id') or '').strip(),
            'title': str(payload.get('model') or '').strip(),
            'product_url': str(payload.get('product_url') or '').strip(),
            'current_price': payload.get('price'),
            'original_price': payload.get('original_price'),
            'currency': str(payload.get('currency') or 'PKR').upper(),
            'rating': payload.get('rating'),
            'review_count': payload.get('review_count') or 0,
            'warranty': _optional_text(payload.get('warranty')),
            'is_available': bool(payload.get('is_available')),
            # The gallery is a first-class field, not just raw context: the
            # backend stores it so the catalog can show the product.
            'image_urls': [
                str(image_url)[:1000]
                for image_url in (payload.get('image_urls') or [])
                if image_url
            ][:12],
            'scraped_at': _normalize_scraped_at(
                payload.get('scrape_timestamp')
            ),
            'seller': VextroApiIngestionPipeline._build_seller(payload),
            'raw_payload': raw_payload,
        }
        if product_variant_id is not None:
            listing_payload['product_variant_id'] = product_variant_id
        return listing_payload

    COMMUNITY_OPINIONS_PATH = (
        '/api/v1/internal/acquisition/community-opinions'
    )

    def _deliver_community_opinions(self, payload):
        """Send one phone's guide-site rating and opinions to the backend."""

        context = (
            f"source={payload.get('source')} "
            f"phone={str(payload.get('product_name'))[:80]}"
        )
        result = self._post_json(
            self.COMMUNITY_OPINIONS_PATH,
            {
                'source': payload.get('source'),
                'product_name': payload.get('product_name'),
                'catalog_name': payload.get('catalog_name'),
                'brand': _optional_text(payload.get('brand')),
                'source_url': payload.get('source_url'),
                'opinions_url': payload.get('opinions_url'),
                'rating': payload.get('rating'),
                'rating_count': payload.get('rating_count') or 0,
                'reference_price': payload.get('reference_price'),
                'opinions': [
                    {
                        'position': opinion.get('position'),
                        'author': _optional_text(opinion.get('author')),
                        'posted_at': opinion.get('posted_at'),
                        'text': opinion.get('text'),
                        'contact_removed': bool(
                            opinion.get('contact_removed')
                        ),
                    }
                    for opinion in (payload.get('opinions') or [])
                    if opinion.get('text')
                ],
                'scraped_at': _normalize_scraped_at(
                    payload.get('scrape_timestamp')
                ),
            },
            context,
        )

        if not result.get('matched'):
            raise AcquisitionDeliveryError(
                f'No catalog phone for this guide-site page ({context}).',
                error_type='product_unmatched',
                error_stage='matching',
                outcome='rejected',
            )

        logging.info(
            'Community opinions delivered (%s, created=%s, duplicates=%s).',
            context,
            result.get('created_count'),
            result.get('duplicate_count'),
        )

    def process_item(self, item, spider):
        payload = dict(ItemAdapter(item))

        if payload.get('opinions') is not None:
            # A guide-site page describes a phone, not an offer: it goes to
            # its own endpoint and a listing is never built from it.
            self._deliver_community_opinions(payload)
            return item

        context = self._context(payload)

        if payload.get('reviews') is not None:
            if str(payload.get('external_listing_id')) in self.unplaced_listing_ids:
                raise ReviewsOfTurnedAwayListingError(
                    'Reviews of a listing this run did not place in the catalogue.'
                )
            # Reviews are resolved by (platform, external listing id), so the
            # listing must already be in the database. Buffered listings are
            # delivered first, otherwise a brand-new product's reviews would
            # be rejected as "listing unresolved" until the next crawl.
            self._flush_listing_buffer(spider)

            review_payload = {
                'platform_code': str(
                    payload.get('platform') or ''
                ).strip().lower(),
                'external_listing_id': str(
                    payload.get('external_listing_id') or ''
                ).strip(),
                'source_url': str(
                    payload.get('source_url') or ''
                ).strip(),
                'reviews': payload.get('reviews') or [],
            }
            try:
                ingestion_result = self._post_json(
                    self.REVIEWS_PATH,
                    review_payload,
                    context,
                )
            except AcquisitionDeliveryError as exc:
                response_status = exc.metadata.get('http_status')
                if response_status == 404:
                    exc.error_type = 'review_listing_unresolved'
                elif response_status in {400, 422}:
                    exc.error_type = 'review_validation_failure'
                else:
                    exc.error_type = 'review_ingestion_failure'
                raise

            expected_total = len(review_payload['reviews'])
            processed_total = (
                ingestion_result.get('created_count', 0)
                + ingestion_result.get('duplicate_count', 0)
            )
            if (
                ingestion_result.get('listing_id') is None
                or processed_total != expected_total
            ):
                raise AcquisitionDeliveryError(
                    f'Review ingestion result was invalid ({context}).',
                    error_type='review_ingestion_failure',
                    error_stage='ingestion',
                )

            logging.info(
                'Secure review acquisition delivered batch '
                '(%s, created=%s, duplicates=%s).',
                context,
                ingestion_result.get('created_count'),
                ingestion_result.get('duplicate_count'),
            )
            self._send_signal(
                REVIEWS_INGESTED,
                created_count=int(
                    ingestion_result.get('created_count') or 0
                ),
                duplicate_count=int(
                    ingestion_result.get('duplicate_count') or 0
                ),
                spider=spider,
            )
            return item

        match_result = self._post_json(
            self.RESOLVE_PATH,
            self._build_match_payload(payload),
            context,
        )

        if match_result.get('product_created'):
            logging.info(
                'Canonical product created from marketplace discovery (%s).',
                context,
            )
            self._send_signal(
                CANONICAL_PRODUCT_CREATED,
                spider=spider,
            )

        product_variant_id = match_result.get('product_variant_id')
        if not match_result.get('matched') or not product_variant_id:
            reason = str(match_result.get('reason') or 'no safe match')
            self.unplaced_listing_ids.add(str(payload.get('external_id')))

            # The matcher suggests its best guess for nearly anything, so a
            # match-only listing is queued only when that guess is a
            # likely one; the rest resemble no catalogued product.
            if payload.get('match_only') and (
                not match_result.get('suggested_product_variant_id')
                or int(match_result.get('confidence') or 0)
                < MATCH_ONLY_REVIEW_CONFIDENCE
            ):
                logging.info(
                    'Passed over a match-only listing with no catalogue '
                    'product (%s, reason=%s).',
                    context,
                    reason,
                )
                raise NotInCatalogueError(
                    f'No catalogue product for a match-only listing ({context}).'
                )

            listing_payload = self._build_listing_payload(payload)
            pending_payload = {
                'platform_code': listing_payload['platform_code'],
                'external_id': listing_payload['external_id'],
                'title': listing_payload['title'],
                'product_url': listing_payload['product_url'],
                # The queue keeps the match request an administrator can
                # replay; whether its source may add products is not part
                # of it.
                'match_payload': {
                    key: value
                    for key, value in self._build_match_payload(payload).items()
                    if key not in ('allow_new_product', 'listing_price')
                },
                'listing_payload': listing_payload,
                'match_confidence': int(
                    match_result.get('confidence') or 0
                ),
                'match_reason': reason[:500],
                'suggested_product_variant_id': (
                    match_result.get('suggested_product_variant_id')
                ),
            }
            pending_result = self._post_json(
                self.PENDING_MATCHES_PATH,
                pending_payload,
                context,
            )
            logging.error(
                'Secure acquisition queued unresolved item '
                '(%s, pending_match_id=%s, confidence=%s, reason=%s).',
                context,
                pending_result.get('id'),
                match_result.get('confidence'),
                reason,
            )
            raise AcquisitionDeliveryError(
                f'No safe canonical product match ({context}).',
                error_type='product_unmatched',
                error_stage='matching',
                metadata={
                    'confidence': match_result.get('confidence'),
                    'pending_match_id': pending_result.get('id'),
                },
                outcome='rejected',
            )

        listing_payload = self._build_listing_payload(
            payload,
            product_variant_id,
        )
        batch_index = len(self.listing_buffer)
        self.listing_buffer.append({
            'item': item,
            'payload': listing_payload,
            'batch_index': batch_index,
        })
        self._send_signal(
            BULK_ITEM_QUEUED,
            item=item,
            spider=spider,
        )
        if len(self.listing_buffer) >= self.batch_size:
            self._flush_listing_buffer(spider)

        return item
