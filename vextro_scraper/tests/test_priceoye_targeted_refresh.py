"""PriceOye spider: re-reading only the product pages it is given."""

import asyncio
import json

from scrapy.http import HtmlResponse, Request

from vextro_scraper.items import SmartphoneItem
from vextro_scraper.spiders.priceoye_spider import PriceoyeSpider


def collect(async_generator):
    """Drain a spider's async ``start()`` into a list."""

    async def drain():
        return [output async for output in async_generator]

    return asyncio.run(drain())


def test_only_the_given_product_pages_are_requested():
    """The backend re-reads one phone without walking the catalogue."""

    spider = PriceoyeSpider(product_urls=(
        'https://priceoye.pk/mobiles/honor/honor-x9d,'
        'https://example.com/not-priceoye,'
        ' https://priceoye.pk/mobiles/honor/honor-x9d '
    ))
    requests = collect(spider.start())

    assert [request.url for request in requests] == [
        'https://priceoye.pk/mobiles/honor/honor-x9d',
    ]
    assert requests[0].callback == spider.parse_product
    assert requests[0].meta['item']['exact_model_title'] is True
    # A targeted run can never pass for a complete catalogue walk.
    assert spider.full_crawl_completed is False


def test_without_product_pages_the_whole_catalogue_is_crawled():
    requests = collect(PriceoyeSpider().start())

    assert [request.url for request in requests] == [
        'https://priceoye.pk/mobiles',
    ]


def test_a_phone_reached_without_a_listing_page_is_named_from_its_own_page():
    url = 'https://priceoye.pk/mobiles/honor/honor-x9d'
    product_data = {
        'dataSet': {'title': 'Honor X9d', 'warranty': '1 Year'},
        'product_config': {
            'dataPrices': {
                'midnight_black': {'256gb - 12gb ram': [{
                    'product_price': '138,999',
                    'retail_price': '154,999',
                    'product_availability': 'In Stock',
                }]},
            },
        },
    }
    response = HtmlResponse(
        url=url,
        body=(
            '<html><body><script>window.product_data = '
            f'{json.dumps(product_data)};</script></body></html>'
        ),
        encoding='utf-8',
        request=Request(url, meta={'item': SmartphoneItem(platform='PriceOye')}),
    )

    listings = [
        output
        for output in PriceoyeSpider().parse_product(response)
        if isinstance(output, SmartphoneItem)
    ]

    assert len(listings) == 1
    assert listings[0]['model'] == 'Honor X9d'
    assert listings[0]['color'] == 'Midnight Black'
    assert listings[0]['price'] == 138999
    assert listings[0]['original_price'] == 154999
    assert listings[0]['warranty'] == '1 Year Warranty'
