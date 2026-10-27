"""Microwave ovens: their spiders and what the category does not sell."""

import pytest

from vextro_scraper.pipelines import is_out_of_category
from vextro_scraper.scheduler import DEFAULT_SPIDERS
from vextro_scraper.spiders.daraz_spider import DarazMicrowaveSpider
from vextro_scraper.spiders.shopify_spider import (
    FriendsHomeMicrowaveSpider,
    JalalMicrowaveSpider,
    TelemartMicrowaveSpider,
)

MICROWAVE_SPIDERS = [
    FriendsHomeMicrowaveSpider,
    JalalMicrowaveSpider,
    TelemartMicrowaveSpider,
    DarazMicrowaveSpider,
]


@pytest.mark.parametrize('spider', MICROWAVE_SPIDERS)
def test_the_microwave_spiders_file_their_listings_as_microwaves(spider):
    assert spider.catalog_category == 'microwave-ovens'
    assert spider.name.endswith('_microwaves')


def test_the_stores_read_their_microwave_collections():
    assert FriendsHomeMicrowaveSpider.collections == ('microwave-ovens-pakistan',)
    assert JalalMicrowaveSpider.collections == ('microwave-oven', 'built-in-microwave-oven')
    assert TelemartMicrowaveSpider.collections == ('microwave-ovens',)
    assert DarazMicrowaveSpider.CATALOG_PATH == '/microwaves/'


def test_the_marketplaces_only_join_catalogued_microwaves():
    assert TelemartMicrowaveSpider.match_only is True
    assert DarazMicrowaveSpider.match_only is True


def test_the_scheduler_crawls_the_marketplaces_after_the_stores():
    order = list(DEFAULT_SPIDERS)

    for marketplace in ('telemart_microwaves', 'daraz_microwaves'):
        for store in ('friendshome_microwaves', 'jalal_microwaves'):
            assert order.index(marketplace) > order.index(store)
    assert order[-1] == 'whatmobile_opinions'


@pytest.mark.parametrize(
    'title',
    [
        'Anex AG-3079 Convection Oven Toaster With Official Warranty',
        'Westpoint WF-4256 Deluxe Air Fryer 8 Liter With Official Warranty',
        'Westpoint WF-2800RK Rotisserie Oven with Kebab Grill 30 Liter',
        'Steeline SL-EB-73ERCD-10BC27T Electric Built-In Oven',
        'HALEY ELECTRIC OVEN 65L HY-5131',
        'Microwave Glass Plate Replacement 24.5cm',
        'Microwave Oven Cover Dust Proof',
    ],
)
def test_toasters_air_fryers_baking_ovens_and_plates_are_not_microwaves(title):
    assert is_out_of_category('microwave-ovens', title)


@pytest.mark.parametrize(
    'title',
    [
        'HAIER SOLO MICROWAVE OVEN 20 LITRE Model HMW-20MXP3',
        # An air fryer microwave, and a built-in microwave, are microwaves.
        'Dawlance DW-530 AF Air Fryer Microwave Oven 30 Liter with Official Warranty',
        'Steeline MEG56B 25L Built-In Microwave Oven',
    ],
)
def test_microwaves_are_microwaves(title):
    assert not is_out_of_category('microwave-ovens', title)
