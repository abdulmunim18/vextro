"""Shophive spider: offers read from the store's own catalogue feed.

The fixture is a real feed response cut down to twelve phones, one for
every case the spider has to get right.
"""

import asyncio
import json
from pathlib import Path

import pytest
from scrapy.http import Request, TextResponse

from vextro_scraper.pipelines import VextroCleaningPipeline
from vextro_scraper.spiders.shophive_spider import (
    CATEGORY_PATHS,
    GRAPHQL_URL,
    ShophiveFeedError,
    ShophiveSpider,
    colour_image,
    normalize_warranty,
    parse_name,
    tidy_colour,
)


FIXTURE = Path(__file__).parent / 'fixtures' / 'shophive_products.json'


def feed_response(body):
    return TextResponse(
        url=GRAPHQL_URL,
        body=json.dumps(body).encode('utf-8'),
        encoding='utf-8',
    )


def fixture_products():
    return json.loads(FIXTURE.read_text(encoding='utf-8'))


def products_page(items, *, total=None, pages=1):
    return {
        'data': {
            'products': {
                'total_count': len(items) if total is None else total,
                'page_info': {'current_page': 1, 'total_pages': pages},
                'items': items,
            }
        }
    }


def collect(async_generator):
    async def drain():
        return [output async for output in async_generator]

    return asyncio.run(drain())


def crawl_fixture(spider=None, category='mobile-phones'):
    spider = spider or ShophiveSpider()
    outputs = list(spider.parse_products(
        feed_response(fixture_products()),
        product_filter={'category_uid': {'eq': 'Mjc2Mg=='}},
        page=1,
        category=category,
    ))

    return spider, [output for output in outputs if not isinstance(output, Request)]


def offers_of(items, sku):
    return [
        item for item in items
        if str(item['external_id']).split('-')[0] == sku
    ]


# --------------------------------------------------------------------------
# Names
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('name', 'expected'),
    [
        ('Samsung Galaxy A17 6GB 128GB', ('Samsung Galaxy A17', 6, 128, False)),
        ('Vivo Y05e 4GB +64GB', ('Vivo Y05e', 4, 64, False)),
        ('Samsung Galaxy Z Fold 8 Ultra 12GB 1TB', ('Samsung Galaxy Z Fold 8 Ultra', 12, 1024, False)),
        ('Oppo Reno 16F 5G 8GB 256GB', ('Oppo Reno 16F 5G', 8, 256, False)),
        ('Apple iPhone 17 Pro Max 512GB PTA Approved', ('Apple iPhone 17 Pro Max', None, 512, True)),
        ('Apple iPhone 18 Pro Max 2TB PTA Approved', ('Apple iPhone 18 Pro Max', None, 2048, True)),
        ('Itel A50C 2GB 64GB (Special Edition)', ('Itel A50C (Special Edition)', 2, 64, False)),
        ('Nokia 5310 2G (2024)', ('Nokia 5310 2G (2024)', None, None, False)),
        ('Nokia 105 Power', ('Nokia 105 Power', None, None, False)),
    ],
)
def test_the_memory_and_pta_wording_come_off_the_model_name(name, expected):
    assert parse_name(name) == expected


@pytest.mark.parametrize(
    ('title', 'expected'),
    [
        (' Night Pulse', 'Night Pulse'),
        ('Pearl white', 'Pearl White'),
        ('BLACK', 'Black'),
        ('Awesome Icyblue', 'Awesome Icyblue'),
        ('  ', None),
    ],
)
def test_colour_names_are_spelled_one_way(title, expected):
    assert tidy_colour(title) == expected


@pytest.mark.parametrize(
    ('stated', 'expected'),
    [
        ('1 Year Manufacturer', '1 Year Manufacturer Warranty'),
        ('Manufacturer Warranty', 'Manufacturer Warranty'),
        ('Check at Delivery', 'Check at Delivery'),
        ('Not Available', None),
        (None, None),
    ],
)
def test_the_warranty_is_kept_as_the_shop_states_it(stated, expected):
    assert normalize_warranty(stated) == expected


def test_a_colours_photo_is_found_by_the_files_name():
    gallery = [
        'https://www.shophive.com/media/s/a/samsung_galaxy_37_5g_white.jpg',
        'https://www.shophive.com/media/s/a/samsung_galaxy_a37_5g_awesome_charcol.jpg',
        'https://www.shophive.com/media/s/a/samsung_galaxy_a37_awesome_lavender.jpg',
        'https://www.shophive.com/media/s/a/samusng_a37_awesome_graygreen.jpg',
    ]

    assert colour_image('Awesome Charcol', gallery) == gallery[1]
    # "awesome" is on three files and says nothing; "white" is on one.
    assert colour_image('Awesome White', gallery) == gallery[0]
    assert colour_image('Awesome Graygreen', gallery) == gallery[3]


def test_no_photo_is_guessed_when_none_clearly_shows_the_colour():
    gallery = [
        'https://www.shophive.com/media/x/front.jpg',
        'https://www.shophive.com/media/x/back.jpg',
    ]

    assert colour_image('Midnight Blue', gallery) is None
    assert colour_image('Black', gallery[:1]) is None


# --------------------------------------------------------------------------
# Offers
# --------------------------------------------------------------------------


def test_each_colour_of_a_phone_is_an_offer_of_its_own():
    _, items = crawl_fixture()
    offers = offers_of(items, 'U71107')

    assert [offer['color'] for offer in offers] == [
        'Awesome Graygreen',
        'Awesome White',
        'Awesome Lavender',
        'Awesome Charcol',
    ]
    assert len({offer['external_id'] for offer in offers}) == 4

    first = offers[0]
    assert first['platform'] == 'Shophive'
    assert first['model'] == 'Samsung Galaxy A37 5G'
    assert first['brand'] == 'Samsung'
    assert first['exact_model_title'] is True
    assert first['sku'] is None
    assert first['product_url'] == (
        'https://www.shophive.com/samsung-galaxy-a37-5g-8gb-256gb/'
    )
    assert first['availability'] == 'In Stock'
    assert first['warranty'] == '1 Year Manufacturer Warranty'
    assert first['specifications']['ram'] == '8GB'
    assert first['specifications']['storage_capacity'] == '256GB'
    assert first['image_urls']


def test_a_colour_that_costs_more_carries_its_own_price():
    _, items = crawl_fixture()
    prices = {
        offer['color']: (offer['price'], offer['original_price'])
        for offer in offers_of(items, 'U71107')
    }

    assert prices['Awesome White'] == (137999.0, 164999.0)
    assert prices['Awesome Charcol'] == (140999.0, 167999.0)


def test_each_colour_leads_with_its_own_photo():
    _, items = crawl_fixture()
    charcol = next(
        offer for offer in offers_of(items, 'U71107')
        if offer['color'] == 'Awesome Charcol'
    )

    assert 'awesome_charcol' in charcol['image_urls'][0]
    assert len(charcol['image_urls']) == len(set(charcol['image_urls']))


def test_the_name_decides_the_memory_when_the_table_disagrees():
    """The Galaxy A17 "6GB" page's specification table says 4GB."""

    _, items = crawl_fixture()
    offer = offers_of(items, 'U68816')[0]

    assert offer['model'] == 'Samsung Galaxy A17'
    assert offer['specifications']['ram'] == '6GB'
    assert offer['specifications']['storage_capacity'] == '128GB'
    assert offer['variant'] == '6GB RAM / 128GB'


def test_a_phone_listed_at_zero_is_not_an_offer():
    spider, items = crawl_fixture()

    assert offers_of(items, 'U67696') == []   # Galaxy Z Flip 7, coming soon
    assert offers_of(items, 'U66558') == []   # photography kit, Rs 0
    assert offers_of(items, 'U72356') == []   # Z Fold 8 Ultra 1TB, Rs 0
    assert spider.unpriced_count == 3
    assert all(item['price'] > 0 for item in items)


def test_a_priced_phone_that_is_coming_soon_is_kept_but_unavailable():
    _, items = crawl_fixture()
    offers = offers_of(items, 'U72306')

    assert offers
    assert all(offer['price'] == 249999.0 for offer in offers)
    assert all(offer['availability'] == 'Out of Stock' for offer in offers)


def test_a_phone_without_colour_options_is_one_offer_without_a_colour():
    _, items = crawl_fixture()
    offers = offers_of(items, 'U72007')

    assert len(offers) == 1
    assert offers[0]['external_id'] == 'U72007'
    assert offers[0]['color'] is None
    assert offers[0]['model'] == 'Xiaomi 17T'
    assert offers[0]['brand'] == 'Xiaomi'


def test_an_iphone_states_storage_but_no_ram():
    _, items = crawl_fixture()
    offer = offers_of(items, 'U68545')[0]

    assert offer['model'] == 'Apple iPhone 17 Pro Max'
    assert offer['specifications']['storage_capacity'] == '512GB'
    assert 'ram' not in offer['specifications']
    assert offer['specifications']['pta_status'] == 'PTA Approved'


def test_a_feature_phone_has_no_memory_figures_at_all():
    _, items = crawl_fixture()
    offer = offers_of(items, 'U68962')[0]

    assert offer['model'] == 'Nokia 125 (2024)'
    assert 'ram' not in offer['specifications']
    assert 'storage_capacity' not in offer['specifications']
    assert offer['variant'] is None


def test_every_offer_passes_the_cleaning_step_as_a_phone():
    _, items = crawl_fixture()
    pipeline = VextroCleaningPipeline()

    cleaned = [pipeline.process_item(item, None) for item in items]

    assert len(cleaned) == len(items)
    assert all(item['brand'] for item in cleaned)
    assert all(item['image_urls'] for item in cleaned)
    assert {item['is_available'] for item in cleaned} == {True, False}


# --------------------------------------------------------------------------
# Walking the feed
# --------------------------------------------------------------------------


def test_a_full_crawl_first_asks_for_the_two_phone_categories():
    requests = collect(ShophiveSpider().start())

    assert len(requests) == 1
    assert requests[0].url == GRAPHQL_URL
    assert requests[0].method == 'POST'
    assert json.loads(requests[0].body)['variables'] == {
        'paths': list(CATEGORY_PATHS),
    }


def test_each_category_is_opened_by_the_identifier_the_feed_gives():
    spider = ShophiveSpider()
    requests = list(spider.parse_categories(feed_response({
        'data': {'categoryList': [
            {'uid': 'Mjc2Mg==', 'url_path': 'mobile-phones', 'product_count': 126},
            {'uid': 'MTgwMA==', 'url_path': 'apple/iphone', 'product_count': 29},
        ]},
    })))

    assert [
        json.loads(request.body)['variables']['filter'] for request in requests
    ] == [
        {'category_uid': {'eq': 'Mjc2Mg=='}},
        {'category_uid': {'eq': 'MTgwMA=='}},
    ]
    assert [request.cb_kwargs['category'] for request in requests] == [
        'mobile-phones',
        'apple/iphone',
    ]
    assert spider.failed_page_count == 0


def test_a_category_is_followed_to_its_last_page():
    spider = ShophiveSpider()
    items = fixture_products()['data']['products']['items']
    outputs = list(spider.parse_products(
        feed_response(products_page(items, total=126, pages=3)),
        product_filter={'category_uid': {'eq': 'Mjc2Mg=='}},
        page=1,
        category='mobile-phones',
    ))
    follow_ups = [output for output in outputs if isinstance(output, Request)]

    assert len(follow_ups) == 1
    assert json.loads(follow_ups[0].body)['variables']['page'] == 2
    assert 'mobile-phones' not in spider.finished_categories


def test_a_run_is_complete_only_when_the_shops_own_count_is_met():
    spider = ShophiveSpider()
    items = fixture_products()['data']['products']['items']

    def read(category, entries, total):
        list(spider.parse_products(
            feed_response(products_page(entries, total=total)),
            product_filter={'category_uid': {'eq': 'x'}},
            page=1,
            category=category,
        ))

    read('mobile-phones', items[:9], 9)
    assert spider.full_crawl_completed is False   # iPhones not read yet

    read('apple/iphone', items[9:], 4)            # the feed promised 4, sent 3
    assert spider.full_crawl_completed is False

    read('apple/iphone', items[9:], 3)
    assert spider.full_crawl_completed is True


def test_a_missing_category_stops_the_run_counting_as_complete():
    spider = ShophiveSpider()
    requests = list(spider.parse_categories(feed_response({
        'data': {'categoryList': [
            {'uid': 'Mjc2Mg==', 'url_path': 'mobile-phones', 'product_count': 126},
        ]},
    })))

    assert len(requests) == 1
    assert spider.failed_page_count == 1
    assert spider.full_crawl_completed is False


def test_an_error_from_the_feed_fails_the_page_loudly():
    spider = ShophiveSpider()

    with pytest.raises(ShophiveFeedError):
        list(spider.parse_products(
            feed_response({'errors': [{'message': 'Internal server error'}]}),
            product_filter={},
            page=1,
            category='mobile-phones',
        ))

    assert spider.failed_page_count == 1
    assert spider.full_crawl_completed is False


def test_a_phone_filed_in_both_categories_is_emitted_once():
    spider = ShophiveSpider()
    _, first = crawl_fixture(spider, 'mobile-phones')
    _, second = crawl_fixture(spider, 'apple/iphone')

    assert first
    assert second == []


# --------------------------------------------------------------------------
# Refreshing chosen phones
# --------------------------------------------------------------------------


def test_chosen_pages_are_asked_for_by_their_key_and_nothing_else():
    spider = ShophiveSpider(product_urls=(
        'https://www.shophive.com/samsung-galaxy-a17-6gb-128gb/,'
        'https://www.shophive.com/xiaomi-17t-12gb-512gb/,'
        'https://www.shophive.com/samsung-galaxy-a17-6gb-128gb/,'
        'https://priceoye.pk/mobiles/samsung/samsung-galaxy-a17,'
        'https://www.shophive.com/mobile-phones/samsung'
    ))
    requests = collect(spider.start())

    assert len(requests) == 1
    assert json.loads(requests[0].body)['variables']['filter'] == {
        'url_key': {'in': [
            'samsung-galaxy-a17-6gb-128gb',
            'xiaomi-17t-12gb-512gb',
        ]},
    }


def test_a_refresh_of_chosen_pages_never_counts_as_a_full_crawl():
    spider = ShophiveSpider(
        product_urls='https://www.shophive.com/samsung-galaxy-a17-6gb-128gb/',
    )
    outputs = list(spider.parse_products(
        feed_response(fixture_products()),
        product_filter={'url_key': {'in': ['samsung-galaxy-a17-6gb-128gb']}},
        page=1,
        category=None,
    ))

    assert outputs
    assert spider.full_crawl_completed is False
