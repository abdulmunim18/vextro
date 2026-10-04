import json
from pathlib import Path

import pytest
from scrapy.exceptions import IgnoreRequest
from scrapy.http import HtmlResponse, Request, TextResponse
from twisted.python.failure import Failure

from vextro_scraper.normalizers import clean_listing_title
from vextro_scraper.pipelines import (
    NonSmartphoneItemError,
    VextroCleaningPipeline,
    infer_brand,
)
from vextro_scraper.spiders.priceoye_spider import (
    PriceOyeReviewParserError,
    PriceoyeSpider,
)
from vextro_scraper.spiders.daraz_spider import (
    DarazParserError,
    DarazReviewBlockedError,
    DarazReviewDisallowedError,
    DarazReviewFetchError,
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
    # The spider now parses prices into numbers so every platform delivers
    # one comparable type.
    assert item['price'] == 125000.0
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


def test_daraz_parser_strips_store_prefix_and_stock_code():
    """A Daraz store sells under its own name; the phone keeps only its own.

    "Carrefour Samsung Galaxy A07 4+128GB Green-303662" is the same phone
    PriceOye lists as "Samsung Galaxy A07", and it only matches it once the
    store name and the marketplace stock code are gone.
    """

    spider = DarazSpider()
    response = TextResponse(
        url='https://www.daraz.pk/smartphones/?ajax=true',
        body=json.dumps({
            'mods': {
                'listItems': [{
                    'itemId': '303662',
                    'name': (
                        'Carrefour Samsung Galaxy A07 4+128GB Green-303662'
                    ),
                    'price': '62500',
                    'inStock': True,
                    'sellerName': 'Carrefour Pakistan',
                    'image': '//img.drz.lazcdn.com/a07-green.jpg',
                }],
            },
            'mainInfo': {'page': 1, 'totalResults': 1, 'pageSize': 40},
        }).encode('utf-8'),
    )

    item = list(spider.parse(response))[0]
    cleaned = VextroCleaningPipeline().process_item(item, None)

    assert cleaned['model'] == 'Samsung Galaxy A07 4+128GB Green'
    assert cleaned['brand'] == 'Samsung'
    assert cleaned['seller']['name'] == 'Carrefour Pakistan'
    assert cleaned['image_urls'] == [
        'https://img.drz.lazcdn.com/a07-green.jpg'
    ]


def test_cleaning_pipeline_keeps_a_title_that_is_only_a_store_name():
    """Cleaning must never leave a listing without anything to match on."""

    cleaned = VextroCleaningPipeline().process_item(
        {
            'model': 'Carrefour',
            'price': '62500',
            'availability': 'In Stock',
            'product_url': 'https://www.daraz.pk/products/i303662.html',
            'seller': {'name': 'Carrefour Pakistan'},
            'image_urls': [],
            'specifications': {},
        },
        None,
    )

    assert cleaned['model'] == 'Carrefour'


def test_daraz_parser_reads_gallery_from_alternate_payload_fields():
    """Daraz names the catalog image differently per rendering surface."""

    spider = DarazSpider()

    assert spider.extract_image_urls({
        'mainImage': {'url': '//img.drz.lazcdn.com/primary.jpg'},
        'images': ['https://img.drz.lazcdn.com/gallery-1.jpg'],
    }) == [
        'https://img.drz.lazcdn.com/gallery-1.jpg',
        'https://img.drz.lazcdn.com/primary.jpg',
    ]

    assert spider.extract_image_urls({'thumbUrl': 'https://x.pk/t.webp'}) == [
        'https://x.pk/t.webp'
    ]

    assert spider.extract_image_urls({}) == []


def test_cleaning_pipeline_rejects_images_that_are_not_photographs():
    """Placeholders and tracking pixels must not pose as product images."""

    cleaned = VextroCleaningPipeline().process_item(
        {
            'model': 'Samsung Galaxy A07 4GB 128GB',
            'price': '62500',
            'availability': 'In Stock',
            'product_url': 'https://www.daraz.pk/products/i303662.html',
            'image_urls': [
                'https://placehold.co/400x400.png',
                '/static/a07.jpg',
                'https://img.drz.lazcdn.com/a07.jpg_720x720q80.jpg_.webp',
                'https://img.drz.lazcdn.com/a07.jpg_720x720q80.jpg_.webp',
                'https://www.daraz.pk/tracker',
            ],
            'specifications': {},
        },
        None,
    )

    assert cleaned['image_urls'] == [
        'https://www.daraz.pk/static/a07.jpg',
        'https://img.drz.lazcdn.com/a07.jpg_720x720q80.jpg_.webp',
    ]


def test_priceoye_product_parser_falls_back_to_structured_gallery():
    """PriceOye's JSON-LD carries the gallery when the markup changes."""

    spider = PriceoyeSpider()
    item = {
        'platform': 'PriceOye',
        'external_id': 'samsung-galaxy-a07',
        'model': 'Samsung Galaxy A07',
        'price': 'Rs 35,495',
        'product_url': (
            'https://priceoye.pk/mobiles/samsung/samsung-galaxy-a07'
        ),
    }
    request = Request(url=item['product_url'], meta={'item': item})
    response = HtmlResponse(
        url=item['product_url'],
        request=request,
        encoding='utf-8',
        body=b'''
            <html>
              <head>
                <script type="application/ld+json">
                {
                  "@type": "Product",
                  "name": "Samsung Galaxy A07",
                  "image": [
                    "https://images.priceoye.pk/samsung-galaxy-a07.webp"
                  ],
                  "offers": {
                    "@type": "Offer",
                    "price": "35495",
                    "availability": "https://schema.org/InStock"
                  }
                }
                </script>
              </head>
              <body>
                <div class="product-price">Rs 35,495</div>
              </body>
            </html>
        ''',
    )

    parsed_item = list(spider.parse_product(response))[0]

    assert parsed_item['image_urls'] == [
        'https://images.priceoye.pk/samsung-galaxy-a07.webp'
    ]


def test_clean_listing_title_drops_stock_codes_but_keeps_model_years():
    """A six-digit shop code is noise; a model year identifies the phone."""

    assert clean_listing_title(
        'Carrefour | Oppo Mobile A6 8+256GB Gold (306237)',
        seller_name='Carrefour Pakistan',
    ) == 'Oppo Mobile A6 8+256GB Gold'
    assert clean_listing_title(
        'Samsung Galaxy A07 [SKU: 303662]',
    ) == 'Samsung Galaxy A07'
    assert clean_listing_title('Nokia 130 (2023)') == 'Nokia 130 (2023)'


def test_priceoye_pagination_walks_numbered_catalog_pages():
    """PriceOye's "next" anchor carries no href, so pages are walked.

    Following that empty anchor ended every crawl after the first page,
    which is why most of the PriceOye catalog never reached VEXTRO.
    """

    spider = PriceoyeSpider()
    response = HtmlResponse(
        url='https://priceoye.pk/mobiles',
        encoding='utf-8',
        body=b'''
            <html><body>
              <div class="productBox">
                <a href="https://priceoye.pk/mobiles/samsung/galaxy-a07"></a>
                <div class="detail-box">Samsung Galaxy A07 Rs 35,495</div>
              </div>
              <a rel="next" class="next btn">Next</a>
            </body></html>
        ''',
    )

    results = list(spider.parse(response))
    followed = [request.url for request in results]

    assert 'https://priceoye.pk/mobiles?page=2' in followed


def test_priceoye_pagination_stops_on_an_empty_page():
    spider = PriceoyeSpider()
    response = HtmlResponse(
        url='https://priceoye.pk/mobiles?page=12',
        encoding='utf-8',
        body=b'<html><body><a rel="next" class="next btn"></a></body></html>',
    )

    assert list(spider.parse(response, page_number=12)) == []


def test_priceoye_pagination_prefers_a_real_next_link():
    spider = PriceoyeSpider()
    response = HtmlResponse(
        url='https://priceoye.pk/mobiles',
        encoding='utf-8',
        body=b'''
            <html><body>
              <div class="productBox">
                <a href="/mobiles/samsung/galaxy-a07"></a>
                <div class="detail-box">Samsung Galaxy A07 Rs 35,495</div>
              </div>
              <a rel="next" href="/mobiles?page=2&sort=new">Next</a>
            </body></html>
        ''',
    )

    followed = [request.url for request in spider.parse(response)]

    assert 'https://priceoye.pk/mobiles?page=2&sort=new' in followed


def test_priceoye_catalog_page_url_replaces_an_existing_page_parameter():
    assert PriceoyeSpider.catalog_page_url(
        'https://priceoye.pk/mobiles?page=3',
        4,
    ) == 'https://priceoye.pk/mobiles?page=4'


def test_infer_brand_prefers_the_maker_over_the_shop():
    """Daraz puts the seller in its brand field; the catalog must not."""

    assert infer_brand(
        'Carrefour Samsung Galaxy A07 4+128GB Green',
        'Carrefour',
    ) == 'Samsung'
    assert infer_brand('Oppo A6 8+256GB', 'OPPO Pakistan Official') == 'Oppo'
    assert infer_brand('Redmi 15 4G', 'Redmi') == 'Xiaomi'
    assert infer_brand('Vivo Y29 5G', 'vivo .') == 'Vivo'
    assert infer_brand('Faywa F1', 'FAYWA TRADING (PVT) LTD') == 'Faywa'


def test_infer_brand_keeps_small_brands_and_drops_shop_names():
    # A real low-cost brand VEXTRO does not know yet is kept as it stands.
    assert infer_brand('me Mobile L109', 'me Mobile') == 'me Mobile'
    assert infer_brand('E-Tachi iPro', 'E-Tachi') == 'E-Tachi'

    # A shop name on an unrecognised phone is no brand at all.
    assert infer_brand('Mystery Device X1', 'Al Fatah Electronics Store') is None
    assert infer_brand('Some Phone', '.No Brand.') is None


def test_cleaning_pipeline_drops_accessories_from_the_phone_catalog():
    """The smartphones category also serves cables, chargers and covers."""

    pipeline = VextroCleaningPipeline()

    with pytest.raises(NonSmartphoneItemError):
        pipeline.process_item(
            {
                'platform': 'Daraz',
                'external_id': '1960769278',
                'model': '2 in 1 OTG CABLE TYPE C & MICRO',
                'price': '399',
                'availability': 'In Stock',
                'product_url': 'https://www.daraz.pk/products/i1960769278.html',
                'image_urls': [],
                'specifications': {},
            },
            None,
        )

    with pytest.raises(NonSmartphoneItemError):
        pipeline.process_item(
            {
                'platform': 'Daraz',
                'external_id': '1961466463',
                'model': (
                    'Original Samsung 45W PD UK Pin PPS Super Fast GaN '
                    'Charger UK Plug for GALAXY S25 S24'
                ),
                'price': '29000',
                'availability': 'In Stock',
                'product_url': 'https://www.daraz.pk/products/i1961466463.html',
                'image_urls': [],
                'specifications': {},
            },
            None,
        )


def test_cleaning_pipeline_keeps_phones_that_mention_their_hardware():
    """A phone whose title lists its own battery or camera is not an accessory."""

    cleaned = VextroCleaningPipeline().process_item(
        {
            'platform': 'Daraz',
            'external_id': '1950000001',
            'model': (
                'Infinix Hot 50 8GB 256GB 5000mAh Battery 50MP Camera '
                'Type-C Dual SIM'
            ),
            'price': '44999',
            'availability': 'In Stock',
            'product_url': 'https://www.daraz.pk/products/i1950000001.html',
            'image_urls': ['https://img.drz.lazcdn.com/hot50.jpg'],
            'specifications': {},
        },
        None,
    )

    assert cleaned['brand'] == 'Infinix'


def _daraz_review_response(body, *, item_id='1961146747'):
    url = (
        'https://my.daraz.pk/pdp/review/getReviewList'
        f'?itemId={item_id}&pageSize=20&filter=0&sort=0&pageNo=1'
    )
    return TextResponse(url=url, body=body, encoding='utf-8')


def test_daraz_recognises_the_anti_bot_page_instead_of_reviews():
    """Daraz serves a WAF challenge with HTTP 200, not an error status."""

    spider = DarazSpider()
    response = _daraz_review_response(
        b'<a id="a-link" href="https://g.alicdn.com/sd/punish/waf_block.html'
        b'?wh_ttid=pc"></a>'
    )

    with pytest.raises(DarazReviewBlockedError):
        list(spider.parse_reviews(response, external_listing_id='1961146747'))

    assert spider.blocked_review_responses == 1
    # One blocked reply is not yet a pattern; reviews keep being requested.
    assert spider.reviews_blocked is False


def test_daraz_stops_requesting_reviews_once_the_api_is_blocked():
    """A blocked API must not produce one failure per listing in a run."""

    spider = DarazSpider()

    for _ in range(spider.MAX_BLOCKED_REVIEW_RESPONSES):
        with pytest.raises(DarazReviewBlockedError):
            list(
                spider.parse_reviews(
                    _daraz_review_response(b'<html>waf_block</html>'),
                    external_listing_id='1961146747',
                )
            )

    assert spider.reviews_blocked is True
    assert spider._build_review_request('1961146747', 5) is None


def test_daraz_review_requests_carry_the_product_page_as_referer():
    spider = DarazSpider()
    request = spider._build_review_request('1961146747', 5)

    assert request is not None
    assert request.headers.get('Referer') == (
        b'https://www.daraz.pk/products/i1961146747.html'
    )


def test_daraz_still_parses_a_normal_review_payload():
    """The block detector must not reject genuine review JSON."""

    spider = DarazSpider()
    response = _daraz_review_response(
        json.dumps({
            'model': {
                'items': [{
                    'reviewRateId': '555',
                    'buyerName': 'Test Buyer',
                    'rating': 5,
                    'reviewContent': 'Great phone.',
                    'boughtDate': '20 Sep 2026',
                    'isPurchased': True,
                    'upVotes': 2,
                }],
                'paging': {'totalPages': 1},
            },
        }).encode('utf-8'),
    )

    batches = list(
        spider.parse_reviews(response, external_listing_id='1961146747')
    )

    assert len(batches) == 1
    assert batches[0]['reviews'][0]['rating'] == 5
    assert spider.blocked_review_responses == 0


def test_a_phone_that_advertises_its_free_charger_is_not_dropped():
    """Marketing copy lists what is in the box; that is not the product."""

    cleaned = VextroCleaningPipeline().process_item(
        {
            'platform': 'Daraz',
            'external_id': '1950000002',
            'model': (
                'Original Vivo Y85 Smartphone | 4GB 64GB | PTA Approved | '
                'FREE Charger Included'
            ),
            'price': '29999',
            'availability': 'In Stock',
            'product_url': 'https://www.daraz.pk/products/i1950000002.html',
            'image_urls': ['https://img.drz.lazcdn.com/y85.jpg'],
            'specifications': {},
        },
        None,
    )

    assert cleaned['brand'] == 'Vivo'


def _robots_failure(item_id='1961146747'):
    """Build the failure Scrapy delivers when robots.txt forbids a URL."""

    request = Request(
        url=(
            'https://my.daraz.pk/pdp/review/getReviewList'
            f'?itemId={item_id}'
        ),
        meta={'external_listing_id': item_id},
    )
    failure = Failure(IgnoreRequest('Forbidden by robots.txt'))
    failure.request = request

    return failure


def test_daraz_records_a_disallowed_review_api_once_per_run():
    """robots.txt forbids the review API, and that will not change.

    Recording it per listing reported 149 failures in one crawl and marked
    the run degraded for a decision the marketplace had already made.
    """

    spider = DarazSpider()

    with pytest.raises(DarazReviewDisallowedError):
        spider.review_fetch_error(_robots_failure())

    assert spider.reviews_blocked is True

    # Every later listing is silent, and no further requests are built.
    assert spider.review_fetch_error(_robots_failure('1961146748')) is None
    assert spider._build_review_request('1961146748', 5) is None


def test_daraz_still_reports_a_genuine_review_fetch_failure():
    spider = DarazSpider()
    request = Request(
        url='https://my.daraz.pk/pdp/review/getReviewList?itemId=1',
        meta={'external_listing_id': '1'},
    )
    failure = Failure(ConnectionRefusedError('connection refused'))
    failure.request = request

    with pytest.raises(DarazReviewFetchError):
        spider.review_fetch_error(failure)

    assert spider.reviews_blocked is False


def test_phones_that_list_bundled_accessories_are_not_dropped():
    """Real Daraz phones a first version of this rule threw away."""

    pipeline = VextroCleaningPipeline()

    for title in (
        'Infinix Note 60 Pro 8GB / 256GB with Free Powerbank',
        'Vivo Y17 Phone | 4GB RAM 128GB Storage | Memory Card Support | '
        'Box Charger & Phone',
        'Vivo Y71 | 6GB Ram | Dual Sim + Memory Card | With Free Gift Box',
    ):
        cleaned = pipeline.process_item(
            {
                'platform': 'Daraz',
                'external_id': '1950000003',
                'model': title,
                'price': '44999',
                'availability': 'In Stock',
                'product_url': 'https://www.daraz.pk/products/i1950000003.html',
                'image_urls': ['https://img.drz.lazcdn.com/phone.jpg'],
                'specifications': {},
            },
            None,
        )

        assert cleaned['brand'] in {'Infinix', 'Vivo'}
