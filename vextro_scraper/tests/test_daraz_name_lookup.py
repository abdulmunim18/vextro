"""Daraz spider: finding a phone by name when its listings never show it."""

import asyncio
import json

from scrapy.http import Request, TextResponse

from vextro_scraper.items import SmartphoneItem
from vextro_scraper.spiders.daraz_spider import DarazSpider


def collect(async_generator):
    async def drain():
        return [output async for output in async_generator]

    return asyncio.run(drain())


def search_response(spider, term, item_ids, *, total=2000):
    return TextResponse(
        url=spider.search_url(term),
        encoding='utf-8',
        body=json.dumps({
            'mods': {
                'listItems': [
                    {
                        'itemId': item_id,
                        'name': f'{term} listing {item_id}',
                        'price': '41999',
                        'inStock': True,
                        'sellerName': 'MOBILE INN',
                    }
                    for item_id in item_ids
                ],
                'filter': {'filterItems': [
                    {'name': 'brand', 'options': [{'value': 'samsung'}]},
                ]},
            },
            'mainInfo': {'page': 1, 'pageSize': 40, 'totalResults': total},
        }).encode('utf-8'),
    )


def test_a_phone_is_searched_inside_the_smartphone_category():
    """The category search is open to crawlers; the site-wide one is not."""

    assert DarazSpider.search_url('Dcode Cygnal Prime') == (
        'https://www.daraz.pk/smartphones/?ajax=true&q=Dcode+Cygnal+Prime'
    )


def test_given_names_only_those_phones_are_looked_up():
    """How the backend refreshes one product: no listing walk at all."""

    spider = DarazSpider(search_terms='Dcode Cygnal Prime| Honor X9d |ab')
    requests = collect(spider.start())

    assert [request.url for request in requests] == [
        spider.search_url('Dcode Cygnal Prime'),
        spider.search_url('Honor X9d'),
    ]
    assert requests[0].cb_kwargs == {'search_term': 'Dcode Cygnal Prime'}


def test_a_lookup_yields_its_results_and_starts_no_walk():
    spider = DarazSpider()
    outputs = list(spider.parse(
        search_response(spider, 'Dcode Cygnal Prime', [501, 502]),
        search_term='Dcode Cygnal Prime',
    ))

    assert [
        output['external_id']
        for output in outputs
        if isinstance(output, SmartphoneItem)
    ] == ['501', '502']
    # No next page and no brand listings: one page answers one phone.
    assert [output for output in outputs if isinstance(output, Request)] == []


def test_an_item_a_lookup_found_first_does_not_end_a_listing_walk_early():
    """A walk has run dry only when the walks themselves return nothing new."""

    spider = DarazSpider()
    list(spider.parse(
        search_response(spider, 'Dcode Cygnal Prime', [501, 502]),
        search_term='Dcode Cygnal Prime',
    ))

    walk_page = TextResponse(
        url='https://www.daraz.pk/smartphones/?ajax=true&page=2',
        encoding='utf-8',
        body=search_response(spider, 'x', [501, 502]).body,
    )
    outputs = list(spider.parse(walk_page))
    items = [o for o in outputs if isinstance(o, SmartphoneItem)]
    follow_ups = [o for o in outputs if isinstance(o, Request)]

    # Already captured by the lookup, so not delivered twice...
    assert items == []
    # ...but new to the walk, so the walk carries on.
    assert follow_ups and follow_ups[-1].cb_kwargs['stale_pages'] == 0
