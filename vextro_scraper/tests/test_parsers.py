import json
from pathlib import Path

import pytest
from scrapy.http import HtmlResponse, Request, TextResponse

from vextro_scraper.items import SmartphoneItem
from vextro_scraper.pipelines import (
    VextroCleaningPipeline,
    infer_brand,
)
from vextro_scraper.spiders.priceoye_spider import (
    PriceOyeReviewParserError,
    PriceoyeSpider,
)
from vextro_scraper.spiders.daraz_spider import (
    DarazParserError,
    DarazSpider,
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


def test_daraz_malformed_json_raises_monitorable_parser_error():
    spider = DarazSpider()
    response = TextResponse(
        url='https://www.daraz.pk/smartphones/?ajax=true',
        body=b'not-json',
    )

    with pytest.raises(DarazParserError):
        list(spider.parse(response))


def test_daraz_parser_constructs_url_when_marketplace_omits_it():
    spider = DarazSpider()
    response = TextResponse(
        url='https://www.daraz.pk/smartphones/?ajax=true',
        body=json.dumps({
            'mods': {
                'listItems': [{
                    'itemId': '1965744785',
                    'name': 'Samsung Galaxy A55 8GB RAM 256GB ROM',
                    'price': '125000',
                    'inStock': True,
                }],
            },
            'mainInfo': {'page': 1, 'totalResults': 1, 'pageSize': 40},
        }).encode('utf-8'),
    )

    item = list(spider.parse(response))[0]

    assert item['product_url'] == (
        'https://www.daraz.pk/products/i1965744785.html'
    )


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


def test_priceoye_review_parser_uses_saved_marketplace_fixture():
    fixture = (
        Path(__file__).parent
        / 'fixtures'
        / 'priceoye_reviews.html'
    ).read_bytes()
    spider = PriceoyeSpider()
    response = HtmlResponse(
        url='https://priceoye.pk/mobiles/test/sanitized/reviews',
        encoding='utf-8',
        body=fixture,
    )

    batch = list(
        spider.parse_reviews(response, 'sanitized-listing')
    )[0]

    assert batch['platform'] == 'PriceOye'
    assert batch['external_listing_id'] == 'sanitized-listing'
    assert len(batch['reviews']) == 3
    assert batch['reviews'][0]['rating'] == 5
    assert batch['reviews'][0]['verified_purchase'] is True
    assert batch['reviews'][0]['review_text'].endswith('❤️')
    assert batch['reviews'][1]['review_text'] is None
    assert batch['reviews'][1]['verified_purchase'] is False
    assert batch['reviews'][2]['reviewer_display_name'] is None
    assert batch['reviews'][2]['reviewed_at'].startswith('2025-09-07')


def test_priceoye_review_parser_rejects_advertised_broken_markup():
    spider = PriceoyeSpider()
    response = HtmlResponse(
        url='https://priceoye.pk/mobiles/test/broken/reviews',
        encoding='utf-8',
        body=b'<section class="product-rating">12 Reviews</section>',
    )

    with pytest.raises(PriceOyeReviewParserError):
        list(spider.parse_reviews(response, 'broken-listing'))


def _load_iphone17_response():
    fixture = (
        Path(__file__).parent
        / 'fixtures'
        / 'priceoye_iphone17_colors.html'
    ).read_bytes()
    return HtmlResponse(
        url='https://priceoye.pk/mobiles/apple/apple-iphone-17',
        encoding='utf-8',
        body=fixture,
        request=Request(
            url='https://priceoye.pk/mobiles/apple/apple-iphone-17',
            meta={
                'item': {
                    'platform': 'PriceOye',
                    'model': 'Apple Iphone 17',
                    'external_id': 'apple-iphone-17',
                },
            },
        ),
    )


def test_priceoye_color_variants_parsing_is_accurate():
    """Every <ul.colors> li must map to a distinct variant entry.

    Live PriceOye markup for the iPhone 17 as of 2026-10-01 lists five
    colours; Black, White and Mist Blue carry a <span class="sold-out-tag">
    marker while Sage (active) and Lavender do not. The parser must
    reflect that split exactly, since the UI reads is_available
    directly from this signal.
    """

    response = _load_iphone17_response()
    variants = PriceoyeSpider.extract_color_variants(response)

    assert [variant['color'] for variant in variants] == [
        'Black', 'White', 'Sage', 'Lavender', 'Mist Blue',
    ]
    assert [variant['slug'] for variant in variants] == [
        'black', 'white', 'sage', 'lavender', 'mist_blue',
    ]
    assert [variant['is_available'] for variant in variants] == [
        False, False, True, True, False,
    ]
    assert [variant['active'] for variant in variants] == [
        False, False, True, False, False,
    ]
    assert variants[2]['thumbnail_url'].endswith(
        'apple-iphone-17-pakistan-priceoye-yknw6-100x100.webp',
    )


def test_priceoye_extract_prices_captures_discount():
    """The scraper reads both the headline price and the pre-discount
    original. ``<sup>Rs</sup>`` and the numeric text sit in sibling
    nodes, so a single space between them is expected and the
    downstream cleaning pipeline strips it."""

    response = _load_iphone17_response()
    current, original = PriceoyeSpider.extract_prices(response)
    assert current == 'Rs 384,999'
    assert original == 'Rs 399,000'


def test_priceoye_parse_product_yields_one_item_per_color():
    """parse_product must fan out one SmartphoneItem per colour.

    Each colour gets a stable external_id (base slug + '--' + colour
    slug), the correct availability, and a 500x500 image rewritten
    from the inline 100x100 swatch when it is not the active colour.
    Exactly one review-fetch Request is scheduled against the
    alphabetically-first colour (``apple-iphone-17--black`` here) so
    reviews land on a deterministic listing across runs.
    """

    spider = PriceoyeSpider()
    response = _load_iphone17_response()

    emitted = list(spider.parse_product(response))

    items = [entry for entry in emitted if isinstance(entry, SmartphoneItem)]
    requests = [entry for entry in emitted if isinstance(entry, Request)]

    assert len(items) == 5
    assert [item['color'] for item in items] == [
        'Black', 'White', 'Sage', 'Lavender', 'Mist Blue',
    ]
    assert [item['availability'] for item in items] == [
        'Out of Stock', 'Out of Stock', 'In Stock', 'In Stock', 'Out of Stock',
    ]
    assert [item['external_id'] for item in items] == [
        'apple-iphone-17--black',
        'apple-iphone-17--white',
        'apple-iphone-17--sage',
        'apple-iphone-17--lavender',
        'apple-iphone-17--mist_blue',
    ]
    # Every colour variant inherits the same product-level pricing.
    for item in items:
        assert item['price'] == 'Rs 384,999'
        assert item['original_price'] == 'Rs 399,000'
        assert item['model'] == 'Apple Iphone 17'
        assert item['warranty'] == '1 Year Official Warranty'

    # Active colour (Sage) reuses the full-size gallery image; the
    # other colours promote their 100x100 swatch into 500x500.
    sage_item = next(item for item in items if item['color'] == 'Sage')
    assert any(
        'mxvta-500x500.webp' in url for url in sage_item['image_urls']
    )
    black_item = next(item for item in items if item['color'] == 'Black')
    assert black_item['image_urls'] == [
        'https://images.priceoye.pk/apple-iphone-17-pakistan-priceoye-wr7vg-500x500.webp',
    ]

    # Reviews attach to the alphabetically-first colour (Black) so the
    # mapping stays stable even when PriceOye swaps the active colour.
    assert len(requests) == 1
    review_request = requests[0]
    assert review_request.url.endswith('/apple-iphone-17/reviews')
    assert review_request.cb_kwargs['external_listing_id'] == (
        'apple-iphone-17--black'
    )


def test_priceoye_parse_product_falls_back_when_no_color_selector():
    """Products without ``ul.colors`` must still produce one listing.

    This preserves the old single-item behaviour for SKUs that
    PriceOye lists as a single-colour product, so a markup change
    does not silently drop them from the catalog.
    """

    body = (
        b"<html><body><h1>Mono Phone</h1>"
        b"<div class='product-price'><span class='summary-price'>Rs10,000</span></div>"
        b"</body></html>"
    )
    response = HtmlResponse(
        url='https://priceoye.pk/mobiles/test/mono-phone',
        encoding='utf-8',
        body=body,
        request=Request(
            url='https://priceoye.pk/mobiles/test/mono-phone',
            meta={
                'item': {
                    'platform': 'PriceOye',
                    'model': 'Mono Phone',
                    'external_id': 'mono-phone',
                },
            },
        ),
    )

    emitted = list(PriceoyeSpider().parse_product(response))
    items = [entry for entry in emitted if isinstance(entry, SmartphoneItem)]
    assert len(items) == 1
    assert items[0]['color'] == 'N/A'
    assert items[0]['external_id'] == 'mono-phone'
