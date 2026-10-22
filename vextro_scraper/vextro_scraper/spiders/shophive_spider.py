"""Shophive smartphone offers, read from the store's own catalogue feed.

Shophive runs on Magento 2, whose storefront publishes its catalogue through
a GraphQL endpoint: the same data its product pages are built from, with no
login. Reading it takes four requests for every phone the shop lists, where
walking the HTML pages would take about 170, and it states each colour's
price outright instead of leaving it inside page scripts.

What the feed says, and what this spider does with it:

* Every RAM and storage combination is a product of its own; its colours
  are options on it. One listing is emitted per colour.
* A colour can cost more than the others. Its price is the product's price
  plus that colour's surcharge.
* Unreleased phones are listed at Rs 0. Nothing can be bought at that
  price, so they are not offers and are skipped.
* A priced phone whose shipping reads "Coming Soon" cannot be bought yet;
  it is kept with its price and marked unavailable.
* The specification table sometimes contradicts the product's name (a
  "6GB" page whose table says 4GB). The name is what the shop sells the
  phone as, so it wins and the table only fills what the name leaves out.

The feed is trusted only as far as it can be checked. It silently ignores
a filter it does not support and answers with the whole store instead
(asking for a product by its ``url_key`` returns all 8,500 products, from
televisions to coffee machines). So phones are only ever asked for by
category, every product received must be filed under a phone category, and
a category that answers with far more products than it holds stops the
crawl.
"""

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy
from scrapy.exceptions import CloseSpider
from scrapy.http import JsonRequest

from vextro_scraper.items import SmartphoneItem
from vextro_scraper.normalizers import parse_price


BASE_URL = 'https://www.shophive.com'
GRAPHQL_URL = f'{BASE_URL}/graphql'

# The two places Shophive files phones. iPhones live under the Apple store,
# not under "mobile-phones".
CATEGORY_PATHS = ('mobile-phones', 'apple/iphone')

PAGE_SIZE = 50
# Shophive lists about 160 phones. This is the stop that keeps a change on
# their side from turning into an endless crawl.
MAX_PAGES_PER_CATEGORY = 40

CATEGORIES_QUERY = '''
query($paths: [String]) {
  categoryList(filters: {url_path: {in: $paths}}) {
    uid
    url_path
    product_count
  }
}
'''

PRODUCTS_QUERY = '''
query($filter: ProductAttributeFilterInput!, $page: Int!, $size: Int!) {
  products(filter: $filter, pageSize: $size, currentPage: $page) {
    total_count
    page_info { current_page total_pages }
    items {
      sku
      name
      url_key
      url_suffix
      stock_status
      categories { url_path }
      price_range {
        minimum_price {
          regular_price { value }
          final_price { value }
        }
      }
      image { url }
      media_gallery { url position disabled }
      rating_summary
      review_count
      ... on CustomizableProductInterface {
        options {
          title
          ... on CustomizableRadioOption {
            radio_value: value { option_type_id title price price_type }
          }
          ... on CustomizableDropDownOption {
            dropdown_value: value { option_type_id title price price_type }
          }
        }
      }
      custom_attributesV2(filters: {is_visible_on_front: true}) {
        items {
          code
          ... on AttributeValue { value }
          ... on AttributeSelectedOptions { selected_options { label } }
        }
      }
    }
  }
}
'''

# "8GB 256GB", "4GB +64GB", "12GB/256GB", "12GB 1TB": RAM, then storage.
MEMORY_PAIR = re.compile(
    r'\b(\d{1,2})\s*GB\s*[+/]?\s*(\d{1,4})\s*(GB|TB)\b',
    re.I,
)
# A lone figure, as on iPhones: "512GB", "2TB".
MEMORY_SINGLE = re.compile(r'\b(\d{1,4})\s*(GB|TB)\b', re.I)
PTA_APPROVED = re.compile(r'\bPTA\s+Approved\b', re.I)
SECOND_GENERATION = re.compile(r'(?<![A-Za-z0-9])2G(?![A-Za-z0-9])', re.I)
BRACKETED = re.compile(r'\(\s*([^()]*?)\s*\)')
MODEL_YEAR = re.compile(r'(?:19|20)\d{2}')

COLOUR_OPTION_TITLE = re.compile(r'^\s*colou?rs?\s*$', re.I)
# A short code mixing letters and digits: "Mh5U4", "MXW23".
PART_NUMBER = re.compile(r'(?=[A-Za-z0-9]*\d)(?=[A-Za-z0-9]*[A-Za-z])[A-Za-z0-9]{4,6}')

# Values Shophive types where it has nothing to state.
EMPTY_VALUES = frozenset({
    '', 'n/a', 'na', 'none', 'not available', 'info not available',
    'info not availible',
})

# The feed's brand attribute, where it differs from the manufacturer's name.
BRAND_NAMES = {'mi': 'Xiaomi', 'itel': 'Itel'}

# Specification rows worth keeping, under the labels the backend knows.
SPECIFICATION_LABELS = (
    ('c2c_operating_system', 'operating_system'),
    ('c2c_screen_size', 'display'),
    ('c2c_camera_pixel', 'main_camera'),
    ('c2c_dual_sim', 'dual_sim'),
    ('c2c_water_resistant', 'water_resistant'),
    ('c2c_expandable_memory', 'expandable_memory'),
)


class ShophiveFeedError(RuntimeError):
    """Shophive's catalogue feed could not be read."""

    error_type = 'feed_error'
    error_stage = 'fetch'


def stated(value):
    """Return a feed value as text, or ``None`` when it states nothing."""

    text = ' '.join(str(value if value is not None else '').split())

    return None if text.lower() in EMPTY_VALUES else text


def capacity_gb(value, unit):
    return int(value) * (1024 if str(unit).lower() == 'tb' else 1)


def parse_name(name):
    """Split a product name into ``(model, ram_gb, storage_gb, pta_approved)``.

    "Samsung Galaxy A17 6GB 128GB" is the phone "Samsung Galaxy A17" in one
    configuration; the memory figures and "PTA Approved" describe the offer,
    not the model, and would stop the phone matching the same model on
    another marketplace.
    """

    text = ' '.join(str(name or '').split())
    ram_gb = storage_gb = None

    pair = MEMORY_PAIR.search(text)
    if pair:
        ram_gb = int(pair.group(1))
        storage_gb = capacity_gb(pair.group(2), pair.group(3))
        text = text[:pair.start()] + ' ' + text[pair.end():]
    else:
        single = MEMORY_SINGLE.search(text)
        if single:
            figure = capacity_gb(single.group(1), single.group(2))
            # No phone has 32GB of RAM or 16GB of storage on its own line.
            if figure >= 32:
                storage_gb = figure
            else:
                ram_gb = figure
            text = text[:single.start()] + ' ' + text[single.end():]

    pta_approved = bool(PTA_APPROVED.search(text))
    text = PTA_APPROVED.sub(' ', text)
    # Shophive labels its feature phones "2G". No model is told apart by
    # it, and other marketplaces name the same phones without it.
    text = SECOND_GENERATION.sub(' ', text)
    # "(Special Edition)" is part of the model's name and other
    # marketplaces write it without brackets. A bracketed year stays as
    # it is: "(2024)" is how every marketplace marks a feature phone's
    # generation.
    text = BRACKETED.sub(
        lambda match: (
            match.group(0)
            if MODEL_YEAR.fullmatch(match.group(1))
            else f' {match.group(1)} '
        ),
        text,
    )
    text = re.sub(r'\(\s*\)', ' ', text)
    model = ' '.join(text.split()).strip(' -–—_|/,;:.')

    return model, ram_gb, storage_gb, pta_approved


def tidy_colour(title):
    """Spell a colour option consistently: " night pulse" -> "Night Pulse"."""

    words = str(title or '').split()

    # Shophive appends Apple's part number to iPad colours: "Space Grey
    # Mh5U4". It names the configuration, not the colour.
    if len(words) > 1 and PART_NUMBER.fullmatch(words[-1]):
        words.pop()

    if not words:
        return None

    return ' '.join(
        word.capitalize() if word.islower() or word.isupper() else word
        for word in words
    )[:80]


def normalize_warranty(value):
    """Return the warranty as the shop states it, readable on its own."""

    text = stated(value)

    if text is None:
        return None

    if re.match(r'^\d+\s*(?:year|month)s?\b', text, re.I) and not re.search(
        r'warranty', text, re.I,
    ):
        text = f'{text} Warranty'

    return text[:255]


def colour_image(colour, image_urls):
    """Return the gallery photo that shows a colour, when one clearly does.

    The feed does not say which photo is which colour, but the files are
    named after them ("..._awesome_charcol.jpg"). A word shared by every
    file ("awesome") says nothing, so each word counts for less the more
    files carry it, and a photo is chosen only when it beats all others.
    """

    words = re.findall(r'[a-z0-9]+', str(colour or '').lower())
    names = [
        re.sub(r'[^a-z0-9]+', '', urlparse(url).path.rsplit('/', 1)[-1].lower())
        for url in image_urls
    ]

    if not words or len(names) < 2:
        return None

    scores = [0.0] * len(names)
    for word in words:
        carriers = [index for index, name in enumerate(names) if word in name]
        for index in carriers:
            scores[index] += 1 / len(carriers)

    best = max(range(len(names)), key=scores.__getitem__)
    runner_up = max(
        (score for index, score in enumerate(scores) if index != best),
        default=0.0,
    )

    if scores[best] < 0.5 or scores[best] <= runner_up:
        return None

    return image_urls[best]


class ShophiveSpider(scrapy.Spider):
    name = 'shophive_smartphones'
    platform_code = 'shophive'
    catalog_category = 'mobile-phones'
    parser_version = 'shophive-v1-storefront-feed'
    allowed_domains = ['shophive.com']

    # The store categories this spider reads, and the subcategories within
    # them that hold something else (drawing pads, accessories).
    category_paths = CATEGORY_PATHS
    excluded_paths = ()

    custom_settings = {
        'USER_AGENT': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
        'DOWNLOAD_DELAY': 1.5,
    }

    def __init__(self, product_urls=None, *args, **kwargs):
        """Read every phone Shophive lists, or only the pages given.

        ``-a product_urls=<url>[,<url>...]`` re-reads just those phones,
        which is how the backend refreshes one product when a shopper
        opens it. The feed cannot be asked for a product by its address,
        so such a run walks the phone categories like a full crawl, emits
        only the phones named and stops once it has found them all. It is
        never counted as a full crawl.
        """

        super().__init__(*args, **kwargs)
        self.targeted = bool(str(product_urls or '').strip())
        self.targeted_keys = {
            key
            for key in (
                self.url_key(part)
                for part in str(product_urls or '').split(',')
            )
            if key
        }
        self.found_keys = set()
        # category path -> the number of phones its own record says it has.
        self.category_sizes = {}
        # category path -> the number of phones Shophive says it holds.
        self.expected_counts = {}
        # category path -> the SKUs this run received from it.
        self.received_skus = {}
        self.finished_categories = set()
        self.emitted_skus = set()
        self.failed_page_count = 0
        self.unpriced_count = 0

    @staticmethod
    def url_key(product_url):
        """Return the feed's key for a product page address, if it is one."""

        parsed = urlparse(str(product_url or '').strip())

        if not parsed.netloc.lower().endswith('shophive.com'):
            return None

        segments = [segment for segment in parsed.path.split('/') if segment]

        return segments[0] if len(segments) == 1 else None

    @property
    def full_crawl_completed(self):
        """True when every phone Shophive lists was received.

        The feed states how many phones each category holds, so the run
        is complete only when both categories were read to their last page
        and delivered exactly that many. Only then does a listing's
        absence mean the shop stopped offering it.
        """

        return (
            not self.targeted
            and self.failed_page_count == 0
            and all(
                path in self.finished_categories
                and self.expected_counts.get(path) is not None
                and len(self.received_skus.get(path, ()))
                == self.expected_counts[path]
                for path in self.category_paths
            )
        )

    async def start(self):
        if self.targeted and not self.targeted_keys:
            self.logger.warning(
                'None of the pages given is a Shophive product page; '
                'nothing to refresh.'
            )
            return

        yield JsonRequest(
            GRAPHQL_URL,
            data={
                'query': CATEGORIES_QUERY,
                'variables': {'paths': list(self.category_paths)},
            },
            callback=self.parse_categories,
            errback=self.feed_fetch_error,
        )

    def products_request(self, category_uid, *, page, category):
        return JsonRequest(
            GRAPHQL_URL,
            data={
                'query': PRODUCTS_QUERY,
                'variables': {
                    # The one product filter this spider uses. The feed
                    # honours it; it does not honour ``url_key``.
                    'filter': {'category_uid': {'eq': category_uid}},
                    'page': page,
                    'size': PAGE_SIZE,
                },
            },
            callback=self.parse_products,
            errback=self.feed_fetch_error,
            cb_kwargs={
                'category_uid': category_uid,
                'page': page,
                'category': category,
            },
        )

    def feed_fetch_error(self, failure):
        """Record a lost request so the run is not mistaken for a full one."""

        self.failed_page_count += 1
        error = ShophiveFeedError('Shophive feed request failed.')
        cause = getattr(failure, 'value', None)
        if cause is None:
            raise error
        raise error from cause

    def feed_data(self, response):
        """Return the feed's ``data`` object, or fail the page loudly."""

        try:
            body = json.loads(response.text)
        except ValueError as error:
            self.failed_page_count += 1
            raise ShophiveFeedError(
                'Shophive feed answered with something that is not JSON.'
            ) from error

        data = body.get('data') if isinstance(body, dict) else None
        errors = body.get('errors') if isinstance(body, dict) else None

        if errors or not isinstance(data, dict):
            self.failed_page_count += 1
            messages = '; '.join(
                str(entry.get('message'))[:200]
                for entry in (errors or [])
                if isinstance(entry, dict)
            )
            raise ShophiveFeedError(
                f'Shophive feed reported an error: {messages or "no data"}'
            )

        return data

    def parse_categories(self, response):
        """Open each phone category by the identifier the feed gives it."""

        categories = {
            category.get('url_path'): category
            for category in self.feed_data(response).get('categoryList') or []
            if isinstance(category, dict)
        }

        for path in self.category_paths:
            category = categories.get(path)

            if not category or not category.get('uid'):
                # Without the category its phones cannot be read, and the
                # run must not be taken for a complete one.
                self.failed_page_count += 1
                self.logger.error(
                    'Shophive no longer has the category %r.', path,
                )
                continue

            self.category_sizes[path] = int(category.get('product_count') or 0)

            yield self.products_request(
                category['uid'],
                page=1,
                category=path,
            )

    @staticmethod
    def filed_under(product, category):
        """Report whether the feed files a product under a phone category."""

        return any(
            isinstance(entry, dict)
            and (
                entry.get('url_path') == category
                or str(entry.get('url_path') or '').startswith(f'{category}/')
            )
            for entry in product.get('categories') or []
        )

    def refuse_unfiltered_answer(self, category, total_count, entries):
        """Stop the crawl when the feed did not apply the category filter.

        An ignored filter is not an error to the feed: it answers with the
        whole store. Nothing from such an answer may reach the catalogue.
        """

        strangers = [
            entry.get('name')
            for entry in entries
            if not self.filed_under(entry, category)
        ]
        ceiling = self.category_sizes.get(category, 0) * 2 + 20

        if not strangers and total_count <= ceiling:
            return

        self.failed_page_count += 1
        self.logger.error(
            'Shophive answered for %r with products outside it '
            '(total=%s, category holds %s, e.g. %r). Crawl stopped.',
            category,
            total_count,
            self.category_sizes.get(category),
            strangers[:3],
        )
        raise CloseSpider('shophive_category_filter_ignored')

    def parse_products(self, response, category_uid, page, category):
        products = self.feed_data(response).get('products') or {}
        entries = [
            entry
            for entry in products.get('items') or []
            if isinstance(entry, dict) and entry.get('sku')
        ]
        total_count = int(products.get('total_count') or 0)

        self.refuse_unfiltered_answer(category, total_count, entries)

        self.expected_counts[category] = total_count
        self.received_skus.setdefault(category, set()).update(
            entry['sku'] for entry in entries
        )

        for entry in entries:
            if entry['sku'] in self.emitted_skus:
                continue

            if any(self.filed_under(entry, path) for path in self.excluded_paths):
                continue

            if self.targeted:
                if entry.get('url_key') not in self.targeted_keys:
                    continue
                self.found_keys.add(entry['url_key'])

            self.emitted_skus.add(entry['sku'])
            yield from self.product_items(entry)

        total_pages = int(
            (products.get('page_info') or {}).get('total_pages') or 0
        )

        if self.targeted and self.found_keys >= self.targeted_keys:
            # Every phone asked for has been read; the rest is not needed.
            return

        if page < min(total_pages, MAX_PAGES_PER_CATEGORY):
            yield self.products_request(
                category_uid,
                page=page + 1,
                category=category,
            )
        elif page >= total_pages:
            self.finished_categories.add(category)

    @staticmethod
    def attributes(product):
        """Return the product's specification rows as ``{code: text}``."""

        values = {}
        container = product.get('custom_attributesV2')
        entries = container.get('items') if isinstance(container, dict) else None

        for entry in entries or []:
            if not isinstance(entry, dict) or not entry.get('code'):
                continue

            options = entry.get('selected_options')
            if isinstance(options, list) and options:
                text = ', '.join(
                    str(option.get('label'))
                    for option in options
                    if isinstance(option, dict) and option.get('label')
                )
            else:
                text = entry.get('value')

            text = stated(text)
            if text is not None:
                values[entry['code']] = text

        return values

    @staticmethod
    def colour_options(product):
        """Return ``[(option_id, colour, surcharge, surcharge_type), ...]``."""

        colours = []

        for option in product.get('options') or []:
            if not isinstance(option, dict) or not COLOUR_OPTION_TITLE.match(
                str(option.get('title') or '')
            ):
                continue

            for value in (
                option.get('radio_value') or option.get('dropdown_value') or []
            ):
                if not isinstance(value, dict):
                    continue

                colour = tidy_colour(value.get('title'))
                option_id = value.get('option_type_id')

                if colour is None or option_id is None:
                    continue

                colours.append((
                    option_id,
                    colour,
                    float(value.get('price') or 0),
                    str(value.get('price_type') or 'FIXED').upper(),
                ))

        return colours

    @staticmethod
    def with_surcharge(price, surcharge, surcharge_type):
        if price is None:
            return None

        if surcharge_type == 'PERCENT':
            return round(price * (1 + surcharge / 100), 2)

        return price + surcharge

    def product_items(self, product):
        """Yield one listing per colour of a product, or one without colour."""

        minimum = (
            (product.get('price_range') or {}).get('minimum_price') or {}
        )
        price = parse_price((minimum.get('final_price') or {}).get('value'))

        if price is None or price <= 0:
            # Listed, but not yet for sale at any price.
            self.unpriced_count += 1
            return

        regular_price = parse_price(
            (minimum.get('regular_price') or {}).get('value')
        )
        attributes = self.attributes(product)
        model, ram_gb, storage_gb, pta_approved = parse_name(
            product.get('name')
        )

        if not model or not product.get('url_key'):
            return

        if storage_gb is None:
            stored = MEMORY_SINGLE.search(
                attributes.get('c2c_internal_memory') or ''
            )
            if stored:
                storage_gb = capacity_gb(stored.group(1), stored.group(2))

        specifications = {}
        if ram_gb is not None:
            specifications['ram'] = f'{ram_gb}GB'
        if storage_gb is not None:
            specifications['storage_capacity'] = f'{storage_gb}GB'
        for code, label in SPECIFICATION_LABELS:
            if code in attributes:
                specifications[label] = attributes[code]
        if pta_approved:
            specifications['pta_status'] = 'PTA Approved'

        gallery = [
            image.get('url')
            for image in sorted(
                (
                    image
                    for image in product.get('media_gallery') or []
                    if isinstance(image, dict) and not image.get('disabled')
                ),
                key=lambda image: image.get('position') or 0,
            )
            if image.get('url')
        ]
        main_image = (product.get('image') or {}).get('url')
        images = list(dict.fromkeys(
            url for url in [main_image, *gallery] if url
        ))

        review_count = int(product.get('review_count') or 0)
        rating = (
            round(float(product.get('rating_summary') or 0) / 20, 2)
            if review_count
            else None
        )
        shipping = attributes.get('c2c_shipping')
        available = (
            product.get('stock_status') == 'IN_STOCK'
            and (shipping or '').lower() != 'coming soon'
        )
        brand = attributes.get('manufacturer')
        variant = ' / '.join(
            part
            for part in (
                f'{ram_gb}GB RAM' if ram_gb is not None else None,
                f'{storage_gb}GB' if storage_gb is not None else None,
            )
            if part
        )

        base = SmartphoneItem()
        base['platform'] = 'Shophive'
        # Shophive names each phone itself; no seller writes the title.
        base['exact_model_title'] = True
        base['model'] = model
        base['brand'] = BRAND_NAMES.get(str(brand or '').lower(), brand)
        base['variant'] = variant or None
        # The SKU names one memory configuration in every colour; sending
        # it would file all its colours under the first one's variant.
        base['sku'] = None
        base['seller'] = None
        base['product_url'] = (
            f"{BASE_URL}/{product['url_key']}"
            f"{product.get('url_suffix') or '/'}"
        )
        base['availability'] = 'In Stock' if available else 'Out of Stock'
        base['warranty'] = normalize_warranty(attributes.get('c2c_warranty'))
        base['rating'] = rating
        base['review_count'] = review_count
        base['specifications'] = specifications
        base['scrape_timestamp'] = datetime.now(timezone.utc).isoformat()

        colours = self.colour_options(product)

        if not colours:
            item = base
            item['external_id'] = str(product['sku'])
            item['color'] = None
            item['price'] = price
            item['original_price'] = (
                regular_price
                if regular_price is not None and regular_price > price
                else None
            )
            item['image_urls'] = images
            yield item
            return

        for option_id, colour, surcharge, surcharge_type in colours:
            item = base.deepcopy()
            item['external_id'] = f"{product['sku']}-{option_id}"
            item['color'] = colour
            item['price'] = self.with_surcharge(
                price, surcharge, surcharge_type,
            )
            original = self.with_surcharge(
                regular_price, surcharge, surcharge_type,
            )
            item['original_price'] = (
                original
                if original is not None and original > item['price']
                else None
            )
            own_image = colour_image(colour, images)
            item['image_urls'] = list(dict.fromkeys(
                url for url in [own_image, *images] if url
            ))
            yield item

    def closed(self, reason):
        missing = sorted(self.targeted_keys - self.found_keys)

        if self.targeted and missing:
            self.logger.warning(
                'Shophive no longer lists %s of the phones asked for: %s',
                len(missing),
                missing[:10],
            )

        self.logger.info(
            'Shophive crawl closed (%s): phones read=%s, not yet '
            'priced=%s, expected per category=%s, complete=%s.',
            reason,
            len(self.emitted_skus),
            self.unpriced_count,
            self.expected_counts,
            self.full_crawl_completed,
        )


class ShophiveTabletSpider(ShophiveSpider):
    """Shophive's tablets: the Apple iPad store and the tablets category.

    The tablets category also holds Wacom, XP-Pen and Penpower drawing
    pads, Kindle e-readers and tablet accessories, each in a subcategory of
    its own; those are skipped. Drawing pads filed in no subcategory are
    caught by the pipeline's tablet rules.
    """

    name = 'shophive_tablets'
    catalog_category = 'tablets'
    parser_version = 'shophive-tablets-v1'
    category_paths = ('apple/ipad', 'tablets')
    excluded_paths = (
        'tablets/wacom',
        'tablets/xp-pen',
        'tablets/penpower',
        'tablets/tablet-accessories',
        'tablets/amazon-kindle',
    )
