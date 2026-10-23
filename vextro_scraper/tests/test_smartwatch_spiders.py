"""Smart watches: their spiders and what the watch category does not sell."""

import pytest

from vextro_scraper.pipelines import infer_brand, is_out_of_category
from vextro_scraper.scheduler import DEFAULT_SPIDERS
from vextro_scraper.spiders.daraz_spider import DarazSmartwatchSpider
from vextro_scraper.spiders.priceoye_spider import (
    PriceoyeSmartwatchSpider,
    PriceoyeSpider,
)
from vextro_scraper.spiders.shophive_spider import (
    ShophiveSmartwatchSpider,
    ShophiveSpider,
)


@pytest.mark.parametrize(
    'spider',
    [PriceoyeSmartwatchSpider, DarazSmartwatchSpider, ShophiveSmartwatchSpider],
)
def test_the_watch_spiders_file_their_listings_as_smart_watches(spider):
    assert spider.catalog_category == 'smart-watches'
    assert spider.name.endswith('_smartwatches')


def test_priceoye_watches_walk_the_watch_catalogue():
    spider = PriceoyeSmartwatchSpider(
        product_urls='https://priceoye.pk/smart-watches/apple/apple-watch-series-11-46mm',
    )

    assert spider.start_urls == ['https://priceoye.pk/smart-watches']
    assert spider.targeted_urls == [
        'https://priceoye.pk/smart-watches/apple/apple-watch-series-11-46mm',
    ]


def test_priceoye_leaves_unbranded_watch_pages_unrequested():
    watches = PriceoyeSmartwatchSpider()

    assert watches.files_under_unbranded(
        'https://priceoye.pk/smart-watches/assorted/zw10-ladies-smart-watch'
    )
    assert not watches.files_under_unbranded(
        'https://priceoye.pk/smart-watches/apple/apple-watch-series-11-46mm'
    )
    # Phones keep every page.
    assert not PriceoyeSpider().files_under_unbranded(
        'https://priceoye.pk/mobiles/assorted/some-phone'
    )


def test_daraz_watches_only_join_catalogued_watches():
    assert DarazSmartwatchSpider.match_only is True
    assert DarazSmartwatchSpider.CATALOG_PATH == '/smart-watches/'
    assert DarazSmartwatchSpider.custom_settings['DARAZ_REVIEWS_ENABLED'] is False


def test_shophive_watches_read_the_apple_store_and_skip_whoop():
    assert ShophiveSmartwatchSpider.category_paths == ('apple/watch', 'smart-watches')
    assert ShophiveSmartwatchSpider.excluded_paths == ('smart-watches/whoop-bands',)


@pytest.mark.parametrize(
    ('name', 'colour'),
    [
        ('Apple Watch Series 11 46mm Jet Black Aluminium Case With Black Sports Band', 'Jet Black'),
        ('Apple Watch SE Gen 3 40mm Midnight Case With Midnight Sports Band', 'Midnight'),
        ('Apple Watch Ultra 3 GPS + Cellular, 49mm Natural Titanium Case with Neon Green Ocean Band', 'Natural'),
        ('Xiaomi Watch S5', None),
    ],
)
def test_an_apple_watch_colour_is_read_from_its_name(name, colour):
    assert ShophiveSmartwatchSpider.title_colour(name) == colour
    # Phones carry colour options instead.
    assert ShophiveSpider.title_colour(name) is None


def test_the_scheduler_crawls_daraz_watches_after_the_stores_that_catalogue_them():
    order = list(DEFAULT_SPIDERS)

    assert order.index('daraz_smartwatches') > order.index('priceoye_smartwatches')
    assert order.index('daraz_smartwatches') > order.index('shophive_smartwatches')


@pytest.mark.parametrize(
    ('title', 'field', 'expected'),
    [
        # The store's own brand field stands over a title naming another
        # brand's product line.
        ('Zero Pixel Smartwatch', 'Zero', 'Zero'),
        ('Xinji Nothing N1 Smart Watch', 'Xinji', 'Xinji'),
        # Unless the title names another maker outright.
        ('Mibro Watch GS Explorer S', 'Xiaomi', 'Mibro'),
        ('Redmi Watch 6', 'Xiaomi', 'Xiaomi'),
        ('Xiaomi Imilab Imiki SF1E Smart Watch', 'Xiaomi', 'Imilab'),
        ('QTab Y1', 'QMobile', 'QMobile'),
    ],
)
def test_a_store_naming_its_own_goods_is_trusted_for_their_maker(title, field, expected):
    assert infer_brand(title, field, prefer_provided=True) == expected


@pytest.mark.parametrize(
    'title',
    [
        'Ultra Smart Watch 7-in-1 Strap Set with Multiple Color Bands',
        'Silicone Strap for Apple Watch 44mm',
        'Charging Cable for Samsung Galaxy Watch',
        'Tempered Glass Screen Protector for Galaxy Watch 6',
        'Google Fitbit Air Special Edition Screenless Fitness Tracker',
        'WHOOP Life MG Device Health & Fitness Tracker',
        # Copies wearing a brand's name.
        'Samsung Galaxy JS Watch 7 Ultra 47mm AMOLED Smart Watch Super Master Premium',
        'Samsung Galaxy Logo Smart Watch Ultra Round Dial With Samsung Logo',
        # Kept up at an absurd price so nobody buys it.
        'Do Not Purchase Tecno Active Watch 3 Choice Free Gift',
    ],
)
def test_straps_chargers_and_screenless_trackers_are_not_watches(title):
    assert is_out_of_category('smart-watches', title)


@pytest.mark.parametrize(
    'title',
    [
        'Apple Watch Ultra 3 GPS + Cellular 49mm Black Titanium Case with Black Ocean Band',
        'Xiaomi Smart Band 10 Ceramic Edition',
        'Zero Luna Smartwatch with 2 Straps',
        'Oraimo Watch 5 2.01" HD Panda Glass 1ATM Smart Watch (OSW-805)',
    ],
)
def test_watches_and_bands_are_watches(title):
    assert not is_out_of_category('smart-watches', title)
