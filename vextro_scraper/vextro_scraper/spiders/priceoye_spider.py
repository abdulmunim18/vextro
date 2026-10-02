import json
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


class PriceOyePageFetchError(RuntimeError):
    """A PriceOye listing or product page could not be fetched."""

    error_type = "page_fetch_error"
    error_stage = "fetch"

class PriceoyeSpider(scrapy.Spider):
    name = "priceoye_smartphones"
    platform_code = "priceoye"
    parser_version = "priceoye-v4-variant-matrix"
    allowed_domains = ["priceoye.pk"]

    # The catalogue listing is a live "recommended" ranking that
    # reshuffles between requests: walking it returned 385 entries but
    # only 304 distinct phones, silently skipping 81. A sorted listing
    # would be stable, but robots.txt only permits the ``?page=`` query,
    # so sorting is not an option. Each brand's own page lists that
    # brand's current phones on its first page, so the walk covers the
    # general listing AND every brand page, then checks the number of
    # distinct phones against the catalogue's stated size.
    listing_url = "https://priceoye.pk/mobiles"
    start_urls = [listing_url]
    listing_page_size = 36

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._reached_catalogue_end = False
        self._failed_pages = 0
        self._product_urls = set()
        self._stated_total = None

    @property
    def full_crawl_completed(self):
        """True when every catalogue and product page was read.

        The backend treats this as proof that a listing it did not
        receive is no longer on sale, so anything that leaves a doubt
        withholds it: a page that failed to download, or fewer distinct
        phones queued than the catalogue says it holds. Better to keep
        a stale offer for one more cycle than to mark a healthy one
        unavailable.
        """

        if not self._reached_catalogue_end or self._failed_pages:
            return False
        if self._stated_total is None:
            return True
        return len(self._product_urls) >= self._stated_total

    def page_fetch_error(self, failure):
        self._failed_pages += 1
        request = getattr(failure, 'request', None)
        error = PriceOyePageFetchError(
            'PriceOye page request failed: '
            f"{getattr(request, 'url', 'unknown url')}"
        )
        cause = getattr(failure, 'value', None)
        if cause is None:
            raise error
        raise error from cause

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

    def _max_listing_pages(self):
        crawler = getattr(self, 'crawler', None)
        if crawler is None:
            return 60
        return max(1, crawler.settings.getint('PRICEOYE_MAX_PAGES', 60))

    def _crawl_brand_pages(self):
        """Brand pages complete the catalogue; a capped trial run skips them."""

        crawler = getattr(self, 'crawler', None)
        if crawler is None:
            return True
        return crawler.settings.getbool('PRICEOYE_BRAND_PAGES', True)

    def _product_requests(self, response):
        """Queue every product linked from a listing or brand page."""

        for phone in response.css('div.productBox'):
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

            if not item['product_url']:
                continue

            product_url = response.urljoin(item['product_url'])
            if product_url in self._product_urls:
                # The same phone shows up on both the general listing
                # and its brand page; one visit is enough.
                continue
            self._product_urls.add(product_url)

            # DEEP SCRAPING: visit the product page, which carries the
            # full colour/storage matrix for this phone.
            yield response.follow(
                product_url,
                callback=self.parse_product,
                errback=self.page_fetch_error,
                meta={'item': item},
            )

    def parse(self, response):
        """Walk the general catalogue listing, page by page."""

        page = int(response.meta.get('listing_page', 1))
        phones = response.css('div.productBox')

        if page == 1:
            listing_data = self.extract_product_data(response) or {}

            # The catalogue's own size, used to confirm the walk really
            # covered every phone.
            stated_total = listing_data.get('totalCategoryProducts')
            if not isinstance(stated_total, int):
                stated = re.search(
                    r'(\d[\d,]*)\s+results', response.text, re.I,
                )
                stated_total = (
                    int(stated.group(1).replace(',', ''))
                    if stated
                    else None
                )
            self._stated_total = stated_total

            if self._crawl_brand_pages():
                brand_options = (
                    ((listing_data.get('brand_filter_bar') or {})
                     .get('filters') or {})
                    .get('brands') or {}
                ).get('options') or {}
                for brand_slug in brand_options:
                    slug = re.sub(
                        r'[^a-z0-9-]+', '-', str(brand_slug).lower(),
                    ).strip('-')
                    if not slug:
                        continue
                    yield scrapy.Request(
                        url=f"{self.listing_url}/{slug}",
                        callback=self.parse_brand,
                        errback=self.page_fetch_error,
                        meta={'brand_slug': slug, 'brand_page': 1},
                    )

        yield from self._product_requests(response)

        # PAGINATION: PriceOye's "Next" control is a script-driven
        # button with no href, so following a[rel="next"] stops after
        # the first page (36 of ~385 phones). The catalogue is served
        # at ?page=N instead; walk it until a page comes back empty.
        if not phones:
            # An empty page past the first one is the natural end of
            # the general listing.
            if page > 1:
                self._reached_catalogue_end = True
            return

        if page < self._max_listing_pages():
            yield scrapy.Request(
                url=f"{self.listing_url}?page={page + 1}",
                callback=self.parse,
                errback=self.page_fetch_error,
                meta={'listing_page': page + 1},
            )

    def parse_brand(self, response):
        """Collect a brand's current phones from its own page.

        A brand page lists the brand's current phones first and its
        discontinued models on later pages, so the first page is all
        that is needed unless it is completely full, in which case the
        current range may continue onto the next one.
        """

        phones = response.css('div.productBox')
        yield from self._product_requests(response)

        brand_page = int(response.meta.get('brand_page', 1))
        if len(phones) >= self.listing_page_size and brand_page < 2:
            slug = response.meta['brand_slug']
            yield scrapy.Request(
                url=f"{self.listing_url}/{slug}?page={brand_page + 1}",
                callback=self.parse_brand,
                errback=self.page_fetch_error,
                meta={'brand_slug': slug, 'brand_page': brand_page + 1},
            )

    @staticmethod
    def extract_product_data(response):
        """Return PriceOye's embedded ``window.product_data`` object.

        Every product page ships the full variant matrix as inline
        JSON: price, pre-discount price, availability and stock for
        each colour and storage option. It is what the page's own
        scripts read when a shopper clicks a colour, so it is the same
        data the shopper sees, without depending on CSS class names.
        """

        text = response.text
        marker = text.find('window.product_data')
        if marker == -1:
            return None
        brace = text.find('{', marker)
        if brace == -1:
            return None
        try:
            data, _ = json.JSONDecoder().raw_decode(text, brace)
        except ValueError:
            return None
        return data if isinstance(data, dict) else None

    @staticmethod
    def _parse_size_label(size_label):
        """Return (ram_gb, storage_gb) from labels like '256gb - 12gb ram'."""

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

    @staticmethod
    def _flatten_specification(raw_specification):
        """Flatten PriceOye's sectioned specification JSON to label/value."""

        if isinstance(raw_specification, str):
            try:
                raw_specification = json.loads(raw_specification)
            except ValueError:
                return {}
        if not isinstance(raw_specification, dict):
            return {}

        flattened = {}
        for rows in raw_specification.values():
            if isinstance(rows, dict):
                rows = [rows]
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for label, value in row.items():
                    text = str(value).strip() if value is not None else ''
                    if text and text.upper() not in {'N/A', 'NA', '-'}:
                        flattened[str(label).strip()] = text
        return flattened

    def _reference_price_item(self, response, data, base_item):
        """Describe a phone PriceOye lists but is not currently selling.

        Such pages carry an empty variant matrix and show only a "Last
        Updated Price" with no buy button. The page's ``schema_status``
        still reads "InStock", which is why availability is taken from
        the matrix instead: no sellable option means not available.
        """

        data_set = data.get('dataSet') or {}
        try:
            reference_price = float(data.get('lowPrice') or 0)
        except (TypeError, ValueError):
            reference_price = 0
        if reference_price <= 0:
            return None

        product_slug = (
            str(data_set.get('slug') or '').strip()
            or base_item.get('external_id')
            or response.url.rstrip('/').split('/')[-1]
        )
        review_count = int(data.get('total_rattings_count') or 0)

        image_urls = []
        for images in (data.get('product_color_images') or {}).values():
            for image in (images or {}).get('large') or []:
                if image:
                    image_urls.append(
                        image if str(image).startswith('http')
                        else f'https://images.priceoye.pk/{image}'
                    )

        item = SmartphoneItem()
        item['platform'] = 'PriceOye'
        item['structured_source'] = True
        item['product_url'] = response.url
        item['external_id'] = product_slug[:150]
        item['model'] = (
            str(data_set.get('title') or '').strip()
            or base_item.get('model', '')
        )
        item['brand'] = str(data_set.get('brand_name') or '').strip() or None
        item['color'] = 'N/A'
        item['variant'] = 'Standard'
        item['price'] = reference_price
        item['availability'] = 'Out of Stock'
        item['stock_quantity'] = 0
        item['warranty'] = (
            str(data_set.get('warranty') or '').strip()
            or 'Official Brand Warranty'
        )
        item['rating'] = data.get('average_rating') if review_count else None
        item['review_count'] = review_count
        item['image_urls'] = image_urls[:12]
        item['specifications'] = self._flatten_specification(
            data_set.get('specification')
        )
        item['scrape_timestamp'] = datetime.now(timezone.utc).isoformat()
        return item

    def _items_from_product_data(self, response, data, base_item):
        """Build one item per colour and storage option from page JSON."""

        config = data.get('product_config') or {}
        price_matrix = config.get('dataPrices')
        data_set = data.get('dataSet') or {}

        if not isinstance(price_matrix, dict) or not price_matrix:
            reference_item = self._reference_price_item(
                response, data, base_item,
            )
            return [reference_item] if reference_item else []

        product_slug = (
            str(data_set.get('slug') or '').strip()
            or base_item.get('external_id')
            or response.url.rstrip('/').split('/')[-1]
        )
        model = (
            str(data_set.get('title') or '').strip()
            or base_item.get('model', '')
        )
        brand = str(data_set.get('brand_name') or '').strip() or None
        specifications = self._flatten_specification(
            data_set.get('specification')
        )
        color_images = data.get('product_color_images') or {}

        # Display names come from the page's colour picker; the JSON
        # only carries machine keys such as "mist_blue".
        color_names = {
            variant['slug']: variant['color']
            for variant in self.extract_color_variants(response)
        }

        review_count = int(data.get('total_rattings_count') or 0)
        # A rating is only meaningful alongside at least one review.
        rating = data.get('average_rating') if review_count else None
        scraped_at = datetime.now(timezone.utc).isoformat()

        items = []
        for color_slug in sorted(price_matrix):
            sizes = price_matrix[color_slug]
            if isinstance(sizes, list):
                sizes = {'': sizes}
            if not isinstance(sizes, dict):
                continue

            color_key = str(color_slug).strip().lower()
            color_name = color_names.get(color_key) or ' '.join(
                part.capitalize()
                for part in re.split(r'[_\-\s]+', color_key)
                if part
            )

            for size_label in sorted(sizes):
                offers = sizes[size_label]
                if isinstance(offers, dict):
                    offers = [offers]
                if not isinstance(offers, list) or not offers:
                    continue
                offer = next(
                    (
                        entry for entry in offers
                        if isinstance(entry, dict)
                        and str(entry.get('store_name', '')).lower()
                        == 'priceoye'
                    ),
                    offers[0],
                )
                if not isinstance(offer, dict):
                    continue

                price_text = str(offer.get('product_price') or '').strip()
                if not price_text:
                    continue

                ram_gb, storage_gb = self._parse_size_label(size_label)
                variant_specifications = dict(specifications)
                if ram_gb is not None:
                    variant_specifications['ram'] = f'{ram_gb}GB'
                if storage_gb is not None:
                    variant_specifications['storage_capacity'] = (
                        f'{storage_gb}GB'
                    )

                size_slug = re.sub(
                    r'[^a-z0-9]+', '-', str(size_label).lower(),
                ).strip('-')
                external_id = '--'.join(
                    part for part in (
                        product_slug,
                        color_key or 'default',
                        size_slug,
                    )
                    if part
                )

                images = (color_images.get(color_slug) or {}).get('large')
                image_urls = [
                    image if str(image).startswith('http')
                    else f'https://images.priceoye.pk/{image}'
                    for image in (images or [])
                    if image
                ]

                item = SmartphoneItem()
                item['platform'] = 'PriceOye'
                item['structured_source'] = True
                item['product_url'] = response.url
                item['external_id'] = external_id[:150]
                item['model'] = model
                item['brand'] = brand
                item['color'] = color_name or 'N/A'
                item['variant'] = (
                    str(size_label).upper()
                    if size_label
                    else 'Standard'
                )
                item['price'] = f'Rs {price_text}'
                retail_text = str(offer.get('retail_price') or '').strip()
                if retail_text:
                    item['original_price'] = f'Rs {retail_text}'
                item['availability'] = (
                    'In Stock'
                    if str(offer.get('product_availability') or '')
                    .strip().lower() == 'in stock'
                    else 'Out of Stock'
                )
                item['stock_quantity'] = offer.get('stock_qty')
                item['warranty'] = (
                    str(offer.get('product_warranty') or '').strip()
                    or str(data_set.get('warranty') or '').strip()
                    or 'Official Brand Warranty'
                )
                item['rating'] = rating
                item['review_count'] = review_count
                item['image_urls'] = image_urls
                item['specifications'] = variant_specifications
                item['scrape_timestamp'] = scraped_at
                items.append(item)

        return items


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

        # Preferred path: the page's own variant matrix. It covers
        # every colour AND storage option with its exact price and
        # stock, which the visible markup only shows for whichever
        # option is currently selected.
        product_data = self.extract_product_data(response)
        if product_data is not None:
            structured_items = self._items_from_product_data(
                response, product_data, base_item,
            )
            if structured_items:
                yield from structured_items

                # Reviews are published per product, so they are
                # attached to one deterministic listing (the first in
                # colour/size order) rather than repeated per variant.
                has_reviews = (
                    structured_items[0].get("review_count") or 0
                ) > 0
                if has_reviews and self._max_reviews_per_listing() > 0:
                    target_id = structured_items[0]["external_id"]
                    yield scrapy.Request(
                        url=f"{response.url.rstrip('/')}/reviews",
                        callback=self.parse_reviews,
                        errback=self.review_fetch_error,
                        cb_kwargs={"external_listing_id": target_id},
                        meta={"external_listing_id": target_id},
                    )
                return

        # Fallback path: no usable JSON on the page, read the markup.
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
