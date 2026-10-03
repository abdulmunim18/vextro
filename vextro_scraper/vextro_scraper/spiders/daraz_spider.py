import scrapy
import json
from math import ceil
from datetime import datetime, timezone
from urllib.parse import urljoin
from vextro_scraper.items import ReviewBatchItem, SmartphoneItem
from vextro_scraper.normalizers import (
    optional_text,
    parse_count,
    parse_daraz_specification_sheet,
    parse_price,
    parse_rating,
)


class DarazParserError(ValueError):
    """A Daraz response could not be parsed as the expected JSON payload."""

    error_type = "invalid_marketplace_response"
    error_stage = "parse"


class DarazReviewParserError(ValueError):
    """Daraz returned a review payload that does not match its contract."""

    error_type = "review_parse_error"
    error_stage = "parse"


class DarazReviewFetchError(RuntimeError):
    """The Daraz review API could not be reached."""

    error_type = "review_fetch_error"
    error_stage = "fetch"


class DarazSpider(scrapy.Spider):
    name = "daraz_smartphones"
    platform_code = "daraz"
    parser_version = "daraz-v2-offers-reviews"
    allowed_domains = ["daraz.pk"]

    # We use the internal AJAX API for reliable scraping. It is the same
    # service the product page itself renders from, so its ``price`` field is
    # the current selling price and the source of truth for this platform.
    start_urls = ["https://www.daraz.pk/smartphones/?ajax=true"]

    # Daraz publishes each item's reviews through its own JSON API. The
    # catalog item already tells us whether any exist, so only items that
    # advertise reviews are fetched.
    REVIEW_API_URL = "https://my.daraz.pk/pdp/review/getReviewList"
    REVIEW_PAGE_SIZE = 20

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DOWNLOAD_DELAY': 2, # Respectful scraping
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.review_listings_requested = 0

    @staticmethod
    def extract_specifications(item_data):
        """Normalize attribute payloads included in Daraz list responses."""

        raw_attributes = (
            item_data.get('attributes')
            or item_data.get('specifications')
            or item_data.get('productAttributes')
            or {}
        )
        specifications = {}

        if isinstance(raw_attributes, dict):
            specifications.update(raw_attributes)
        elif isinstance(raw_attributes, list):
            for attribute in raw_attributes:
                if not isinstance(attribute, dict):
                    continue

                label = (
                    attribute.get('name')
                    or attribute.get('label')
                    or attribute.get('key')
                )
                value = (
                    attribute.get('value')
                    or attribute.get('values')
                    or attribute.get('text')
                )
                if label and value not in (None, ''):
                    specifications[str(label)] = value

        # Daraz's richest specification source is the packed description
        # sheet on each catalog item. Explicit attributes still win.
        for label, value in parse_daraz_specification_sheet(
            item_data.get('description')
        ).items():
            specifications.setdefault(label, value)

        return specifications

    @staticmethod
    def extract_seller(item_data):
        """Return the marketplace seller behind one Daraz catalog item."""

        name = optional_text(item_data.get('sellerName'), max_length=255)

        if name is None:
            return None

        return {
            'name': name,
            'external_seller_id': optional_text(
                item_data.get('sellerId'),
                max_length=150,
            ),
        }

    @staticmethod
    def extract_prices(item_data):
        """Return ``(current_price, original_price)`` for one catalog item.

        ``price`` is Daraz's current selling price. ``originalPriceShow`` is
        the struck-through list price and is an empty string when nothing is
        discounted. A list price at or below the selling price is marketing
        noise, not a discount, so it is dropped.
        """

        current_price = parse_price(
            item_data.get('price')
            or item_data.get('priceShow')
        )
        original_price = parse_price(
            item_data.get('originalPriceShow')
            or item_data.get('originalPrice')
        )

        if (
            original_price is not None
            and current_price is not None
            and original_price <= current_price
        ):
            original_price = None

        return current_price, original_price

    def _max_review_listings(self):
        """Return how many listings may be enriched with reviews per run."""

        crawler = getattr(self, 'crawler', None)

        if crawler is None:
            return 150

        if not crawler.settings.getbool('DARAZ_REVIEWS_ENABLED', True):
            return 0

        return max(
            0,
            crawler.settings.getint('MAX_REVIEW_LISTINGS_PER_RUN', 150),
        )

    def _max_reviews_per_listing(self):
        crawler = getattr(self, 'crawler', None)

        if crawler is None:
            return 50

        return max(
            0,
            min(
                crawler.settings.getint('MAX_REVIEWS_PER_LISTING', 50),
                100,
            ),
        )

    def parse(self, response):
        try:
            data = json.loads(response.text)
        except json.JSONDecodeError as exc:
            self.logger.error("Failed to parse JSON response from Daraz API.")
            raise DarazParserError(
                "Daraz returned malformed JSON."
            ) from exc

        # Extract products list from JSON response
        mods = data.get("mods", {})
        list_items = mods.get("listItems", [])

        for item_data in list_items:
            item = SmartphoneItem()
            item['platform'] = 'Daraz'

            # Get the external ID (itemId)
            external_id = str(item_data.get('itemId') or '').strip()
            item['external_id'] = external_id

            # Clean URL
            product_url = (
                item_data.get('productUrl')
                or item_data.get('itemUrl')
                or item_data.get('item_url')
                or ''
            )
            product_url = str(product_url).strip()
            if product_url.lower() in {'none', 'null', 'n/a'}:
                product_url = ''
            if product_url.startswith('//'):
                product_url = 'https:' + product_url
            elif product_url.startswith('/'):
                product_url = urljoin('https://www.daraz.pk', product_url)
            elif product_url and not product_url.startswith(('http://', 'https://')):
                product_url = urljoin('https://www.daraz.pk', product_url)
            elif not product_url and external_id:
                product_url = (
                    'https://www.daraz.pk/products/'
                    f'i{external_id}.html'
                )
            item['product_url'] = product_url

            # Get Title and Price
            item['model'] = item_data.get('name', '')
            item['brand'] = (
                item_data.get('brandName')
                or item_data.get('brand')
                or item_data.get('brand_name')
            )

            current_price, original_price = self.extract_prices(item_data)
            item['price'] = current_price
            item['original_price'] = original_price

            # Marketplace review aggregates shown on the catalog card.
            item['rating'] = parse_rating(item_data.get('ratingScore'))
            review_count = parse_count(
                item_data.get('review')
                or item_data.get('reviewCount')
            )
            item['review_count'] = review_count or 0

            item['seller'] = self.extract_seller(item_data)
            item['sku'] = optional_text(
                item_data.get('sku')
                or item_data.get('skuId'),
                max_length=120,
            )

            # Daraz currently exposes the primary catalog image on each
            # AJAX list item. Keep fallbacks for payload variants seen on
            # category pages and normalize protocol-relative URLs.
            raw_images = (
                item_data.get('images')
                or item_data.get('image')
                or item_data.get('imageUrl')
                or item_data.get('thumbUrl')
                or []
            )
            if isinstance(raw_images, str):
                raw_images = [raw_images]
            elif isinstance(raw_images, dict):
                raw_images = list(raw_images.values())

            item['image_urls'] = [
                ('https:' + image_url)
                if image_url.startswith('//')
                else image_url
                for image_url in raw_images
                if isinstance(image_url, str) and image_url
            ]
            item['specifications'] = self.extract_specifications(
                item_data
            )

            # Availability
            in_stock = item_data.get('inStock', False)
            item['availability'] = (
                'In Stock' if in_stock else 'Out of Stock'
            )

            # RAM, storage and colour are derived from the normalized
            # specification sheet and the title. Writing placeholder text
            # here used to push "Standard"/"N/A" into the catalog.
            item['variant'] = None
            item['color'] = None
            item['warranty'] = None

            item['scrape_timestamp'] = datetime.now(timezone.utc).isoformat()

            yield item

            review_request = self._build_review_request(
                external_id,
                review_count,
            )
            if review_request is not None:
                yield review_request

        # PAGINATION: Check if there's a next page and follow it
        main_info = data.get("mainInfo", {})
        page = int(main_info.get('page', 1))
        page_size = max(1, int(main_info.get('pageSize', 40)))
        total_pages = max(
            1,
            ceil(int(main_info.get('totalResults', 0)) / page_size),
        )

        if page < total_pages:
            next_page_url = f"https://www.daraz.pk/smartphones/?ajax=true&page={page + 1}"
            yield scrapy.Request(url=next_page_url, callback=self.parse)

    def _build_review_request(self, external_id, review_count, page_number=1):
        """Return a bounded review request for one catalog item."""

        if (
            not external_id
            or not review_count
            or self._max_reviews_per_listing() <= 0
        ):
            return None

        if page_number == 1:
            if self.review_listings_requested >= self._max_review_listings():
                return None
            self.review_listings_requested += 1

        return scrapy.Request(
            url=(
                f'{self.REVIEW_API_URL}?itemId={external_id}'
                f'&pageSize={self.REVIEW_PAGE_SIZE}'
                f'&filter=0&sort=0&pageNo={page_number}'
            ),
            callback=self.parse_reviews,
            errback=self.review_fetch_error,
            cb_kwargs={
                'external_listing_id': external_id,
                'page_number': page_number,
            },
            meta={
                'external_listing_id': external_id,
                'dont_merge_cookies': True,
            },
            headers={'Accept': 'application/json'},
            dont_filter=True,
        )

    @staticmethod
    def _parse_review_date(value):
        """Return an ISO timestamp for a Daraz ``"20 Sep 2026"`` date.

        Daraz only publishes a relative review time ("2 weeks ago"), so the
        purchase date it shows beside the review is used instead. It is the
        marketplace's own dated statement about that review.
        """

        normalized = ' '.join(str(value or '').split()).replace(
            ' Sept ',
            ' Sep ',
        )

        if not normalized:
            return None

        for date_format in ('%d %b %Y', '%d %B %Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(
                    normalized,
                    date_format,
                ).replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                continue

        return None

    def parse_reviews(self, response, external_listing_id, page_number=1):
        """Convert one page of the Daraz review API into a review batch."""

        try:
            payload = json.loads(response.text)
        except json.JSONDecodeError as exc:
            raise DarazReviewParserError(
                'Daraz returned malformed review JSON.'
            ) from exc

        if not isinstance(payload, dict) or not isinstance(
            payload.get('model'),
            dict,
        ):
            raise DarazReviewParserError(
                'Daraz review payload did not match its contract.'
            )

        model = payload['model']
        raw_reviews = model.get('items')

        if not isinstance(raw_reviews, list) or not raw_reviews:
            return

        limit = self._max_reviews_per_listing()
        reviews = []

        for position, raw_review in enumerate(raw_reviews[:limit], start=1):
            if not isinstance(raw_review, dict):
                continue

            rating = raw_review.get('rating')
            if not isinstance(rating, int) or not 1 <= rating <= 5:
                continue

            review_id = optional_text(
                raw_review.get('reviewRateId'),
                max_length=150,
            )
            image_urls = [
                image.get('url')
                for image in (raw_review.get('images') or [])[:10]
                if isinstance(image, dict) and image.get('url')
            ]

            reviews.append({
                'external_review_id': review_id,
                'reviewer_external_id': optional_text(
                    raw_review.get('buyerId'),
                    max_length=150,
                ),
                'reviewer_display_name': optional_text(
                    raw_review.get('buyerName'),
                    max_length=255,
                ),
                'rating': rating,
                'review_text': optional_text(
                    raw_review.get('reviewContent'),
                    max_length=10000,
                ),
                'reviewed_at': self._parse_review_date(
                    raw_review.get('boughtDate')
                ),
                'verified_purchase': bool(raw_review.get('isPurchased')),
                'helpful_count': (
                    raw_review['upVotes']
                    if isinstance(raw_review.get('upVotes'), int)
                    and raw_review['upVotes'] >= 0
                    else None
                ),
                'raw_metadata': {
                    'source_position': position,
                    'source_page': page_number,
                    'image_urls': image_urls,
                },
            })

        if not reviews:
            return

        batch = ReviewBatchItem()
        batch['platform'] = 'Daraz'
        batch['external_listing_id'] = external_listing_id
        batch['source_url'] = response.url
        batch['reviews'] = reviews
        yield batch

        paging = model.get('paging')
        total_pages = (
            paging.get('totalPages')
            if isinstance(paging, dict)
            else None
        )
        collected = page_number * self.REVIEW_PAGE_SIZE

        if (
            isinstance(total_pages, int)
            and page_number < total_pages
            and collected < limit
        ):
            next_request = self._build_review_request(
                external_listing_id,
                review_count=1,
                page_number=page_number + 1,
            )
            if next_request is not None:
                yield next_request

    def review_fetch_error(self, failure):
        request = getattr(failure, 'request', None)
        external_listing_id = (
            request.meta.get('external_listing_id')
            if request is not None
            else None
        )
        error = DarazReviewFetchError(
            'Daraz review API request failed.'
        )
        error.metadata = {
            'external_listing_id': external_listing_id,
        }
        cause = getattr(failure, 'value', None)
        if cause is None:
            raise error
        raise error from cause
