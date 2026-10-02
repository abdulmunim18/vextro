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
    original_price = scrapy.Field()   # Pre-discount strike-through price, if any.
    availability = scrapy.Field() # In Stock / Out of Stock
    stock_quantity = scrapy.Field()   # Units left, when the marketplace states it.
    seller = scrapy.Field()

    # Marketplace-reported review aggregate for the product.
    rating = scrapy.Field()
    review_count = scrapy.Field()

    # True when brand, model, colour and storage came from structured
    # page data rather than being inferred from a free-text title.
    structured_source = scrapy.Field()
    
    # NLP & Operational Data
    platform = scrapy.Field()     # 'Daraz' or 'PriceOye'
    product_url = scrapy.Field()
    image_urls = scrapy.Field()   # Ordered product gallery URLs
    specifications = scrapy.Field() # Normalized label/value technical data
    scrape_timestamp = scrapy.Field()
    raw_html_path = scrapy.Field() # Link to where the raw snapshot is saved


class ReviewBatchItem(scrapy.Item):
    """A bounded review collection tied to a known marketplace listing."""

    platform = scrapy.Field()
    external_listing_id = scrapy.Field()
    source_url = scrapy.Field()
    reviews = scrapy.Field()
