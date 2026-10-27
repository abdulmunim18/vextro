"""Televisions: their spiders and what the TV category does not sell."""

import pytest

from vextro_scraper.pipelines import is_out_of_category
from vextro_scraper.scheduler import DEFAULT_SPIDERS
from vextro_scraper.spiders.daraz_spider import DarazTelevisionSpider
from vextro_scraper.spiders.priceoye_spider import PriceoyeTelevisionSpider
from vextro_scraper.spiders.shophive_spider import ShophiveTelevisionSpider
from vextro_scraper.spiders.shopify_spider import (
    FriendsHomeTelevisionSpider,
    JalalTelevisionSpider,
    TelemartTelevisionSpider,
)

TV_SPIDERS = [
    FriendsHomeTelevisionSpider,
    JalalTelevisionSpider,
    TelemartTelevisionSpider,
    PriceoyeTelevisionSpider,
    ShophiveTelevisionSpider,
    DarazTelevisionSpider,
]


@pytest.mark.parametrize('spider', TV_SPIDERS)
def test_the_tv_spiders_file_their_listings_as_tvs(spider):
    assert spider.catalog_category == 'televisions'
    assert spider.name.endswith('_tvs')


def test_the_stores_read_their_own_tv_collections():
    assert FriendsHomeTelevisionSpider.collections == ('led-tv',)
    assert JalalTelevisionSpider.collections == ('led-tv',)
    # Telemart spreads its TVs over four collections, none holding all.
    assert set(TelemartTelevisionSpider.collections) == {
        'tv-video', 'smart-leds', '4k-ultra-leds', 'led-tvs',
    }
    assert PriceoyeTelevisionSpider().start_urls == ['https://priceoye.pk/led-tv']
    assert ShophiveTelevisionSpider.category_paths == ('tv/led',)
    assert DarazTelevisionSpider.CATALOG_PATH == '/televisions/'


def test_the_marketplaces_only_join_catalogued_tvs():
    assert TelemartTelevisionSpider.match_only is True
    assert DarazTelevisionSpider.match_only is True


def test_the_scheduler_crawls_the_marketplaces_after_the_stores():
    order = list(DEFAULT_SPIDERS)

    for marketplace in ('telemart_tvs', 'daraz_tvs'):
        for store in ('friendshome_tvs', 'jalal_tvs', 'priceoye_tvs', 'shophive_tvs'):
            assert order.index(marketplace) > order.index(store)
    assert order[-1] == 'whatmobile_opinions'


@pytest.mark.parametrize(
    'title',
    [
        'Xiaomi TV Stick 4K 2nd Gen Streaming Media Player',
        'Xiaomi Mi Tv Box S 3rd Generation',
        'G10S Voice Control Air Mouse | 2.4GHz Wireless Remote with USB Receiver',
        '3M HDMI to HDMI Cable - High-Performance HDMI Cable',
        'ViewSonic ViewBoard IFP6534 65" 4K Interactive Display EDLA Certified',
        'Viewsonic CDE4314-2C 43" 4K Commercial Display with Pro AV Integration',
        'Universal TV Wall Mount Bracket 32 to 65 Inch',
        'AOC 16T3FE 15.6" FHD IPS Portable LED',
        'Lattafa EDP Ejazi 100 ml Perfume For Men',
    ],
)
def test_sticks_boxes_mounts_and_displays_are_not_tvs(title):
    assert is_out_of_category('televisions', title)


@pytest.mark.parametrize(
    'title',
    [
        'TCL 55 INCH SMART & 4K QD MINILED TV Model 55C6K',
        'SAMSUNG LED 55" UA55U8000FUSMM 4K UHD SMART TV C/O',
        # What comes after "with" is the offer.
        'Haier H55S81EUX 55 Inch 4K QLED Google TV With Official Warranty and Wall Mount',
    ],
)
def test_tvs_are_tvs(title):
    assert not is_out_of_category('televisions', title)
