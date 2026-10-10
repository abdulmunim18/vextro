"""WhatMobile spider: ratings and visitor opinions for VEXTRO's phones."""

import asyncio
from pathlib import Path

import pytest
from scrapy.http import HtmlResponse, Request

from vextro_scraper.items import CommunityOpinionsItem
from vextro_scraper.spiders.whatmobile_spider import (
    CONTACT_PLACEHOLDER,
    WhatmobileSpider,
    name_key,
    remove_contact_numbers,
)


FIXTURES = Path(__file__).parent / 'fixtures'


def fixture_response(name, url):
    return HtmlResponse(
        url=url,
        body=(FIXTURES / name).read_bytes(),
        encoding='utf-8',
    )


def collect(async_generator):
    async def drain():
        return [output async for output in async_generator]

    return asyncio.run(drain())


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Samsung Galaxy A27 5G", "Samsung_Galaxy-A27"),
        ("Infinix Hot 70 Pro", "Infinix_Hot-70-Pro"),
        ("Apple iPhone 17 Pro Max", "Apple_iPhone-17-Pro-Max"),
        ("Tecno Mobile Spark 40", "Tecno_Spark-40"),
    ],
)
def test_a_catalogue_name_and_a_whatmobile_address_name_one_phone(first, second):
    assert name_key(first) == name_key(second)


def test_look_alike_phones_keep_different_keys():
    assert name_key("Infinix Hot 70 Pro") != name_key("Infinix Hot 70")
    assert name_key("Samsung Galaxy A27") != name_key("Samsung Galaxy A26")


@pytest.mark.parametrize(
    "text",
    [
        "sale karna hai rabta 0323 4004838",
        "contact 03036806902 Hafizabad",
        "whatsapp +92-300-1234567 par",
    ],
)
def test_contact_numbers_never_leave_the_spider(text):
    cleaned, removed = remove_contact_numbers(text)

    assert removed is True
    assert CONTACT_PLACEHOLDER in cleaned
    assert not any(character.isdigit() for character in cleaned)


def test_ordinary_numbers_in_an_opinion_are_kept():
    cleaned, removed = remove_contact_numbers(
        "24k ka set tha, 124k likh diya. 8GB RAM 256GB me acha hai"
    )

    assert removed is False
    assert "124k" in cleaned and "256GB" in cleaned


def test_only_the_brands_of_wanted_phones_are_opened():
    spider = WhatmobileSpider(
        phone_names='Infinix Hot 70 Pro|Samsung Galaxy A27|Infinix Note 60',
    )
    requests = collect(spider.start())

    assert sorted(request.url for request in requests) == [
        'https://www.whatmobile.com.pk/Infinix_Mobiles_Prices',
        'https://www.whatmobile.com.pk/Samsung_Mobiles_Prices',
    ]


def test_a_brand_listing_leads_only_to_phones_vextro_lists():
    spider = WhatmobileSpider(phone_names='Infinix Hot 70 Pro')
    collect(spider.start())
    listing = HtmlResponse(
        url='https://www.whatmobile.com.pk/Infinix_Mobiles_Prices',
        encoding='utf-8',
        body=(
            '<a href="/Infinix_Hot-70-Pro">a</a>'
            '<a href="Infinix_Hot-70">b</a>'
            '<a href="/Infinix_Hot-70-Pro">again</a>'
            '<a href="/Samsung_Galaxy-A27">other brand</a>'
            '<a href="/Infinix_Mobiles_Prices">self</a>'
        ),
    )

    requests = list(spider.parse_brand(listing, brand='Infinix'))

    assert [request.url for request in requests] == [
        'https://www.whatmobile.com.pk/Infinix_Hot-70-Pro',
    ]
    assert requests[0].cb_kwargs == {
        'slug': 'Infinix_Hot-70-Pro',
        'catalog_name': 'Infinix Hot 70 Pro',
    }


def test_a_phone_page_gives_its_rating_and_asks_for_its_opinions():
    spider = WhatmobileSpider()
    outputs = list(spider.parse_phone(
        fixture_response(
            'whatmobile_phone.html',
            'https://www.whatmobile.com.pk/Infinix_Hot-70-Pro',
        ),
        slug='Infinix_Hot-70-Pro',
        catalog_name='Infinix Hot 70 Pro',
    ))

    assert len(outputs) == 1 and isinstance(outputs[0], Request)
    assert outputs[0].url == (
        'https://www.whatmobile.com.pk/Infinix_Hot-70-Pro_Reviews_0'
    )

    item = outputs[0].cb_kwargs['item']
    assert item['source'] == 'whatmobile'
    assert item['product_name'] == 'Infinix Hot 70 Pro'
    assert item['brand'] == 'Infinix'
    assert item['rating'] == 2.8
    assert item['rating_count'] == 22
    assert item['reference_price'] and item['reference_price'] > 10000


def test_opinions_carry_their_date_and_author_and_lose_phone_numbers():
    spider = WhatmobileSpider()
    item = CommunityOpinionsItem(source='whatmobile', opinions=[])
    outputs = list(spider.parse_opinions(
        fixture_response(
            'whatmobile_reviews.html',
            'https://www.whatmobile.com.pk/Infinix_Hot-70-Pro_Reviews_0',
        ),
        item=item,
    ))

    assert outputs == [item]
    opinions = item['opinions']
    assert len(opinions) == 7

    first = opinions[0]
    assert first['position'] == 1
    assert first['author'].startswith('visitor')
    assert first['posted_at'].startswith('20')
    assert first['text']
    assert first['contact_removed'] is False

    advert = opinions[-1]
    assert advert['contact_removed'] is True
    assert advert['posted_at'].startswith('2026-10-02')
    assert CONTACT_PLACEHOLDER in advert['text']
    assert '0323' not in advert['text'] and '03036806902' not in advert['text']
