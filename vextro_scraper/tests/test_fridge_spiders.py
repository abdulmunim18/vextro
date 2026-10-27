"""Refrigerators and freezers: their spiders and what the category does not sell."""

import pytest

from vextro_scraper.pipelines import is_out_of_category
from vextro_scraper.scheduler import DEFAULT_SPIDERS
from vextro_scraper.spiders.daraz_spider import DarazFreezerSpider, DarazRefrigeratorSpider
from vextro_scraper.spiders.priceoye_spider import PriceoyeRefrigeratorSpider
from vextro_scraper.spiders.shopify_spider import (
    FriendsHomeRefrigeratorSpider,
    JalalRefrigeratorSpider,
    TelemartRefrigeratorSpider,
)

FRIDGE_SPIDERS = [
    FriendsHomeRefrigeratorSpider,
    JalalRefrigeratorSpider,
    TelemartRefrigeratorSpider,
    PriceoyeRefrigeratorSpider,
    DarazRefrigeratorSpider,
    DarazFreezerSpider,
]


@pytest.mark.parametrize('spider', FRIDGE_SPIDERS)
def test_the_fridge_spiders_file_their_listings_as_fridges(spider):
    assert spider.catalog_category == 'refrigerators'


def test_the_stores_read_their_fridges_and_their_freezers():
    assert FriendsHomeRefrigeratorSpider.collections == ('refrigerators-freezers',)
    assert JalalRefrigeratorSpider.collections == ('refrigerators', 'deep-freezers')
    assert TelemartRefrigeratorSpider.collections == ('refrigerators', 'deep-freezers')
    assert PriceoyeRefrigeratorSpider().start_urls == ['https://priceoye.pk/refrigerators']
    assert DarazRefrigeratorSpider.CATALOG_PATH == '/refrigerators/'
    assert DarazFreezerSpider.CATALOG_PATH == '/freezers/'


def test_the_marketplaces_only_join_catalogued_fridges():
    assert TelemartRefrigeratorSpider.match_only is True
    assert DarazRefrigeratorSpider.match_only is True
    assert DarazFreezerSpider.match_only is True


def test_the_scheduler_crawls_the_marketplaces_after_the_stores():
    order = list(DEFAULT_SPIDERS)

    for marketplace in ('telemart_fridges', 'daraz_fridges', 'daraz_freezers'):
        for store in ('friendshome_fridges', 'jalal_fridges', 'priceoye_fridges'):
            assert order.index(marketplace) > order.index(store)
    assert order[-1] == 'whatmobile_opinions'


@pytest.mark.parametrize(
    'title',
    [
        'Ice Cube Tray with No-Spill Removable Lid',
        'VARIOLINE VISI CHILLER VCS-22 650 LITRES SINGLE DOOR',
        'Homage Water Dispenser HWD-49 Hot and Cold',
        'Refrigerator Door Gasket Replacement Seal',
        'Voltage Stabilizer for Refrigerator 1000VA',
    ],
)
def test_trays_chillers_dispensers_and_parts_are_not_fridges(title):
    assert is_out_of_category('refrigerators', title)


@pytest.mark.parametrize(
    'title',
    [
        'HAIER TWIN INVERTER + REFRIGERATOR Model HRF-538TIFRA',
        # A fridge's dispenser is a feature of the fridge.
        'SAMSUNG REFRIGERATOR SIDEBYSIDE RS50N3913SA WATER DISPENSER DOOR IN DOOR',
        'LG REFRIGERATOR SIDEBYSIDE GR-J259CQBV ICE+DISPENSER',
        'Dawlance DF-500 Inverter Double Door Deep Freezer With Official Warranty',
    ],
)
def test_fridges_and_freezers_are_fridges(title):
    assert not is_out_of_category('refrigerators', title)
