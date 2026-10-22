"""Tablets: their spiders, their category rules and Daraz's match-only mode."""

from types import SimpleNamespace

import pytest

from test_api_ingestion_pipeline import (
    FakeResponse,
    RecordingSession,
    build_clean_item,
    build_pipeline,
)
from vextro_scraper.pipelines import (
    NonSmartphoneItemError,
    NotInCatalogueError,
    VextroApiIngestionPipeline,
    VextroCleaningPipeline,
    is_out_of_category,
)
from vextro_scraper.scheduler import DEFAULT_SPIDERS
from vextro_scraper.spiders.daraz_spider import DarazSpider, DarazTabletSpider
from vextro_scraper.spiders.priceoye_spider import PriceoyeSpider, PriceoyeTabletSpider
from vextro_scraper.spiders.shophive_spider import (
    ShophiveSpider,
    ShophiveTabletSpider,
    parse_name,
    tidy_colour,
)


# --------------------------------------------------------------------------
# The spiders
# --------------------------------------------------------------------------


@pytest.mark.parametrize('spider', [PriceoyeTabletSpider, DarazTabletSpider, ShophiveTabletSpider])
def test_the_tablet_spiders_file_their_listings_as_tablets(spider):
    assert spider.catalog_category == 'tablets'
    assert spider.name.endswith('_tablets')


def test_priceoye_tablets_walk_the_tablet_catalogue():
    spider = PriceoyeTabletSpider(
        product_urls=(
            'https://priceoye.pk/tablets/apple/apple-ipad-11-a16,'
            'https://priceoye.pk/mobiles/apple/iphone-17'
        ),
    )

    assert spider.start_urls == ['https://priceoye.pk/tablets']
    assert spider.catalog_path == '/tablets'
    # A phone page is never handed to the tablet spider.
    assert spider.targeted_urls == ['https://priceoye.pk/tablets/apple/apple-ipad-11-a16']
    assert PriceoyeSpider.catalog_path == '/mobiles'


def test_priceoye_tablets_follow_their_own_brand_listings():
    spider = PriceoyeTabletSpider()
    response = SimpleNamespace(
        text='{"brand_filter_bar": {"filters": {"brands": {"options": {"apple": 1}}}}}',
        follow=lambda url, **kwargs: url,
    )

    assert list(spider.brand_catalog_requests(response)) == ['/tablets/apple']


def test_daraz_tablets_only_join_catalogued_tablets_and_skip_reviews():
    assert DarazTabletSpider.match_only is True
    assert DarazTabletSpider.CATALOG_PATH == '/tablets/'
    assert DarazTabletSpider.search_url('iPad Air') == (
        'https://www.daraz.pk/tablets/?ajax=true&q=iPad+Air'
    )
    assert DarazTabletSpider.custom_settings['DARAZ_REVIEWS_ENABLED'] is False
    assert not getattr(DarazSpider, 'match_only', False)


def test_shophive_tablets_read_the_ipad_store_and_skip_drawing_pads():
    assert ShophiveTabletSpider.category_paths == ('apple/ipad', 'tablets')
    assert 'tablets/wacom' in ShophiveTabletSpider.excluded_paths
    assert ShophiveSpider.excluded_paths == ()

    spider = ShophiveTabletSpider()
    spider.category_sizes = {'tablets': 3}
    wacom = {
        'sku': 'W1',
        'name': 'Wacom Intuos Pro Medium',
        'categories': [{'url_path': 'tablets'}, {'url_path': 'tablets/wacom'}],
    }
    tab = {
        'sku': 'T1',
        'name': 'Xiaomi Pad 7 8GB 256GB',
        'categories': [{'url_path': 'tablets'}, {'url_path': 'tablets/xiaomi-mi'}],
    }
    emitted = []
    spider.product_items = lambda product: emitted.append(product['sku']) or []
    spider.feed_data = lambda response: {
        'products': {
            'items': [wacom, tab],
            'total_count': 2,
            'page_info': {'total_pages': 1},
        },
    }

    list(spider.parse_products(None, 'uid', 1, 'tablets'))

    assert emitted == ['T1']
    # Both still count as received, so the crawl can be judged complete.
    assert spider.received_skus['tablets'] == {'W1', 'T1'}


@pytest.mark.parametrize(
    ('option', 'expected'),
    [
        ('Space Grey Mh5U4', 'Space Grey'),
        ('Starlight Mh5W4', 'Starlight'),
        ('Coralred', 'Coralred'),
        ('Titanium Black', 'Titanium Black'),
    ],
)
def test_an_ipad_colour_loses_the_part_number_shophive_appends(option, expected):
    assert tidy_colour(option) == expected


def test_a_slash_between_ram_and_storage_is_read():
    assert parse_name('Samsung Galaxy Tab S11 Ultra 14.6" 12GB/256GB Wifi')[1:3] == (12, 256)


def test_the_scheduler_crawls_daraz_tablets_after_the_stores_that_catalogue_them():
    order = list(DEFAULT_SPIDERS)

    assert order.index('daraz_tablets') > order.index('priceoye_tablets')
    assert order.index('daraz_tablets') > order.index('shophive_tablets')
    assert order[-1] == 'whatmobile_opinions'


# --------------------------------------------------------------------------
# What the tablet category does not sell
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    'title',
    [
        'XP-Pen Deco 640 Drawing Tablet',
        'Veikk Studio VK2200 Pro Creative Pen Display Tablet',
        'reMarkable Paper Pro Move 7.3" Digital Paper Tablet With Color Display',
        '12 Inchs Colorful LCD Writing Tablet for Kids',
        'Samsung Galaxy Tab S11 11" 12GB/128GB Wifi-With Keyboard',
        'Amaze A275 Pro Active Stylus Pen For iPad',
        'ESR iPad Air 11 M2 / M3 UltraFit Armorite Screen Protector 2 Packs',
    ],
)
def test_drawing_pads_and_accessories_are_not_tablets(title):
    assert is_out_of_category('tablets', title)


@pytest.mark.parametrize(
    'title',
    [
        'Apple iPad Air 13" M4 2026 8th Gen 128GB Wi-Fi',
        'Lenovo Tab M8 Gen 4 2GB 32GB',
        'Amazon Fire HD 8 Kids Pro Tablet Bright 8" HD Screen (2024)',
        'Samsung Galaxy Tab A11 8.7" 4GB 64GB WiFi SM-X133',
    ],
)
def test_tablets_are_tablets(title):
    assert not is_out_of_category('tablets', title)


def test_the_cleaning_pipeline_drops_what_a_tablet_listing_is_not():
    item = {
        **build_clean_item(),
        'model': 'XP-Pen Deco 640 Drawing Tablet',
        'specifications': {},
    }

    with pytest.raises(NonSmartphoneItemError, match='tablets'):
        VextroCleaningPipeline().process_item(item, SimpleNamespace(catalog_category='tablets'))


# --------------------------------------------------------------------------
# Match-only delivery
# --------------------------------------------------------------------------


def match_only_item():
    return {
        **build_clean_item(),
        'model': 'Samsung Galaxy Tab S10 FE 8GB 128GB WiFi',
        'category': 'tablets',
        'match_only': True,
    }


def test_a_match_only_listing_asks_the_backend_not_to_add_a_product():
    payload = VextroApiIngestionPipeline._build_match_payload(match_only_item())

    assert payload['allow_new_product'] is False
    assert 'allow_new_product' not in VextroApiIngestionPipeline._build_match_payload(
        build_clean_item()
    )


def test_the_cleaning_pipeline_marks_a_match_only_spiders_listings():
    spider = SimpleNamespace(catalog_category='tablets', match_only=True)
    item = {**build_clean_item(), 'model': 'Samsung Galaxy Tab S10 FE 8GB 128GB WiFi'}

    assert VextroCleaningPipeline().process_item(item, spider)['match_only'] is True


def test_a_match_only_listing_resembling_nothing_is_not_queued():
    session = RecordingSession(
        FakeResponse(200, {
            'matched': False,
            'confidence': 0,
            'product_variant_id': None,
            'reason': 'No candidate products found.',
        }),
    )

    with pytest.raises(NotInCatalogueError):
        build_pipeline(session).process_item(match_only_item(), spider=None)

    assert [call[0] for call in session.calls] == [
        'http://backend.test/api/v1/internal/acquisition/resolve-product',
    ]


def test_a_match_only_listing_close_to_a_tablet_is_queued_for_review():
    session = RecordingSession(
        FakeResponse(200, {
            'matched': False,
            'confidence': 80,
            'product_variant_id': None,
            'suggested_product_variant_id': 12,
            'reason': 'Below the automatic threshold.',
        }),
        FakeResponse(201, {'id': 5, 'status': 'pending'}),
    )

    with pytest.raises(Exception) as raised:
        build_pipeline(session).process_item(match_only_item(), spider=None)

    assert not isinstance(raised.value, NotInCatalogueError)
    assert session.calls[1][0].endswith('/pending-matches')
    # The queue's match request is a plain one the backend accepts.
    assert 'allow_new_product' not in session.calls[1][1]['json']['match_payload']


def test_a_match_only_listing_with_only_a_distant_guess_is_not_queued():
    session = RecordingSession(
        FakeResponse(200, {
            'matched': False,
            'confidence': 52,
            'product_variant_id': None,
            'suggested_product_variant_id': 12,
            'reason': 'Below the automatic threshold.',
        }),
    )

    with pytest.raises(NotInCatalogueError):
        build_pipeline(session).process_item(match_only_item(), spider=None)

    assert len(session.calls) == 1


def test_turned_away_listings_are_rejections_not_failures():
    assert NotInCatalogueError.outcome == 'rejected'
    assert NonSmartphoneItemError.outcome == 'rejected'
