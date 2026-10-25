"""Laptops: their spiders and what the laptop category does not sell."""

import pytest

from test_api_ingestion_pipeline import (
    FakeResponse,
    RecordingSession,
    build_clean_item,
    build_pipeline,
)
from vextro_scraper.pipelines import (
    ReviewsOfTurnedAwayListingError,
    VextroApiIngestionPipeline,
    is_out_of_category,
)
from vextro_scraper.scheduler import DEFAULT_SPIDERS
from vextro_scraper.spiders.daraz_spider import DarazLaptopSpider
from vextro_scraper.spiders.priceoye_spider import PriceoyeLaptopSpider
from vextro_scraper.spiders.shophive_spider import ShophiveLaptopSpider


@pytest.mark.parametrize('spider', [PriceoyeLaptopSpider, DarazLaptopSpider, ShophiveLaptopSpider])
def test_the_laptop_spiders_file_their_listings_as_laptops(spider):
    assert spider.catalog_category == 'laptops'
    assert spider.name.endswith('_laptops')


def test_priceoye_laptops_walk_the_laptop_catalogue():
    assert PriceoyeLaptopSpider().start_urls == ['https://priceoye.pk/laptops']


def test_shophive_laptops_read_laptops_and_macbooks_not_desktops():
    paths = ShophiveLaptopSpider.category_paths

    assert 'laptops-computers/laptops' in paths
    assert 'apple/mac/macbook-air' in paths and 'apple/mac/macbook-pro' in paths
    assert not any(word in path for path in paths for word in ('imac', 'mini', 'studio', 'accessories'))


def test_daraz_laptops_only_join_catalogued_laptops():
    assert DarazLaptopSpider.match_only is True
    assert DarazLaptopSpider.CATALOG_PATH == '/laptops/'


def test_the_scheduler_crawls_daraz_laptops_after_the_stores():
    order = list(DEFAULT_SPIDERS)

    assert order.index('daraz_laptops') > order.index('priceoye_laptops')
    assert order.index('daraz_laptops') > order.index('shophive_laptops')
    assert order[-1] == 'whatmobile_opinions'


def test_a_laptops_large_ram_is_not_taken_for_storage():
    """A phone's "64GB RAM" is storage misfiled; a laptop's is RAM."""

    laptop = {
        **build_clean_item(),
        'model': 'MSI Raider 18 HX AI Ultra 9 275HX 64GB 2TB SSD',
        'category': 'laptops',
        'specifications': {'ram': '64GB', 'storage_capacity': '2048GB'},
    }

    payload = VextroApiIngestionPipeline._build_match_payload(laptop)

    assert payload['ram_gb'] == 64
    assert payload['storage_gb'] == 2048

    # A Daraz "RAM" field holding the description's "512GB SSD" is storage.
    seller = {**laptop, 'specifications': {'ram': 'and 512GB PCIe NVMe SSD ensure'}}
    payload = VextroApiIngestionPipeline._build_match_payload(seller)

    assert payload['ram_gb'] is None
    assert payload['storage_gb'] == 512


def test_the_reviews_of_a_listing_sent_for_review_are_not_delivered():
    """The queued listing is not in the catalogue; its reviews would 404."""

    session = RecordingSession(
        FakeResponse(200, {
            'matched': False,
            'confidence': 80,
            'product_variant_id': None,
            'suggested_product_variant_id': 9,
            'reason': 'The requested processor does not match this catalog variant.',
        }),
        FakeResponse(201, {'id': 4, 'status': 'pending'}),
    )
    pipeline = build_pipeline(session)
    listing = {**build_clean_item(), 'external_id': 'thinkbook-16--grey', 'category': 'laptops'}

    with pytest.raises(Exception):
        pipeline.process_item(listing, spider=None)

    with pytest.raises(ReviewsOfTurnedAwayListingError):
        pipeline.process_item(
            {'platform': 'PriceOye', 'external_listing_id': 'thinkbook-16--grey', 'reviews': [{}]},
            spider=None,
        )

    assert len(session.calls) == 2


@pytest.mark.parametrize(
    'title',
    [
        'bags for girls bags for girls',
        'Laptop Backpack 15.6 inch Waterproof',
        'Dell 65W Laptop Charger Adapter',
        'Laptop Cooling Pad with 5 Fans',
        'Dell Latitude 7490 Core i7 8th Gen Used Laptop',
        'HP EliteBook 840 G5 Refurbished',
    ],
)
def test_bags_chargers_and_used_machines_are_not_laptops(title):
    assert is_out_of_category('laptops', title)


@pytest.mark.parametrize(
    'title',
    [
        'HP ProBook 460 G11 Intel Core Ultra 5 125U 16GB RAM 512GB SSD',
        'Apple Macbook Air 2026 M5 15.3" 24GB 1TB SSD',
        'Asus TUF Gaming A15 AMD Ryzen 7 8845HS 16GB RAM 512GB SSD RTX3050 4GB Graphics Laptop',
    ],
)
def test_laptops_are_laptops(title):
    assert not is_out_of_category('laptops', title)
