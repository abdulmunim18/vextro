"""Air conditioners: their spiders and what the AC category does not sell."""

import pytest

from vextro_scraper.pipelines import BRAND_PLACEHOLDERS, is_out_of_category
from vextro_scraper.scheduler import DEFAULT_SPIDERS
from vextro_scraper.spiders.daraz_spider import DarazAirConditionerSpider
from vextro_scraper.spiders.priceoye_spider import PriceoyeAirConditionerSpider
from vextro_scraper.spiders.shopify_spider import (
    FriendsHomeAirConditionerSpider,
    JalalAirConditionerSpider,
    TelemartAirConditionerSpider,
)

AC_SPIDERS = [
    FriendsHomeAirConditionerSpider,
    JalalAirConditionerSpider,
    TelemartAirConditionerSpider,
    PriceoyeAirConditionerSpider,
    DarazAirConditionerSpider,
]


@pytest.mark.parametrize('spider', AC_SPIDERS)
def test_the_ac_spiders_file_their_listings_as_acs(spider):
    assert spider.catalog_category == 'air-conditioners'
    assert spider.name.endswith('_acs')


def test_the_stores_read_their_own_ac_collections():
    assert FriendsHomeAirConditionerSpider.collections == ('air-conditioners-ac-in-pakistan',)
    assert JalalAirConditionerSpider.collections == ('air-conditioners',)
    assert TelemartAirConditionerSpider.collections == ('air-conditioners',)
    assert PriceoyeAirConditionerSpider().start_urls == ['https://priceoye.pk/ac']
    assert DarazAirConditionerSpider.CATALOG_PATH == '/air-conditioners/'


def test_jalals_vendor_is_not_taken_for_a_brand():
    assert FriendsHomeAirConditionerSpider.vendor_is_brand is True
    assert JalalAirConditionerSpider.vendor_is_brand is False
    # Telemart puts its own name where some brands go.
    assert 'telemart' in BRAND_PLACEHOLDERS


def test_the_marketplaces_only_join_catalogued_acs():
    assert TelemartAirConditionerSpider.match_only is True
    assert DarazAirConditionerSpider.match_only is True
    assert not FriendsHomeAirConditionerSpider.match_only
    assert not JalalAirConditionerSpider.match_only


def test_the_scheduler_crawls_the_marketplaces_after_the_stores():
    order = list(DEFAULT_SPIDERS)

    for marketplace in ('telemart_acs', 'daraz_acs'):
        for store in ('friendshome_acs', 'jalal_acs', 'priceoye_acs'):
            assert order.index(marketplace) > order.index(store)
    assert order[-1] == 'whatmobile_opinions'


@pytest.mark.parametrize(
    'title',
    [
        'Transparent Ac Cover Inner 1 Ton 1.5 Ton Double Layer Dust-Proof Waterproof AC Cover',
        '9.5 Inch Portable Air Conditioner Fan Usb Electric Fan With Led Night Light',
        'Anex AG-9087 Air Cooler With Official Warranty',
        'Milli Legacy 9413 Pumps For Women',
        'AC Outdoor Unit Wall Stand Bracket Heavy Duty',
        'Copper Pipe Kit for Split AC 1.5 Ton',
        'Used Haier 1.5 Ton Inverter AC',
    ],
)
def test_covers_coolers_fans_and_stray_goods_are_not_acs(title):
    assert is_out_of_category('air-conditioners', title)


@pytest.mark.parametrize(
    'title',
    [
        'HAIER 1.5 TON T3 INVERTER AC Model HSU-19HFAB W',
        'TCL TAC-24T3-FH T3 2.0 Ton Floor Standing DC Inverter Air Conditioner With Official Warranty',
        # What comes after "with" is the offer.
        'Gree Inverter AC 1.5 Ton GS-18PITH11G with Free Installation and Remote',
        'Midea MCA3-18CRN1 R410 Ceiling Cassette Unit Cool 2.0HP',
    ],
)
def test_acs_are_acs(title):
    assert not is_out_of_category('air-conditioners', title)
