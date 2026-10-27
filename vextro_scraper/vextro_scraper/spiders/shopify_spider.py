"""Offers from stores that run on Shopify, read from the store's own feed.

Friends Home, Jalal Electronics and Telemart are Shopify stores. Every
Shopify store publishes each collection at
``/collections/<handle>/products.json``: up to 250 products a request, with
their price, stock, variants, vendor and images, the same data the store's
pages are built from. A store's robots.txt does not disallow it. A whole
collection takes one or two requests, where its HTML pages would take
dozens, so one spider class serves every such store and a store is added by
naming its address and collections.

What the feed says, and what this spider does with it:

* A product's variants are what the shopper chooses between (usually a
  colour). One listing is emitted per variant.
* A variant priced at Rs 0 is not for sale at any price; it is skipped.
* ``vendor`` is the brand at most stores, and the store's own name at
  some (Jalal). A store says which it is.
* The feed carries no reviews. A store whose product pages show its
  Judge.me review widget (Friends Home, Jalal) has each product page read
  too: the product's own rating and review count go on its listings, and
  the reviews written for that product go to VEXTRO's review store. The
  "reviews from across our store" carousel on the same page is about other
  products and is left alone.
"""

import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import scrapy

from vextro_scraper.items import ReviewBatchItem, SmartphoneItem
from vextro_scraper.normalizers import parse_price


PAGE_SIZE = 250

# A collection holding more pages than this is not what the spider was told
# it is (the whole store answering); the crawl of it stops there.
MAX_PAGES = 20

# Option names under which a store lists a variant's colour.
COLOUR_OPTIONS = {'color', 'colour'}

# The variant title Shopify gives a product that has no variants.
DEFAULT_VARIANT = 'default title'


class ShopifyStoreSpider(scrapy.Spider):
    """One Shopify store's collections, read as one catalogue category.

    A subclass names the store (``platform_code``, ``base_url``), the
    collections holding the category (``collections``) and the category
    itself (``catalog_category``).
    """

    name = None
    platform_code = None
    base_url = None
    catalog_category = None
    collections = ()
    # Whether the feed's vendor is the brand, or the store's own name.
    vendor_is_brand = True
    # A marketplace's sellers write their own titles; its listings only
    # join products another store catalogued.
    match_only = False
    # Whether the store's product pages carry its Judge.me review widget.
    reads_judgeme_reviews = False
    parser_version = 'shopify-v1-products-json'

    custom_settings = {
        'USER_AGENT': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
        'DOWNLOAD_DELAY': 1.5,
    }

    def __init__(self, product_urls=None, *args, **kwargs):
        """Read the store's collections, or only the product pages given.

        ``-a product_urls=<url>[,<url>...]`` re-reads just those products,
        each through its own ``/products/<handle>.json``.
        """

        super().__init__(*args, **kwargs)
        self.targeted_handles = [
            handle
            for handle in (
                self.product_handle(part)
                for part in str(product_urls or '').split(',')
            )
            if handle
        ]
        self.targeted = bool(str(product_urls or '').strip())
        self.finished_collections = set()
        self.failed_page_count = 0
        self.unpriced_count = 0
        self.emitted_ids = set()

    def product_handle(self, product_url):
        """Return the product handle of one of this store's product pages."""

        parsed = urlparse(str(product_url or '').strip())
        own_host = urlparse(self.base_url).netloc.lower().removeprefix('www.')

        if parsed.netloc.lower().removeprefix('www.') != own_host:
            return None

        match = re.match(r'^(?:/collections/[^/]+)?/products/([^/?#.]+)', parsed.path)
        return match.group(1) if match else None

    @property
    def full_crawl_completed(self):
        """True when every collection was read to its last page.

        Only then does a listing's absence mean the store stopped selling it.
        """

        return (
            not self.targeted
            and self.failed_page_count == 0
            and self.finished_collections == set(self.collections)
        )

    async def start(self):
        if self.targeted:
            for handle in self.targeted_handles:
                yield scrapy.Request(
                    f'{self.base_url}/products/{handle}.json',
                    callback=self.parse_product,
                    errback=self.page_failed,
                )
            return

        for collection in self.collections:
            yield self.collection_page(collection, page=1)

    def collection_page(self, collection, *, page):
        return scrapy.Request(
            f'{self.base_url}/collections/{collection}/products.json'
            f'?limit={PAGE_SIZE}&page={page}',
            callback=self.parse_collection,
            errback=self.page_failed,
            cb_kwargs={'collection': collection, 'page': page},
        )

    def page_failed(self, failure):
        self.failed_page_count += 1
        self.logger.error(
            '%s feed request failed: %s', self.platform_code, failure.getErrorMessage(),
        )

    @staticmethod
    def feed(response):
        try:
            return json.loads(response.text)
        except ValueError:
            return None

    def parse_collection(self, response, collection, page):
        data = self.feed(response)
        products = (data or {}).get('products')

        if not isinstance(products, list):
            self.failed_page_count += 1
            self.logger.error(
                '%s answered collection %r page %s with something that is '
                'not a product feed.',
                self.platform_code, collection, page,
            )
            return

        for product in products:
            yield from self.product_items(product)

        if len(products) < PAGE_SIZE:
            self.finished_collections.add(collection)
        elif page >= MAX_PAGES:
            self.failed_page_count += 1
            self.logger.error(
                '%s collection %r still had products after %s pages; '
                'stopped reading it.',
                self.platform_code, collection, page,
            )
        else:
            yield self.collection_page(collection, page=page + 1)

    def parse_product(self, response):
        product = (self.feed(response) or {}).get('product')

        if not isinstance(product, dict):
            self.failed_page_count += 1
            return

        yield from self.product_items(product)

    @staticmethod
    def variant_colour(product, variant):
        """Return the colour a variant is sold in, if the store names one."""

        for position, option in enumerate(product.get('options') or [], start=1):
            name = option.get('name') if isinstance(option, dict) else option
            if str(name or '').strip().lower() in COLOUR_OPTIONS:
                value = variant.get(f'option{position}')
                return str(value).strip() or None if value else None
        return None

    def product_items(self, product):
        """Yield one listing per variant of a product, with its reviews.

        Where the store's product page carries reviews, the listings wait
        for that page so they leave with the product's rating; if the page
        cannot be read they leave without it.
        """

        items = list(self.listing_items(product))
        if not items:
            return
        if not self.reads_judgeme_reviews:
            yield from items
            return

        yield scrapy.Request(
            f"{self.base_url}/products/{product['handle']}",
            callback=self.parse_review_page,
            errback=self.review_page_failed,
            cb_kwargs={'items': items},
            dont_filter=True,
        )

    def review_page_failed(self, failure):
        self.logger.warning(
            '%s product page could not be read for reviews: %s',
            self.platform_code, failure.getErrorMessage(),
        )
        yield from failure.request.cb_kwargs['items']

    def parse_review_page(self, response, items):
        """Put the product's Judge.me rating on its listings; send its reviews."""

        summary = response.css('.jdgm-rev-widg')
        rating = parse_price(summary.attrib.get('data-average-rating')) if summary else None
        count = int(summary.attrib.get('data-number-of-reviews') or 0) if summary else 0
        handle = response.url.rstrip('/').split('/products/')[-1].split('?')[0]

        for item in items:
            if count > 0 and rating:
                item['rating'] = float(rating)
                item['review_count'] = count
            yield item

        reviews = self.judgeme_reviews(response, handle)
        if reviews:
            batch = ReviewBatchItem()
            batch['platform'] = self.platform_code
            batch['external_listing_id'] = items[0]['external_id']
            batch['source_url'] = response.url
            batch['reviews'] = reviews
            yield batch

    def judgeme_reviews(self, response, handle):
        """Return the reviews written for this product, each once.

        The widget is printed twice on some pages, so a review is known by
        its Judge.me id. A review the widget files under another product
        (``data-product-url``) is not this product's.
        """

        crawler = getattr(self, 'crawler', None)
        limit = crawler.settings.getint('MAX_REVIEWS_PER_LISTING', 50) if crawler else 50
        reviews = []
        seen = set()

        for position, review in enumerate(response.css('.jdgm-rev-widg .jdgm-rev'), start=1):
            review_id = review.attrib.get('data-review-id')
            product_url = review.attrib.get('data-product-url') or ''
            if not review_id or review_id in seen:
                continue
            if product_url and f'/products/{handle}' not in product_url:
                continue
            seen.add(review_id)

            score = parse_price(review.css('.jdgm-rev__rating::attr(data-score)').get())
            if score is None or not 1 <= score <= 5:
                continue
            title = ' '.join(review.css('.jdgm-rev__title ::text').getall()).strip()
            body = ' '.join(
                part.strip() for part in review.css('.jdgm-rev__body ::text').getall() if part.strip()
            )
            text = '. '.join(part for part in (title, body) if part) or None

            reviews.append({
                'external_review_id': review_id,
                'reviewer_external_id': None,
                'reviewer_display_name': (
                    ' '.join(review.css('.jdgm-rev__author ::text').getall()).strip() or None
                ),
                'rating': int(score),
                'review_text': text,
                'reviewed_at': self.judgeme_time(
                    review.css('.jdgm-rev__timestamp::attr(data-content)').get()
                ),
                'verified_purchase': review.attrib.get('data-verified-buyer') == 'true',
                'helpful_count': int(review.attrib.get('data-thumb-up-count') or 0),
                'raw_metadata': {'source_position': position, 'review_app': 'judge.me'},
            })
            if len(reviews) >= limit:
                break

        return reviews

    @staticmethod
    def judgeme_time(value):
        """Return Judge.me's "2026-01-13 14:24:31 UTC" as ISO 8601, or None."""

        try:
            return datetime.strptime(
                str(value or '').strip(), '%Y-%m-%d %H:%M:%S UTC'
            ).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            return None

    def listing_items(self, product):
        """Yield one listing per variant of a product."""

        title = ' '.join(str(product.get('title') or '').split())
        handle = product.get('handle')
        variants = [
            variant for variant in product.get('variants') or []
            if isinstance(variant, dict)
        ]

        if not title or not handle or not variants:
            return

        images = [
            image.get('src')
            for image in product.get('images') or []
            if isinstance(image, dict) and image.get('src')
        ]
        vendor = ' '.join(str(product.get('vendor') or '').split()) or None
        several = len(variants) > 1

        for variant in variants:
            price = parse_price(variant.get('price'))

            if price is None or price <= 0:
                self.unpriced_count += 1
                continue

            external_id = (
                f"{product['id']}-{variant['id']}" if several else str(product['id'])
            )
            if external_id in self.emitted_ids:
                # A product filed in two of the collections read.
                continue
            self.emitted_ids.add(external_id)

            option_title = ' '.join(str(variant.get('title') or '').split())
            original = parse_price(variant.get('compare_at_price'))

            item = SmartphoneItem()
            item['platform'] = self.platform_code
            item['exact_model_title'] = not self.match_only
            item['external_id'] = external_id
            # Telemart sells a series as one product whose variants are its
            # models ("Kenwood Glory Pro ..." in "KGP-12C01S - 1.0 Ton"), so
            # a variant's name is part of what the listing sells.
            item['model'] = (
                f'{title} {option_title}'
                if several and option_title.lower() != DEFAULT_VARIANT
                else title
            )
            item['brand'] = vendor if self.vendor_is_brand else None
            item['variant'] = (
                option_title if option_title.lower() != DEFAULT_VARIANT else None
            )
            item['color'] = self.variant_colour(product, variant)
            # One SKU can name every colour of a product.
            item['sku'] = None
            item['seller'] = None
            item['price'] = price
            item['original_price'] = (
                original if original is not None and original > price else None
            )
            item['product_url'] = (
                f'{self.base_url}/products/{handle}'
                + (f"?variant={variant['id']}" if several else '')
            )
            item['availability'] = (
                'In Stock' if variant.get('available', True) else 'Out of Stock'
            )
            item['warranty'] = None
            item['rating'] = None
            item['review_count'] = 0
            item['specifications'] = {}
            item['image_urls'] = images
            item['scrape_timestamp'] = datetime.now(timezone.utc).isoformat()
            yield item

    def closed(self, reason):
        self.logger.info(
            '%s crawl closed (%s): listings=%s, unpriced=%s, collections '
            'finished=%s of %s, complete=%s.',
            self.platform_code,
            reason,
            len(self.emitted_ids),
            self.unpriced_count,
            len(self.finished_collections),
            len(self.collections),
            self.full_crawl_completed,
        )


# ---------------------------------------------------------------------------
# Stores
# ---------------------------------------------------------------------------


class FriendsHomeStore(ShopifyStoreSpider):
    """Friends Home: appliances only, each title ending "Model <code>"."""

    platform_code = 'friendshome'
    base_url = 'https://friendshome.pk'
    allowed_domains = ['friendshome.pk']
    reads_judgeme_reviews = True


class JalalStore(ShopifyStoreSpider):
    """Jalal Electronics, whose feed names the store, not the brand, as vendor."""

    platform_code = 'jalal'
    base_url = 'https://jalalelectronics.com'
    allowed_domains = ['jalalelectronics.com']
    vendor_is_brand = False
    reads_judgeme_reviews = True


class TelemartStore(ShopifyStoreSpider):
    """Telemart, a marketplace whose sellers write their own titles.

    Its pages hold Shopify's retired Product Reviews widget, empty in the
    page itself, so no reviews are read from it.
    """

    platform_code = 'telemart'
    base_url = 'https://telemart.pk'
    allowed_domains = ['telemart.pk']
    match_only = True


class FriendsHomeAirConditionerSpider(FriendsHomeStore):
    name = 'friendshome_acs'
    catalog_category = 'air-conditioners'
    # Its narrower AC collections (by tonnage, by brand) hold nothing this
    # one does not.
    collections = ('air-conditioners-ac-in-pakistan',)


class JalalAirConditionerSpider(JalalStore):
    name = 'jalal_acs'
    catalog_category = 'air-conditioners'
    collections = ('air-conditioners',)


class TelemartAirConditionerSpider(TelemartStore):
    name = 'telemart_acs'
    catalog_category = 'air-conditioners'
    collections = ('air-conditioners',)


class FriendsHomeTelevisionSpider(FriendsHomeStore):
    name = 'friendshome_tvs'
    catalog_category = 'televisions'
    collections = ('led-tv',)


class JalalTelevisionSpider(JalalStore):
    name = 'jalal_tvs'
    catalog_category = 'televisions'
    collections = ('led-tv',)


class TelemartTelevisionSpider(TelemartStore):
    name = 'telemart_tvs'
    catalog_category = 'televisions'
    # Its TVs are spread over these; they also hold monitors and lamps,
    # which the pipeline turns away.
    collections = ('tv-video', 'smart-leds', '4k-ultra-leds', 'led-tvs')


class FriendsHomeRefrigeratorSpider(FriendsHomeStore):
    name = 'friendshome_fridges'
    catalog_category = 'refrigerators'
    # Holds its fridges and its freezers both.
    collections = ('refrigerators-freezers',)


class JalalRefrigeratorSpider(JalalStore):
    name = 'jalal_fridges'
    catalog_category = 'refrigerators'
    collections = ('refrigerators', 'deep-freezers')


class TelemartRefrigeratorSpider(TelemartStore):
    name = 'telemart_fridges'
    catalog_category = 'refrigerators'
    collections = ('refrigerators', 'deep-freezers')


class FriendsHomeWashingMachineSpider(FriendsHomeStore):
    name = 'friendshome_washers'
    catalog_category = 'washing-machines'
    # Holds its washers, washer-dryers and dryers; the narrower ones hold
    # nothing more.
    collections = ('washing-machines-dryers',)


class JalalWashingMachineSpider(JalalStore):
    name = 'jalal_washers'
    catalog_category = 'washing-machines'
    collections = ('washing-machines',)


class TelemartWashingMachineSpider(TelemartStore):
    name = 'telemart_washers'
    catalog_category = 'washing-machines'
    collections = ('washing-machines',)


class FriendsHomeMicrowaveSpider(FriendsHomeStore):
    name = 'friendshome_microwaves'
    catalog_category = 'microwave-ovens'
    collections = ('microwave-ovens-pakistan',)


class JalalMicrowaveSpider(JalalStore):
    name = 'jalal_microwaves'
    catalog_category = 'microwave-ovens'
    # Its microwave collection also holds baking ovens, which the pipeline
    # turns away.
    collections = ('microwave-oven', 'built-in-microwave-oven')


class TelemartMicrowaveSpider(TelemartStore):
    name = 'telemart_microwaves'
    catalog_category = 'microwave-ovens'
    collections = ('microwave-ovens',)
