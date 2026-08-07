import pytest
from scrapy.http import HtmlResponse, TextResponse
import json
import os

from vextro_scraper.spiders.priceoye_spider import PriceoyeSpider
from vextro_scraper.spiders.daraz_spider import DarazSpider

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
                    "inStock": True
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
