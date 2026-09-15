import scrapy
import json
from datetime import datetime, timezone
from vextro_scraper.items import SmartphoneItem


class DarazParserError(ValueError):
    """A Daraz response could not be parsed as the expected JSON payload."""

    error_type = "invalid_marketplace_response"
    error_stage = "parse"


class DarazSpider(scrapy.Spider):
    name = "daraz_smartphones"
    platform_code = "daraz"
    parser_version = "daraz-v1"
    allowed_domains = ["daraz.pk"]
    
    # We use the internal AJAX API for reliable scraping
    start_urls = ["https://www.daraz.pk/smartphones/?ajax=true"]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DOWNLOAD_DELAY': 2, # Respectful scraping
    }

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

        return specifications

    def parse(self, response):
        try:
            data = json.loads(response.text)
            
            # Extract products list from JSON response
            mods = data.get("mods", {})
            list_items = mods.get("listItems", [])
            
            for item_data in list_items:
                item = SmartphoneItem()
                item['platform'] = 'Daraz'
                
                # Get the external ID (itemId)
                item['external_id'] = item_data.get('itemId', '')
                
                # Clean URL
                product_url = item_data.get('productUrl', '')
                if product_url.startswith('//'):
                    product_url = 'https:' + product_url
                item['product_url'] = product_url
                
                # Get Title and Price
                item['model'] = item_data.get('name', '')
                item['brand'] = (
                    item_data.get('brandName')
                    or item_data.get('brand')
                    or item_data.get('brand_name')
                )
                item['price'] = item_data.get('price')

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
                item['availability'] = 'In Stock' if in_stock else 'Out of Stock'
                
                # Parse additional specs if available in the title or attributes
                # The Normalizer in Module 6.2 will extract RAM/Storage cleanly from the title.
                item['variant'] = 'Standard'
                item['color'] = 'N/A'
                item['warranty'] = 'Standard Warranty'
                
                item['scrape_timestamp'] = datetime.now(timezone.utc).isoformat()
                
                yield item

            # PAGINATION: Check if there's a next page and follow it
            main_info = data.get("mainInfo", {})
            page = int(main_info.get('page', 1))
            total_pages = int(main_info.get('totalResults', 0)) // int(main_info.get('pageSize', 40)) + 1
            
            if page < total_pages:
                next_page_url = f"https://www.daraz.pk/smartphones/?ajax=true&page={page + 1}"
                yield scrapy.Request(url=next_page_url, callback=self.parse)
                
        except json.JSONDecodeError as exc:
            self.logger.error("Failed to parse JSON response from Daraz API.")
            raise DarazParserError(
                "Daraz returned malformed JSON."
            ) from exc
