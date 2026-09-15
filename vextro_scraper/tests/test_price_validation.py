import json
import logging
from math import inf, nan

import pytest
from scrapy.http import HtmlResponse, Request, TextResponse

from vextro_scraper.pipelines import (
    InvalidMarketplacePriceError,
    VextroCleaningPipeline,
    normalize_marketplace_price,
)
from vextro_scraper.spiders.daraz_spider import DarazSpider
from vextro_scraper.spiders.priceoye_spider import PriceoyeSpider


@pytest.mark.parametrize(
    ('raw_price', 'expected'),
    [
        (119999, 119999.0),
        ('119999', 119999.0),
        ('119,999', 119999.0),
        ('Rs. 119,999', 119999.0),
        ('Rs72,999', 72999.0),
        ('PKR 119,999', 119999.0),
        ('119,999.50', 119999.50),
    ],
)
def test_marketplace_price_normalizer_accepts_supported_formats(
    raw_price,
    expected,
):
    assert normalize_marketplace_price(raw_price) == expected


@pytest.mark.parametrize(
    'raw_price',
    [
        None,
        '',
        ' ',
        'N/A',
        'Call for Price',
        'Contact Seller',
        'Rs.',
        'Free',
        'abc123',
        0,
        0.0,
        -1,
        -999,
        nan,
        inf,
        -inf,
    ],
)
def test_marketplace_price_normalizer_rejects_invalid_values(raw_price):
    with pytest.raises(ValueError):
        normalize_marketplace_price(raw_price)


def test_cleaning_pipeline_logs_context_and_drops_invalid_price(caplog):
    item = {
        'platform': 'Daraz',
        'external_id': 'bad-price-123',
        'model': 'Example Phone',
        'price': 'Call for Price',
        'product_url': 'https://www.daraz.pk/products/bad-price.html',
    }

    with caplog.at_level(logging.WARNING):
        with pytest.raises(InvalidMarketplacePriceError):
            VextroCleaningPipeline().process_item(item, spider=None)

    assert 'reason=invalid_price' in caplog.text
    assert 'platform=daraz' in caplog.text
    assert 'external_id=bad-price-123' in caplog.text
    assert "raw_price='Call for Price'" in caplog.text


def test_missing_daraz_price_is_rejected_before_delivery():
    spider = DarazSpider()
    response = TextResponse(
        url='https://www.daraz.pk/smartphones/?ajax=true',
        body=json.dumps({
            'mods': {
                'listItems': [{
                    'itemId': 'daraz-missing-price',
                    'productUrl': '//www.daraz.pk/products/missing.html',
                    'name': 'Samsung Missing Price Phone',
                    'inStock': True,
                }],
            },
            'mainInfo': {
                'page': '1',
                'totalResults': '1',
                'pageSize': '40',
            },
        }).encode('utf-8'),
    )

    item = list(spider.parse(response))[0]
    assert item['price'] is None

    with pytest.raises(InvalidMarketplacePriceError):
        VextroCleaningPipeline().process_item(item, spider)


def test_missing_priceoye_price_is_rejected_before_delivery():
    spider = PriceoyeSpider()
    request = Request(
        url='https://priceoye.pk/mobiles/test/missing-price',
        meta={'item': {
            'platform': 'PriceOye',
            'external_id': 'priceoye-missing-price',
            'model': 'PriceOye Missing Price Phone',
            'price': None,
            'product_url': '/mobiles/test/missing-price',
        }},
    )
    response = HtmlResponse(
        url=request.url,
        request=request,
        encoding='utf-8',
        body=b'<html><body><div>Unavailable</div></body></html>',
    )

    item = list(spider.parse_product(response))[0]
    assert item['price'] is None

    with pytest.raises(InvalidMarketplacePriceError):
        VextroCleaningPipeline().process_item(item, spider)
