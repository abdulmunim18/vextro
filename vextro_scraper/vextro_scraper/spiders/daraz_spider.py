import scrapy
import json
from datetime import datetime
from vextro_scraper.items import SmartphoneItem

class DarazSpider(scrapy.Spider):
    name = "daraz_smartphones"
    allowed_domains = ["daraz.pk"]
    
    # We use the internal AJAX API for reliable scraping
    start_urls = ["https://www.daraz.pk/smartphones/?ajax=true"]

    custom_settings = {
        'USER_AGENT': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'DOWNLOAD_DELAY': 2, # Respectful scraping
    }

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
                item['price'] = item_data.get('price', '0')
                
                # Availability
                in_stock = item_data.get('inStock', False)
                item['availability'] = 'In Stock' if in_stock else 'Out of Stock'
                
                # Parse additional specs if available in the title or attributes
                # The Normalizer in Module 6.2 will extract RAM/Storage cleanly from the title.
                item['variant'] = 'Standard'
                item['color'] = 'N/A'
                item['warranty'] = 'Standard Warranty'
                
                item['scrape_timestamp'] = datetime.now().isoformat()
                
                yield item

            # PAGINATION: Check if there's a next page and follow it
            main_info = data.get("mainInfo", {})
            page = int(main_info.get('page', 1))
            total_pages = int(main_info.get('totalResults', 0)) // int(main_info.get('pageSize', 40)) + 1
            
            if page < total_pages:
                next_page_url = f"https://www.daraz.pk/smartphones/?ajax=true&page={page + 1}"
                yield scrapy.Request(url=next_page_url, callback=self.parse)
                
        except json.JSONDecodeError:
            self.logger.error("Failed to parse JSON response from Daraz API.")
