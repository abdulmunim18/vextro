import json
import scrapy
import re
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from vextro_scraper.items import ReviewBatchItem, SmartphoneItem
from vextro_scraper.normalizers import (
    extract_json_ld_products,
    json_ld_availability,
    json_ld_offer,
    optional_text,
    parse_count,
    parse_price,
    parse_rating,
)


# Specification labels that state RAM or storage, in the backend's spelling.
RAM_SPEC_KEYS = frozenset({'ram', 'ram_capacity', 'memory_ram', 'memory'})
STORAGE_SPEC_KEYS = frozenset({
    'storage_capacity',
    'storage',
    'rom',
    'internal_memory',
    'internal_storage',
    'built_in_storage',
    'built_in_memory',
})


class PriceOyeReviewParserError(ValueError):
    """PriceOye advertised reviews but returned unusable review markup."""

    error_type = "review_parse_error"
    error_stage = "parse"


class PriceOyeReviewFetchError(RuntimeError):
    """The PriceOye review page could not be fetched."""

    error_type = "review_fetch_error"
    error_stage = "fetch"

class PriceoyeSpider(scrapy.Spider):
    name = "priceoye_smartphones"
    platform_code = "priceoye"
    parser_version = "priceoye-v4-variant-offers"
    allowed_domains = ["priceoye.pk"]
    start_urls = ["https://priceoye.pk/mobiles"]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    @staticmethod
    def extract_specifications(response):
        """Extract label/value specs across PriceOye's current layouts."""

        specifications = {}
        containers = response.css(
            '#specifications, .specifications, .specification, '
            '.product-specifications, .product-specs, .specs'
        )

        for container in containers:
            for row in container.css('tr'):
                cells = [
                    ' '.join(cell.css('::text').getall()).strip()
                    for cell in row.css('th, td')
                ]
                cells = [cell for cell in cells if cell]
                if len(cells) >= 2:
                    specifications[cells[0]] = ' '.join(cells[1:])

            terms = container.css('dt')
            for term in terms:
                label = ' '.join(term.css('::text').getall()).strip()
                value = ' '.join(
                    term.xpath('following-sibling::dd[1]//text()').getall()
                ).strip()
                if label and value:
                    specifications[label] = value

            for row in container.css('li, .spec-row, .spec-item'):
                label = ' '.join(
                    row.css(
                        '.label::text, .title::text, '
                        '.spec-name::text, strong:first-child::text'
                    ).getall()
                ).strip(' :')
                value = ' '.join(
                    row.css(
                        '.value::text, .detail::text, '
                        '.spec-value::text, span:last-child::text'
                    ).getall()
                ).strip()
                if label and value and label != value:
                    specifications[label] = value

        return specifications

    @staticmethod
    def extract_offer(response):
        """Return PriceOye's own structured offer for this product.

        The product page embeds a schema.org ``Product`` block holding the
        current price, availability and aggregate rating. That is the
        marketplace stating those facts in machine-readable form, so it is
        preferred over presentation markup, which changes without notice.
        """

        for product in extract_json_ld_products(response.text):
            if json_ld_offer(product) is not None:
                return product

        return None

    @staticmethod
    def extract_availability(response, product=None):
        """Read PriceOye's structured availability before text fallbacks."""

        structured = json_ld_availability(product)
        if structured is not None:
            return structured

        page_source = response.text
        structured_availability = re.findall(
            r'"product_availability"\s*:\s*"([^"]+)"',
            page_source,
            re.I,
        )
        structured_availability.extend(
            re.findall(
                r'"(?:schema_status|availability)"\s*:\s*"'
                r'(?:https?\\?/\\?/schema\.org\\?/)?([^"]+)"',
                page_source,
                re.I,
            )
        )

        if structured_availability:
            return any(
                value.replace('\\/', '/').lower().endswith('instock')
                or value.strip().lower() == 'in stock'
                for value in structured_availability
            )

        purchase_control = response.xpath(
            '//*[self::button or self::a][contains('
            'translate(normalize-space(.), '
            '"ABCDEFGHIJKLMNOPQRSTUVWXYZ", '
            '"abcdefghijklmnopqrstuvwxyz"), "add to cart") or contains('
            'translate(normalize-space(.), '
            '"ABCDEFGHIJKLMNOPQRSTUVWXYZ", '
            '"abcdefghijklmnopqrstuvwxyz"), "buy now") or contains('
            'translate(normalize-space(.), '
            '"ABCDEFGHIJKLMNOPQRSTUVWXYZ", '
            '"abcdefghijklmnopqrstuvwxyz"), "checkout")]'
        )
        page_text = ' '.join(
            text.strip().lower()
            for text in response.css('body ::text').getall()
            if text.strip()
        )
        explicitly_unavailable = any(
            marker in page_text
            for marker in (
                'currently unavailable',
                'discontinued',
            )
        )
        return bool(purchase_control) and not explicitly_unavailable

    def parse(self, response, page_number=1):
        phones = response.css('div.productBox')

        for phone in phones:
            item = SmartphoneItem()
            item['platform'] = 'PriceOye'
            item['product_url'] = phone.css('a::attr(href)').get()

            details = [
                text.strip()
                for text in phone.css('div.detail-box ::text').getall()
                if text.strip()
            ]
            if details:
                item['model'] = details[0]
                item['price'] = next(
                    (text for text in details if 'Rs' in text),
                    None,
                )

            item['scrape_timestamp'] = datetime.now(timezone.utc).isoformat()

            # DEEP SCRAPING: visit the product page so the offer, gallery and
            # specification sheet come from the marketplace's own record.
            if item['product_url']:
                yield response.follow(
                    item['product_url'],
                    callback=self.parse_product,
                    meta={'item': item},
                )

        next_page_request = self.next_page_request(
            response,
            page_number=page_number,
            page_item_count=len(phones),
        )
        if next_page_request is not None:
            yield next_page_request

    def next_page_request(self, response, *, page_number, page_item_count):
        """Return the request for the next catalog page, if there is one.

        PriceOye renders its "next" control as ``<a rel="next">`` with no
        href, so following that link silently ended every crawl after the
        first 36 phones - the catalog holds several hundred. The listing
        does answer ``?page=N``, so pages are walked explicitly until one
        comes back empty.
        """

        if not page_item_count:
            return None

        if page_number >= self.max_catalog_pages():
            self.logger.info(
                'Stopping PriceOye pagination at the configured page '
                'limit (%s).',
                self.max_catalog_pages(),
            )
            return None

        marked_next = response.css('a[rel="next"]::attr(href)').get()

        if marked_next:
            return response.follow(
                marked_next,
                callback=self.parse,
                cb_kwargs={'page_number': page_number + 1},
            )

        return response.follow(
            self.catalog_page_url(response.url, page_number + 1),
            callback=self.parse,
            cb_kwargs={'page_number': page_number + 1},
        )

    @staticmethod
    def catalog_page_url(current_url, page_number):
        """Return one catalog URL with its ``page`` query parameter set."""

        parsed = urlparse(current_url)
        query = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key != 'page'
        ]
        query.append(('page', str(page_number)))

        return urlunparse(parsed._replace(query=urlencode(query)))

    def max_catalog_pages(self):
        """Return how many catalog pages one run may walk."""

        crawler = getattr(self, 'crawler', None)

        if crawler is None:
            return 40

        return max(
            1,
            crawler.settings.getint('PRICEOYE_MAX_CATALOG_PAGES', 40),
        )


    @staticmethod
    def extract_prices(response, product=None):
        """Return ``(current_price, original_price)`` for a product page.

        The structured offer carries the current price. The struck-through
        retail price only exists in markup, so it is read from the pricing
        box and discarded unless it is genuinely above the selling price.
        """

        offer = json_ld_offer(product)
        current_price = (
            parse_price(offer.get('price')) if offer is not None else None
        )

        pricing_text = "".join(
            part.strip()
            for part in response.css('div.product-price ::text').getall()
            if part.strip()
        )

        if current_price is None:
            current_price = parse_price(
                next(
                    iter(
                        re.findall(r'Rs\s?[\d,]+', pricing_text)
                    ),
                    None,
                )
            )

        original_price = parse_price(
            response.css(
                '.retail-price .summary-price::text, '
                '.retail-price ::text, '
                '.market-price ::text, '
                '.summary-price.line-through::text'
            ).re_first(r'[\d,]{3,}')
        )

        if (
            original_price is not None
            and current_price is not None
            and original_price <= current_price
        ):
            original_price = None

        return current_price, original_price

    @staticmethod
    def extract_rating(product):
        """Return ``(rating, review_count)`` from the structured aggregate."""

        aggregate = (product or {}).get('aggregateRating')

        if not isinstance(aggregate, dict):
            return None, 0

        return (
            parse_rating(aggregate.get('ratingValue')),
            parse_count(aggregate.get('ratingCount')) or 0,
        )

    @staticmethod
    def extract_image_urls(response, product=None):
        """Return the product gallery, trying every published source.

        A listing that reaches the catalog without an image shows as a blank
        card, so the gallery markup, the lazy-loading attributes behind it,
        the structured product block and OpenGraph are all consulted before
        giving up.
        """

        image_urls = []

        structured_images = (product or {}).get('image')
        if isinstance(structured_images, (str, dict)):
            structured_images = [structured_images]
        elif not isinstance(structured_images, (list, tuple)):
            structured_images = []

        candidates = [
            image.get('url') if isinstance(image, dict) else image
            for image in structured_images
        ]

        candidates.extend(
            response.css(
                'img.main-product-img::attr(src), '
                'img.main-product-img::attr(data-src), '
                '.product-image img::attr(src), '
                '.product-image img::attr(data-src), '
                '.product-gallery img::attr(src), '
                '.product-gallery img::attr(data-src), '
                'img.product-img::attr(src)'
            ).getall()
        )

        def collect(urls):
            for candidate in urls:
                image_url = optional_text(candidate, max_length=1000)

                if image_url is None:
                    continue

                absolute_url = response.urljoin(image_url)

                if absolute_url not in image_urls:
                    image_urls.append(absolute_url)

        collect(candidates)

        # The social preview is a single low-resolution copy of the first
        # gallery image, so it is only worth having when nothing else loaded.
        if not image_urls:
            collect(
                response.css(
                    'meta[property="og:image"]::attr(content), '
                    'meta[name="twitter:image"]::attr(content)'
                ).getall()
            )

        return image_urls

    def parse_product(self, response):
        item = response.meta['item']
        item['product_url'] = response.url
        item['external_id'] = (
            item.get('external_id')
            or response.url.rstrip('/').split('/')[-1]
        )

        product = self.extract_offer(response)

        item['brand'] = (
            optional_text((product or {}).get('brand'), max_length=120)
            or response.css(
                '[itemprop="brand"]::attr(content), '
                '[itemprop="brand"] ::text, '
                '.product-brand ::text, '
                '.brand-name ::text'
            ).get()
            or response.css(
                'meta[property="product:brand"]::attr(content)'
            ).get()
        )
        item['sku'] = optional_text(
            (product or {}).get('productID')
            or (product or {}).get('sku'),
            max_length=120,
        )

        # 1. Price: the structured offer first, pricing markup as a fallback.
        current_price, original_price = self.extract_prices(
            response,
            product,
        )
        if current_price is not None:
            item['price'] = current_price
        item['original_price'] = original_price

        # 2. Review aggregate published alongside the offer.
        rating, review_count = self.extract_rating(product)
        item['rating'] = rating
        item['review_count'] = review_count

        # 3. Extract Color
        item['color'] = optional_text(
            response.css('ul.colors li.active .color-name::text').get()
            or response.css('ul.colors li.active ::text').get(),
            max_length=80,
        )

        # 4. Extract Variant (RAM/Storage):
        # First check title regex, then check page active buttons
        title_variant = re.search(r'\(\d+GB.*?\)', item.get('model', ''))
        variant_btn = response.css('div.po-variant-card ul.variants li.active ::text').get()

        if title_variant:
            item['variant'] = title_variant.group(0)
        else:
            item['variant'] = optional_text(variant_btn, max_length=120)

        # 5. Availability
        item['availability'] = (
            'In Stock'
            if self.extract_availability(response, product)
            else 'Out of Stock'
        )

        # 6. Warranty: only record what the page actually states.
        item['warranty'] = optional_text(
            response.xpath(
                '//table//td[contains(text(), "Warranty")]'
                '/following-sibling::td/text()'
            ).get(),
            max_length=255,
        )

        item['image_urls'] = self.extract_image_urls(response, product)
        item['specifications'] = self.extract_specifications(response)

        # 7. One listing per colour and storage option. The fields above
        # describe only the option PriceOye pre-selects; the page's own
        # offer matrix states the price and stock of every other one.
        product_data = self.extract_product_data(response)
        variant_items = self.variant_offer_items(item, product_data)

        if variant_items:
            yield from variant_items
            external_listing_id = variant_items[0].get('external_id')
        else:
            if self.is_reference_only(product_data):
                # PriceOye keeps a page and a "last updated price" for
                # phones it no longer sells; nothing there can be bought.
                item['availability'] = 'Out of Stock'

            yield item
            external_listing_id = item.get('external_id')

        if external_listing_id and self._max_reviews_per_listing() > 0:
            yield scrapy.Request(
                url=f"{response.url.rstrip('/')}/reviews",
                callback=self.parse_reviews,
                errback=self.review_fetch_error,
                cb_kwargs={
                    'external_listing_id': external_listing_id,
                },
                meta={
                    'external_listing_id': external_listing_id,
                },
            )

    @staticmethod
    def extract_product_data(response):
        """Return the ``window.product_data`` object embedded in the page."""

        source = response.text
        marker = source.find('window.product_data')
        start = source.find('{', marker) if marker != -1 else -1

        if start == -1:
            return None

        try:
            data, _ = json.JSONDecoder().raw_decode(source[start:])
        except ValueError:
            return None

        return data if isinstance(data, dict) else None

    @staticmethod
    def offer_matrix(product_data):
        """Return ``[(colour_slug, size_label, offer), ...]`` for a page.

        PriceOye publishes ``dataPrices[colour][size] = [offer]``. Phones
        sold in a single configuration use a list per colour instead of a
        size-keyed map, with the labels held separately in ``aColorSize``.
        """

        config = (product_data or {}).get('product_config')
        if not isinstance(config, dict):
            return []

        prices = config.get('dataPrices')
        if not isinstance(prices, dict):
            return []

        size_labels = config.get('aColorSize')
        if not isinstance(size_labels, dict):
            size_labels = {}

        matrix = []
        for color_slug, sizes in prices.items():
            if isinstance(sizes, list):
                labels = size_labels.get(color_slug)
                if not isinstance(labels, list):
                    labels = []
                sizes = {
                    str(labels[index] if index < len(labels) else '').strip()
                    or (str(index) if len(sizes) > 1 else ''): offers
                    for index, offers in enumerate(sizes)
                }

            if not isinstance(sizes, dict):
                continue

            for size_label, offers in sizes.items():
                if isinstance(offers, dict):
                    offers = [offers]
                if not isinstance(offers, list):
                    continue
                offer = next(
                    (entry for entry in offers if isinstance(entry, dict)),
                    None,
                )
                if offer is not None:
                    matrix.append((str(color_slug), str(size_label), offer))

        return matrix

    @classmethod
    def is_reference_only(cls, product_data):
        """True when the page carries product data but no offer at all."""

        return product_data is not None and not cls.offer_matrix(product_data)

    @staticmethod
    def parse_size_label(size_label):
        """Return ``(ram_gb, storage_gb)`` from '256gb - 12gb ram'."""

        label = str(size_label or '').lower()
        ram_match = re.search(r'(\d{1,3})\s*gb\s*ram', label)
        ram_gb = int(ram_match.group(1)) if ram_match else None

        storage_gb = None
        for value, unit, trailer in re.findall(
            r'(\d{1,4})\s*(gb|tb)(\s*ram)?', label,
        ):
            if trailer.strip():
                continue
            storage_gb = int(value) * (1024 if unit == 'tb' else 1)
            break

        return ram_gb, storage_gb

    def variant_offer_items(self, base_item, product_data):
        """Return one item per colour and storage option on the page."""

        matrix = self.offer_matrix(product_data)
        if not matrix:
            return []

        color_images = product_data.get('product_color_images')
        if not isinstance(color_images, dict):
            color_images = {}

        base_id = base_item.get('external_id')
        base_images = list(base_item.get('image_urls') or [])
        base_specifications = dict(base_item.get('specifications') or {})
        items = []

        for color_slug, size_label, offer in sorted(
            matrix,
            key=lambda entry: (entry[0], entry[1]),
        ):
            price = parse_price(offer.get('product_price'))
            if price is None:
                continue

            item = base_item.deepcopy()
            size_slug = re.sub(r'[^a-z0-9]+', '-', size_label.lower())
            item['external_id'] = '--'.join(
                part
                for part in (base_id, color_slug, size_slug.strip('-'))
                if part
            )
            # The marketplace SKU names the phone, not one configuration;
            # sending it would file every option under the first variant.
            item['sku'] = None
            item['color'] = optional_text(
                color_slug.replace('_', ' ').replace('-', ' ').title(),
                max_length=80,
            )
            item['variant'] = optional_text(size_label, max_length=120)
            item['price'] = price

            retail_price = parse_price(offer.get('retail_price'))
            item['original_price'] = (
                retail_price
                if retail_price is not None and retail_price > price
                else None
            )

            availability = str(
                offer.get('product_availability') or ''
            ).strip().lower()
            item['availability'] = (
                'In Stock' if availability == 'in stock' else 'Out of Stock'
            )

            images = color_images.get(color_slug)
            if isinstance(images, dict):
                images = images.get('large') or images.get('medium')
            if isinstance(images, str):
                images = [images]
            if not isinstance(images, list):
                images = []
            item['image_urls'] = list(dict.fromkeys(
                [image for image in images if isinstance(image, str)]
                + base_images
            ))

            # The option's own RAM and storage must win over the page's
            # specification sheet, which lists every size at once.
            ram_gb, storage_gb = self.parse_size_label(size_label)
            specifications = {}
            if ram_gb is not None:
                specifications['ram'] = f'{ram_gb}GB'
            if storage_gb is not None:
                specifications['storage_capacity'] = f'{storage_gb}GB'
            for label, value in base_specifications.items():
                key = re.sub(r'[^a-z0-9]+', '_', str(label).lower()).strip('_')
                if ram_gb is not None and key in RAM_SPEC_KEYS:
                    continue
                if storage_gb is not None and key in STORAGE_SPEC_KEYS:
                    continue
                specifications[label] = value
            item['specifications'] = specifications

            items.append(item)

        return items

    def _max_reviews_per_listing(self):
        crawler = getattr(self, 'crawler', None)
        if crawler is None:
            return 50
        return max(
            0,
            min(
                crawler.settings.getint(
                    'MAX_REVIEWS_PER_LISTING',
                    50,
                ),
                100,
            ),
        )

    @staticmethod
    def _parse_review_date(value):
        normalized = ' '.join(str(value or '').split()).replace(
            ' Sept ',
            ' Sep ',
        )
        for date_format in ('%d %b %Y', '%d %B %Y'):
            try:
                return datetime.strptime(
                    normalized,
                    date_format,
                ).replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                continue
        raise PriceOyeReviewParserError(
            f'Unsupported PriceOye review date: {normalized[:80]!r}'
        )

    def parse_reviews(self, response, external_listing_id):
        review_boxes = response.css('.review-box')
        aggregate_text = ' '.join(
            response.css('.product-rating ::text').getall()
        )
        if not review_boxes:
            advertised_count = re.search(
                r'\b([1-9]\d*)\s+Reviews?\b',
                aggregate_text,
                re.I,
            )
            if advertised_count:
                raise PriceOyeReviewParserError(
                    'PriceOye advertised reviews without review records.'
                )
            return

        reviews = []
        limit = self._max_reviews_per_listing()
        for position, box in enumerate(review_boxes[:limit], start=1):
            reviewer_name = ' '.join(
                box.css('.user-reivew-name ::text').getall()
            ).strip() or None
            rating = len(box.css('.rating-star img.average-stars'))
            review_text = ' '.join(
                part.strip()
                for part in box.css(
                    '.user-reivew-description ::text'
                ).getall()
                if part.strip()
            ) or None
            date_text = ' '.join(
                box.css('.review-date ::text').getall()
            ).strip()
            if rating < 1 or rating > 5 or not date_text:
                raise PriceOyeReviewParserError(
                    'PriceOye review is missing a valid rating or date.'
                )

            review_image_urls = [
                response.urljoin(image_url)
                for image_url in box.css(
                    '.review-images img::attr(src)'
                ).getall()[:10]
                if image_url
            ]

            reviews.append({
                'external_review_id': None,
                'reviewer_external_id': None,
                'reviewer_display_name': reviewer_name,
                'rating': rating,
                'review_text': review_text,
                'reviewed_at': self._parse_review_date(date_text),
                'verified_purchase': bool(
                    box.css('.verified-user')
                ),
                'helpful_count': None,
                'raw_metadata': {
                    'source_position': position,
                    'image_urls': review_image_urls,
                },
            })

        batch = ReviewBatchItem()
        batch['platform'] = 'PriceOye'
        batch['external_listing_id'] = external_listing_id
        batch['source_url'] = response.url
        batch['reviews'] = reviews
        yield batch

    def review_fetch_error(self, failure):
        request = getattr(failure, 'request', None)
        external_listing_id = (
            request.meta.get('external_listing_id')
            if request is not None
            else None
        )
        error = PriceOyeReviewFetchError(
            'PriceOye review page request failed.'
        )
        error.metadata = {
            'external_listing_id': external_listing_id,
        }
        cause = getattr(failure, 'value', None)
        if cause is None:
            raise error
        raise error from cause
