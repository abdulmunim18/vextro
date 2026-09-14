from scrapy.http import HtmlResponse, Request, TextResponse
import json

from vextro_scraper.spiders.priceoye_spider import PriceoyeSpider
from vextro_scraper.spiders.daraz_spider import DarazSpider
from vextro_scraper.pipelines import (
    VextroCleaningPipeline,
    infer_brand,
)

def test_daraz_parser():
    """Test the Daraz spider JSON parser offline using a fixture."""
    spider = DarazSpider()
    
    # Mock Daraz JSON Response
    mock_json_data = {
        "mods": {
            "listItems": [
                {
                    "itemId": "daraz-test-123",
                    "productUrl": "//www.daraz.pk/products/test.html",
                    "name": "Samsung Galaxy A55 5G 8GB RAM",
                    "price": "125000",
                    "inStock": True,
                    "image": "//static-01.daraz.pk/test-phone.jpg",
                    "attributes": [
                        {"name": "RAM", "value": "8GB"},
                        {"name": "Battery", "value": "5000 mAh"}
                    ]
                }
            ]
        },
        "mainInfo": {"page": "1", "totalResults": "1", "pageSize": "40"}
    }
    
    # Create a mock Scrapy TextResponse
    response = TextResponse(
        url='https://www.daraz.pk/smartphones/?ajax=true',
        body=json.dumps(mock_json_data).encode('utf-8')
    )
    
    # Run the spider parser
    results = list(spider.parse(response))
    
    # We expect 1 item (the smartphone item)
    assert len(results) == 1
    
    item = results[0]
    
    # Check item attributes
    assert item['platform'] == 'Daraz'
    assert item['external_id'] == 'daraz-test-123'
    assert item['model'] == 'Samsung Galaxy A55 5G 8GB RAM'
    assert item['price'] == '125000'
    assert item['availability'] == 'In Stock'
    assert item['product_url'] == 'https://www.daraz.pk/products/test.html'
    assert item['image_urls'] == [
        'https://static-01.daraz.pk/test-phone.jpg'
    ]
    assert item['specifications'] == {
        'RAM': '8GB',
        'Battery': '5000 mAh',
    }


def test_cleaning_pipeline_infers_brand_and_title_specifications():
    item = {
        'model': (
            'Samsung Galaxy A57 8GB RAM 256GB ROM '
            '5000mAh Battery 6.7 Inches Display'
        ),
        'price': 'Rs 168,999',
        'availability': 'In Stock',
        'product_url': 'https://www.daraz.pk/products/a57.html',
        'image_urls': [],
        'specifications': {},
    }

    cleaned = VextroCleaningPipeline().process_item(item, None)

    assert infer_brand(cleaned['model']) == 'Samsung'
    assert cleaned['brand'] == 'Samsung'
    assert cleaned['specifications']['ram'] == '8GB'
    assert cleaned['specifications']['storage_capacity'] == '256GB'
    assert cleaned['specifications']['battery_capacity'] == '5000 mAh'
    assert cleaned['specifications']['display'] == '6.7 inches'


def test_priceoye_product_parser_extracts_gallery_images():
    """PriceOye detail pages should emit their full-size image gallery."""

    spider = PriceoyeSpider()
    item = {
        'platform': 'PriceOye',
        'external_id': 'priceoye-test-phone',
        'model': 'PriceOye Test Phone (8GB-256GB)',
        'price': 'Rs 99,999',
        'product_url': 'https://priceoye.pk/mobiles/test/test-phone',
    }
    request = Request(
        url=item['product_url'],
        meta={'item': item},
    )
    response = HtmlResponse(
        url=item['product_url'],
        request=request,
        encoding='utf-8',
        body=b'''
            <html>
              <head>
                <meta property="og:image" content="https://images.priceoye.pk/fallback.webp">
              </head>
              <body>
                <div class="product-price">Rs 99,999</div>
                <ul class="colors"><li class="active">Midnight Black</li></ul>
                <div class="po-variant-card"><ul class="variants"><li class="active">256GB</li></ul></div>
                <button class="new-purchase-control">Add to Cart</button>
                <img class="main-product-img" src="https://images.priceoye.pk/test-phone-front-500x500.webp">
                <img class="main-product-img" src="https://images.priceoye.pk/test-phone-back-500x500.webp">
                <section id="specifications">
                  <table>
                    <tr><td>RAM</td><td>8GB</td></tr>
                    <tr><td>Battery Capacity</td><td>5000 mAh</td></tr>
                  </table>
                </section>
              </body>
            </html>
        ''',
    )

    parsed_item = list(spider.parse_product(response))[0]

    assert parsed_item['image_urls'] == [
        'https://images.priceoye.pk/test-phone-front-500x500.webp',
        'https://images.priceoye.pk/test-phone-back-500x500.webp',
    ]
    assert parsed_item['specifications'] == {
        'RAM': '8GB',
        'Battery Capacity': '5000 mAh',
    }
    assert parsed_item['availability'] == 'In Stock'


def test_priceoye_availability_uses_embedded_variant_stock():
    spider = PriceoyeSpider()
    request = Request(
        url='https://priceoye.pk/mobiles/samsung/test-phone',
        meta={'item': {
            'platform': 'PriceOye',
            'external_id': 'structured-stock-phone',
            'model': 'Samsung Structured Stock Phone',
            'price': 'Rs 99,999',
            'product_url': (
                'https://priceoye.pk/mobiles/samsung/test-phone'
            ),
        }},
    )
    response = HtmlResponse(
        url=request.url,
        request=request,
        encoding='utf-8',
        body=b'''
          <html><body>
            <script>
              window.product_data = {
                "product_config": {
                  "dataPrices": {
                    "black": [{
                      "product_availability": "In Stock",
                      "stock_qty": 2
                    }],
                    "white": [{
                      "product_availability": "Out Of Stock",
                      "stock_qty": 0
                    }]
                  }
                },
                "schema_status": "InStock"
              };
            </script>
          </body></html>
        ''',
    )

    assert spider.extract_availability(response) is True
    parsed_item = list(spider.parse_product(response))[0]
    assert parsed_item['availability'] == 'In Stock'


def test_priceoye_availability_detects_all_variants_out_of_stock():
    spider = PriceoyeSpider()
    response = HtmlResponse(
        url='https://priceoye.pk/mobiles/test/out-of-stock',
        encoding='utf-8',
        body=b'''
          <html><body><script>
            window.product_data = {
              "product_availability": "Out Of Stock",
              "schema_status": "OutOfStock"
            };
          </script></body></html>
        ''',
    )

    assert spider.extract_availability(response) is False
