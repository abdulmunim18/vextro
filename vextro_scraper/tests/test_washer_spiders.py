"""Washing machines and dryers: their spiders and what the category does not sell."""

import pytest

from vextro_scraper.pipelines import is_out_of_category
from vextro_scraper.scheduler import DEFAULT_SPIDERS
from vextro_scraper.spiders.daraz_spider import DarazWashingMachineSpider
from vextro_scraper.spiders.shopify_spider import (
    FriendsHomeWashingMachineSpider,
    JalalWashingMachineSpider,
    TelemartWashingMachineSpider,
)

WASHER_SPIDERS = [
    FriendsHomeWashingMachineSpider,
    JalalWashingMachineSpider,
    TelemartWashingMachineSpider,
    DarazWashingMachineSpider,
]


@pytest.mark.parametrize('spider', WASHER_SPIDERS)
def test_the_washer_spiders_file_their_listings_as_washers(spider):
    assert spider.catalog_category == 'washing-machines'
    assert spider.name.endswith('_washers')


def test_the_stores_read_their_washer_collections():
    assert FriendsHomeWashingMachineSpider.collections == ('washing-machines-dryers',)
    assert JalalWashingMachineSpider.collections == ('washing-machines',)
    assert TelemartWashingMachineSpider.collections == ('washing-machines',)
    assert DarazWashingMachineSpider.CATALOG_PATH == '/washing-machines/'


def test_the_marketplaces_only_join_catalogued_washers():
    assert TelemartWashingMachineSpider.match_only is True
    assert DarazWashingMachineSpider.match_only is True


def test_the_scheduler_crawls_the_marketplaces_after_the_stores():
    order = list(DEFAULT_SPIDERS)

    for marketplace in ('telemart_washers', 'daraz_washers'):
        for store in ('friendshome_washers', 'jalal_washers'):
            assert order.index(marketplace) > order.index(store)
    assert order[-1] == 'whatmobile_opinions'


@pytest.mark.parametrize(
    'title',
    [
        'Super Asia ECM-4600 Plus Room Air Cooler with Official Warranty',
        'Washing Machine Cover Waterproof Dust Proof Top Load',
        'Washing Machine Stand Trolley Adjustable Base',
        'Inlet Hose Pipe for Automatic Washing Machine 2 Meter',
    ],
)
def test_coolers_covers_stands_and_hoses_are_not_washers(title):
    assert is_out_of_category('washing-machines', title)


@pytest.mark.parametrize(
    'title',
    [
        'HAIER 10KG TWIN TUB WASHING MACHINE Model HTW100-196G',
        'SUPER ASIA 10KG SPIN DRYER MACHINE Model SD-550',
        # What comes after "with" is the offer.
        'HAIER WASHING MACHINE 10KG HWM100-316HS8 BLACK WITH BASE',
    ],
)
def test_washers_and_dryers_are_washers(title):
    assert not is_out_of_category('washing-machines', title)


def washer_listing(**fields):
    from vextro_scraper.items import SmartphoneItem

    item = SmartphoneItem()
    item.update({
        'platform': 'friendshome',
        'external_id': 'W-1',
        'model': 'MIDAS 22KG AUTOMATIC TOP LOAD WASHING MACHINE Model MI-WMTL-2200',
        'brand': 'MIDAS',
        'price': 150000,
        'availability': 'In Stock',
        'product_url': 'https://friendshome.pk/products/midas-22kg',
        'image_urls': ['https://cdn.shopify.com/midas.jpg'],
        'specifications': {},
        'exact_model_title': True,
    })
    item.update(fields)
    return item


def test_a_store_naming_its_own_washer_keeps_the_number_ending_its_code():
    """The "-2200" of "MI-WMTL-2200" is the model's, not a Daraz stock code."""

    from types import SimpleNamespace

    from vextro_scraper.pipelines import VextroCleaningPipeline

    spider = SimpleNamespace(catalog_category='washing-machines')
    cleaned = VextroCleaningPipeline().process_item(washer_listing(), spider)

    assert cleaned['model'].endswith('MI-WMTL-2200')


def test_a_seller_listing_still_loses_the_stock_code_glued_to_it():
    from types import SimpleNamespace

    from vextro_scraper.pipelines import VextroCleaningPipeline

    spider = SimpleNamespace(catalog_category='washing-machines')
    cleaned = VextroCleaningPipeline().process_item(
        washer_listing(
            platform='Daraz',
            model='Haier HWM 120-826S6 12Kg Top Load Washing Machine-303662',
            exact_model_title=False,
        ),
        spider,
    )

    assert cleaned['model'] == 'Haier HWM 120-826S6 12Kg Top Load Washing Machine'
