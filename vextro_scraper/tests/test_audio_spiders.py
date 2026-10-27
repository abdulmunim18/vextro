"""Earbuds and headphones: their spiders and what the category does not sell."""

import pytest

from vextro_scraper.pipelines import bounded_external_id, infer_brand, is_out_of_category
from vextro_scraper.scheduler import DEFAULT_SPIDERS
from vextro_scraper.spiders.daraz_spider import DarazAudioSpider
from vextro_scraper.spiders.priceoye_spider import PriceoyeAudioSpider
from vextro_scraper.spiders.shophive_spider import ShophiveAudioSpider


@pytest.mark.parametrize('spider', [PriceoyeAudioSpider, DarazAudioSpider, ShophiveAudioSpider])
def test_the_audio_spiders_file_their_listings_as_audio(spider):
    assert spider.catalog_category == 'audio-and-earbuds'
    assert spider.name.endswith('_audio')


def test_priceoye_audio_walks_the_earbuds_catalogue_without_unbranded_pages():
    spider = PriceoyeAudioSpider()

    assert spider.start_urls == ['https://priceoye.pk/wireless-earbuds']
    assert spider.files_under_unbranded(
        'https://priceoye.pk/wireless-earbuds/assorted/kisonli-f2-tws-wireless-earbuds'
    )
    assert not spider.files_under_unbranded(
        'https://priceoye.pk/wireless-earbuds/apple/apple-airpods-4'
    )


def test_shophive_audio_reads_earbuds_headphones_and_airpods_only():
    paths = ShophiveAudioSpider.category_paths

    assert 'audio/earbuds' in paths and 'audio/wireless-headphones' in paths
    assert 'apple/airpod' in paths
    assert not any('speaker' in path or 'microphone' in path for path in paths)


def test_daraz_audio_only_joins_catalogued_earbuds():
    assert DarazAudioSpider.match_only is True
    assert DarazAudioSpider.CATALOG_PATH == '/wireless-earbuds/'


def test_the_scheduler_crawls_daraz_audio_after_the_stores():
    order = list(DEFAULT_SPIDERS)

    assert order.index('daraz_audio') > order.index('priceoye_audio')
    assert order.index('daraz_audio') > order.index('shophive_audio')
    assert order[-1] == 'whatmobile_opinions'


@pytest.mark.parametrize(
    'title',
    [
        'Silicone Case for AirPods Pro 2',
        'AirPods Pro 2 Protective Case Cover',
        'Replacement Ear Tips for Galaxy Buds',
        'Anker Soundcore Motion 300 Bluetooth Speaker',
        'Boya BY-M1 Lavalier Microphone',
    ],
)
def test_cases_tips_speakers_and_microphones_are_not_earbuds(title):
    assert is_out_of_category('audio-and-earbuds', title)


@pytest.mark.parametrize(
    'title',
    [
        'Apple AirPods Pro 3 with MagSafe Charging Case (USB-C)',
        'QCY T13 ANC 2 TWS Bluetooth 5.3 Earbuds',
        'Audionic Hammer 110 Ultra On-Ear Headphone',
        'Earbuds with Dual Speaker Drivers',
    ],
)
def test_earbuds_and_headphones_are_audio(title):
    assert not is_out_of_category('audio-and-earbuds', title)


def test_an_overlong_listing_id_is_shortened_the_same_way_every_crawl():
    slug = (
        'xinji-stone-m2-wireless-earbuds-7-hour-playtime-bluetooth-5-3-and-immersive-'
        'hi-fi-sound-6-month-warranty-bass-music-sound-earpods-for-men-and-women--black'
    )

    shortened = bounded_external_id(slug)

    assert len(shortened) <= 150
    assert shortened == bounded_external_id(slug)
    assert shortened.startswith('xinji-stone-m2-wireless-earbuds')
    assert bounded_external_id('apple-airpods-4--white') == 'apple-airpods-4--white'


@pytest.mark.parametrize(
    ('title', 'expected'),
    [
        ('Anker Soundcore Life P3i Hybrid ANC Earbuds', 'Anker'),
        ('Audionic Airbud 625 Wireless Earbuds', 'Audionic'),
        ('QCY T13 ANC 2 TWS Bluetooth 5.3 Earbuds', 'QCY'),
    ],
)
def test_an_audio_makers_name_in_a_daraz_title_is_its_brand(title, expected):
    assert infer_brand(title, 'No Brand') == expected
