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
    sku = scrapy.Field()          # Stable marketplace SKU/model code
    # True when ``model`` is the marketplace's own model name, not a
    # seller's free-text title.
    exact_model_title = scrapy.Field()

    # Time-Series Data (12-hour refresh cycle)
    price = scrapy.Field()
    original_price = scrapy.Field()  # Strike-through / list price
    availability = scrapy.Field() # In Stock / Out of Stock
    seller = scrapy.Field()

    # Marketplace review aggregates shown on the listing itself
    rating = scrapy.Field()
    review_count = scrapy.Field()

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
