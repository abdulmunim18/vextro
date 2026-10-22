"""Every listing carries its catalogue category to the backend."""

from types import SimpleNamespace

import pytest

from vextro_scraper.items import SmartphoneItem
from vextro_scraper.pipelines import (
    NonSmartphoneItemError,
    VextroApiIngestionPipeline,
    VextroCleaningPipeline,
)
from vextro_scraper.spiders.daraz_spider import DarazSpider
from vextro_scraper.spiders.priceoye_spider import PriceoyeSpider
from vextro_scraper.spiders.shophive_spider import ShophiveSpider


def listing(**fields):
    item = SmartphoneItem()
    item.update({
        'platform': 'PriceOye',
        'external_id': 'X-1',
        'model': 'Samsung Galaxy Tab S10 FE 8GB 128GB',
        'brand': 'Samsung',
        'price': 99999,
        'availability': 'In Stock',
        'product_url': 'https://priceoye.pk/tablets/samsung/galaxy-tab-s10-fe',
        'image_urls': ['https://images.priceoye.pk/tab.jpg'],
        'specifications': {'ram': '8GB', 'storage_capacity': '128GB'},
    })
    item.update(fields)
    return item


@pytest.mark.parametrize('spider', [PriceoyeSpider, DarazSpider, ShophiveSpider])
def test_the_phone_spiders_declare_their_category(spider):
    assert spider.catalog_category == 'mobile-phones'


def test_a_listing_takes_its_category_from_its_spider():
    spider = SimpleNamespace(catalog_category='tablets')

    cleaned = VextroCleaningPipeline().process_item(listing(), spider)

    assert cleaned['category'] == 'tablets'


def test_a_listing_with_no_category_anywhere_is_a_phone():
    cleaned = VextroCleaningPipeline().process_item(listing(), None)

    assert cleaned['category'] == 'mobile-phones'


def test_the_backend_is_told_the_category_when_matching():
    payload = dict(listing(category='smart-watches'))

    match = VextroApiIngestionPipeline._build_match_payload(payload)

    assert match['category_slug'] == 'smart-watches'


def test_the_phone_accessory_rules_are_not_applied_to_other_categories():
    """An earbud's charging case is the product, not an accessory of it."""

    earbuds = listing(
        model='Apple AirPods Pro 3 with MagSafe Charging Case',
        specifications={},
    )
    spider = SimpleNamespace(catalog_category='audio-and-earbuds')

    assert VextroCleaningPipeline().process_item(earbuds, spider)['category'] == 'audio-and-earbuds'

    with pytest.raises(NonSmartphoneItemError):
        VextroCleaningPipeline().process_item(
            listing(model='Silicone Charging Case Cover for Samsung Galaxy A17', specifications={}),
            None,
        )
