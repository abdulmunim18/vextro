import scrapy

class SmartphoneItem(scrapy.Item):
    # Core Product Details
    brand = scrapy.Field()
    model = scrapy.Field()
    variant = scrapy.Field()      # e.g., 8GB RAM / 128GB Storage
    color = scrapy.Field()
    condition = scrapy.Field()
    warranty = scrapy.Field()
    is_available = scrapy.Field()
    external_id = scrapy.Field()
    
    # Time-Series Data (12-hour refresh cycle)
    price = scrapy.Field()
    availability = scrapy.Field() # In Stock / Out of Stock
    seller = scrapy.Field()
    
    # NLP & Operational Data
    platform = scrapy.Field()     # 'Daraz' or 'PriceOye'
    product_url = scrapy.Field()
    scrape_timestamp = scrapy.Field()
    raw_html_path = scrapy.Field() # Link to where the raw snapshot is saved