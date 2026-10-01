import scrapy
import re
from datetime import datetime, timezone
from vextro_scraper.items import ReviewBatchItem, SmartphoneItem


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
    parser_version = "priceoye-v3-color-variants"
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
    def extract_color_variants(response):
        """Return every colour variant PriceOye lists for the product.

        The product page's ``ul.colors`` always carries every colour the
        marketplace tracks for a product, whether it is in stock or not.
        Sold-out colours are flagged by the presence of a
        ``<span class="sold-out-tag"></span>`` element inside the
        ``<li>`` (the span is visually styled by CSS but has no inner
        text, so we check for the element itself, never its text).

        Each entry carries:
            color: Human-readable colour name (e.g. ``"Mist Blue"``)
            slug: Machine key from ``data-vars-value`` (e.g. ``"mist_blue"``)
            is_available: ``True`` when the sold-out marker is absent
            active: ``True`` for the colour currently shown in the
                    gallery and price panel; used to attach reviews
                    to a single listing per product.
            thumbnail_url: Small 100x100 colour thumbnail; usable as a
                           500x500 by swapping the dimension suffix.
        """

        variants = []
        for color_li in response.css("ul.colors li"):
            name = (color_li.css(".color-name::text").get() or "").strip()
            if not name:
                continue

            slug = (
                color_li.css("a::attr(data-vars-value)").get() or ""
            ).strip().lower()
            if not slug:
                slug = re.sub(
                    r"[^a-z0-9]+", "-", name.lower()
                ).strip("-")

            is_sold_out = bool(color_li.css(".sold-out-tag"))
            classes = color_li.attrib.get("class") or ""
            active = "active" in classes.split()

            thumbnail = (
                color_li.css(
                    ".product-detail-image::attr(src)"
                ).get()
                or color_li.css("img::attr(src)").get()
            )

            variants.append(
                {
                    "color": name,
                    "slug": slug,
                    "is_available": not is_sold_out,
                    "active": active,
                    "thumbnail_url": thumbnail,
                }
            )
        return variants

    @staticmethod
    def extract_prices(response):
        """Return (current_price, original_price) as PriceOye strings.

        Current price is the headline ``summary-price.price-size-lg``;
        original price is the strike-through variant inside
        ``.retail-price``. Either can be ``None`` when PriceOye does
        not surface a discount for the active variant. The cleaning
        pipeline accepts either format and normalises them downstream.
        """

        def _first_price(selector_list):
            text = " ".join(
                part.strip()
                for part in selector_list.css("::text").getall()
                if part.strip()
            )
            match = re.search(r"Rs\s?[\d,]+", text)
            return match.group(0) if match else None

        current = _first_price(
            response.css(".product-price .summary-price.price-size-lg")
        ) or _first_price(response.css(".product-price"))

        original = _first_price(
            response.css(".retail-price .summary-price")
        )

        return current, original

    @staticmethod
    def _promote_to_main_image(thumbnail_url):
        """Rewrite a PriceOye colour-swatch thumbnail into its 500x500 twin.

        Non-active colours only have 100x100 thumbnails inline. The
        main gallery URL for the same colour follows the convention
        ``<prefix>-500x500.webp``, so we can promote the thumbnail
        instead of refetching the page per colour.
        """

        if not thumbnail_url:
            return None
        promoted = re.sub(
            r"-100x100(\.(?:webp|jpg|jpeg|png))$",
            r"-500x500\1",
            thumbnail_url,
        )
        return promoted

    @staticmethod
    def extract_availability(response):
        """Read PriceOye's embedded variant data before text fallbacks."""

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


    def parse_product(self, response):
        """Emit one listing item per colour PriceOye lists for this product.

        The old implementation emitted a single item for whichever
        colour PriceOye chose to show by default, which meant we never
        learned about the other colours' availability. When the default
        colour later went out of stock, our catalog kept claiming the
        product was in stock. Walking ``ul.colors`` once gives us the
        full picture — including which colours are sold out — from a
        single detail-page fetch.
        """

        base_item = response.meta["item"]
        base_external_id = (
            base_item.get("external_id")
            or response.url.rstrip("/").split("/")[-1]
        )

        # --- Common fields (shared across every colour variant) ---
        brand = (
            response.css(
                '[itemprop="brand"]::attr(content), '
                '[itemprop="brand"] ::text, '
                '.product-brand ::text, '
                '.brand-name ::text'
            ).get()
            or response.css(
                'meta[property="product:brand"]::attr(content)'
            ).get()
        )

        current_price, original_price = self.extract_prices(response)

        model_text = base_item.get("model", "")
        title_variant_match = re.search(
            r"\(\d+GB.*?\)", model_text
        )
        variant_button = response.css(
            "div.po-variant-card ul.variants li.active ::text"
        ).get()
        if title_variant_match:
            variant_label = title_variant_match.group(0)
        elif variant_button:
            variant_label = variant_button.strip()
        else:
            variant_label = "Standard"

        warranty_text = response.xpath(
            '//table//td[contains(text(), "Warranty")]'
            '/following-sibling::td/text()'
        ).get()
        warranty = (
            warranty_text.strip()
            if warranty_text
            else "Official Brand Warranty"
        )

        main_image_urls = response.css(
            "img.main-product-img::attr(src)"
        ).getall()
        if not main_image_urls:
            main_image_urls = response.css(
                'meta[property="og:image"]::attr(content)'
            ).getall()
        main_image_urls = [
            response.urljoin(image_url)
            for image_url in main_image_urls
            if image_url
        ]

        specifications = self.extract_specifications(response)

        # --- Per-colour fan-out ---
        color_variants = self.extract_color_variants(response)

        if not color_variants:
            # PriceOye either removed the colour selector or served a
            # single-colour SKU. Fall back to the pre-split behaviour
            # so these products keep landing instead of being dropped.
            color_variants = [
                {
                    "color": "N/A",
                    "slug": None,
                    "is_available": self.extract_availability(response),
                    "active": True,
                    "thumbnail_url": None,
                }
            ]

        # Reviews are product-level on PriceOye; attach them to the
        # alphabetically-first colour so the review-to-listing mapping
        # stays stable across runs even when PriceOye changes which
        # colour is active or in stock.
        review_target_slug = min(
            (variant.get("slug") or variant["color"].lower() for variant in color_variants),
            default=None,
        )
        review_target_id = None
        scraped_at = datetime.now(timezone.utc).isoformat()

        for color_variant in color_variants:
            item = SmartphoneItem()
            item["platform"] = base_item.get("platform", "PriceOye")
            item["product_url"] = response.url
            item["model"] = model_text
            item["brand"] = brand
            item["variant"] = variant_label
            item["warranty"] = warranty
            item["price"] = current_price
            if original_price:
                item["original_price"] = original_price
            item["specifications"] = specifications
            item["scrape_timestamp"] = scraped_at

            color_name = color_variant["color"]
            color_slug = color_variant.get("slug")
            item["color"] = color_name
            item["availability"] = (
                "In Stock"
                if color_variant["is_available"]
                else "Out of Stock"
            )

            # Unique external_id per colour so each listing updates
            # independently in the catalog. For the single-colour
            # fallback above the suffix is skipped so legacy listings
            # keep their external_id steady across runs.
            if color_slug:
                item["external_id"] = (
                    f"{base_external_id}--{color_slug}"
                )
            else:
                item["external_id"] = base_external_id

            # Images: active colour reuses the full gallery; inactive
            # colours promote their 100x100 swatch to 500x500 so each
            # listing has at least one representative image.
            if color_variant["active"] and main_image_urls:
                item["image_urls"] = main_image_urls
            else:
                promoted = self._promote_to_main_image(
                    color_variant.get("thumbnail_url")
                )
                item["image_urls"] = (
                    [response.urljoin(promoted)] if promoted else []
                )

            if color_slug == review_target_slug:
                review_target_id = item["external_id"]
            elif review_target_id is None and review_target_slug is None:
                # Single-colour fallback path has slug=None for both
                # sides, so take the first (and only) item.
                review_target_id = item["external_id"]

            yield item

        if review_target_id and self._max_reviews_per_listing() > 0:
            yield scrapy.Request(
                url=f"{response.url.rstrip('/')}/reviews",
                callback=self.parse_reviews,
                errback=self.review_fetch_error,
                cb_kwargs={
                    "external_listing_id": review_target_id,
                },
                meta={
                    "external_listing_id": review_target_id,
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
