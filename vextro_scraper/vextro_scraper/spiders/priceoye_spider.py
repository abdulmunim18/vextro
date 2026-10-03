import scrapy
import re
from datetime import datetime, timezone
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
    parser_version = "priceoye-v3-structured-offers"
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

    def parse(self, response):
        phones = response.css('div.productBox')
        
        for phone in phones:
            item = SmartphoneItem()
            item['platform'] = 'PriceOye'
            item['product_url'] = phone.css('a::attr(href)').get()
            
            details = [t.strip() for t in phone.css('div.detail-box ::text').getall() if t.strip()]
            if details:
                item['model'] = details[0]
                item['price'] = next(
                    (t for t in details if 'Rs' in t),
                    None,
                )
            
            item['scrape_timestamp'] = datetime.now(timezone.utc).isoformat()
            
            # DEEP SCRAPING: Instead of saving the item immediately, 
            # we tell Scrapy to visit the product URL and pass the item to a new function!
            if item['product_url']:
                yield response.follow(item['product_url'], callback=self.parse_product, meta={'item': item})

        # PAGINATION: Find the "Next" page button and loop the spider
        next_page = response.css('a[rel="next"]::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)


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

        # PriceOye's current product gallery uses full-size main-product-img
        # elements. OpenGraph is retained as a fallback for markup changes.
        image_urls = response.css('img.main-product-img::attr(src)').getall()
        if not image_urls:
            image_urls = response.css(
                'meta[property="og:image"]::attr(content)'
            ).getall()
        item['image_urls'] = [
            response.urljoin(image_url)
            for image_url in image_urls
            if image_url
        ]
        item['specifications'] = self.extract_specifications(response)
        
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
