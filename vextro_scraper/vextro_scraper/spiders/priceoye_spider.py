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
        import re
        
        item = response.meta['item']
        
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
        in_stock = response.css('button.btn-checkout, a.btn-checkout, button#add-to-cart-btn')
        item['availability'] = 'In Stock' if in_stock else 'Out of Stock'

        # 5. Warranty: Set clean default unless explicitly found
        warranty_text = response.xpath('//table//td[contains(text(), "Warranty")]/following-sibling::td/text()').get()
        item['warranty'] = warranty_text.strip() if warranty_text else 'Official Brand Warranty'
        
        yield item