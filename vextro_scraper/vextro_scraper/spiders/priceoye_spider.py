import scrapy
import re
from datetime import datetime
from vextro_scraper.items import SmartphoneItem

class PriceoyeSpider(scrapy.Spider):
    name = "priceoye_smartphones"
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
                item['price'] = next((t for t in details if 'Rs' in t), '')
            
            item['scrape_timestamp'] = datetime.now().isoformat()
            
            # DEEP SCRAPING: Instead of saving the item immediately, 
            # we tell Scrapy to visit the product URL and pass the item to a new function!
            if item['product_url']:
                yield response.follow(item['product_url'], callback=self.parse_product, meta={'item': item})

        # PAGINATION: Find the "Next" page button and loop the spider
        next_page = response.css('a[rel="next"]::attr(href)').get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)


    def parse_product(self, response):
        item = response.meta['item']

        item['brand'] = (
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
        
        # 1. Clean Price: Extract ONLY the first price matching pattern "Rs X,XXX" or "Rs XX,XXX"
        price_raw = response.css('div.product-price ::text').getall()
        full_price_str = "".join([p.strip() for p in price_raw if p.strip()])
        price_match = re.search(r'Rs\s?[\d,]+', full_price_str)
        if price_match:
            item['price'] = price_match.group(0)

        # 2. Extract Color
        color = response.css('ul.colors li.active ::text').get()
        item['color'] = color.strip() if color else 'N/A'
        
        # 3. Extract Variant (RAM/Storage):
        # First check title regex, then check page active buttons
        title_variant = re.search(r'\(\d+GB.*?\)', item.get('model', ''))
        variant_btn = response.css('div.po-variant-card ul.variants li.active ::text').get()
        
        if title_variant:
            item['variant'] = title_variant.group(0)
        elif variant_btn:
            item['variant'] = variant_btn.strip()
        else:
            item['variant'] = 'Standard'

        # 4. Availability
        item['availability'] = (
            'In Stock'
            if self.extract_availability(response)
            else 'Out of Stock'
        )

        # 5. Warranty: Set clean default unless explicitly found
        warranty_text = response.xpath('//table//td[contains(text(), "Warranty")]/following-sibling::td/text()').get()
        item['warranty'] = warranty_text.strip() if warranty_text else 'Official Brand Warranty'

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
