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
        ("Oppo Reno14 5G", "Oppo_Reno-14"),
        ("Itel A 50", "Itel_A50"),
    ],
)
def test_a_catalogue_name_and_a_whatmobile_address_name_one_phone(first, second):
    assert name_key(first) == name_key(second)


def test_look_alike_phones_keep_different_keys():
    assert name_key("Infinix Hot 70 Pro") != name_key("Infinix Hot 70")
    assert name_key("Samsung Galaxy A27") != name_key("Samsung Galaxy A26")
    assert name_key("Vivo Y17s") != name_key("Vivo Y17")
    assert name_key("Realme 13+ 5G") != name_key("Realme 13 5G")
    assert name_key("Realme 13+") == name_key("Realme_13-Plus")
    assert name_key("Oppo Reno 14") != name_key("Oppo Reno 14 F")


@pytest.mark.parametrize(
    "text",
    [
        "sale karna hai rabta 0323 4004838",
        "contact 03036806902 Hafizabad",
        "whatsapp +92-300-1234567 par",
        "for sale contact me 0301.9294806",
        "Contact num.0322_6604704 Lahore",
        "serious buyers only 0300/6689848",
        "Wholesale Price Lahore 0344/444/9964",
        "With Box And Original Charger 0332 - 2229442",
        "lash condition call 345 7281327",
        "contact 0319100168303191001683",
        "whatsapp 0093-786886910",
    ],
)
def test_contact_numbers_never_leave_the_spider(text):
    cleaned, removed = remove_contact_numbers(text)

    assert removed is True
    assert CONTACT_PLACEHOLDER in cleaned
    assert not any(character.isdigit() for character in cleaned)


def test_ordinary_numbers_in_an_opinion_are_kept():
    cleaned, removed = remove_contact_numbers(
        "24k ka set tha, 124k likh diya. 8GB RAM 256GB me acha hai, "
        "8 128 5000 50 wala model 85,000 ka, camon 30 8/256 10/10, "
        "38999 ....36999 par aa gaya, 17000-18500 mein"
    )

    assert removed is False
    assert "8 128 5000 50" in cleaned
    assert "124k" in cleaned and "256GB" in cleaned


@pytest.mark.parametrize(
    ("published", "expected"),
    [
        ("Total bakwas mobilernPrice is too much rn", "Total bakwas mobile Price is too much"),
        ("snapdragon 6 Gen 3rnPrice 120rnWhat a joke", "snapdragon 6 Gen 3 Price 120 What a joke"),
        ("Official PTA rnWhatsapp par", "Official PTA Whatsapp par"),
        ("modern phone, return policy acha", "modern phone, return policy acha"),
        ("hot 60i rn3 month warranty haii rnrn Only 4 sale", "hot 60i 3 month warranty haii Only 4 sale"),
        ("battery 5000.rn camera acha", "battery 5000. camera acha"),
    ],
)
def test_the_sites_lost_line_breaks_do_not_reach_the_reader(published, expected):
    cleaned, _ = remove_contact_numbers(published)

    assert cleaned == expected


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


def test_two_catalogue_phones_sharing_a_page_each_get_its_opinions():
    spider = WhatmobileSpider(
        phone_names='Samsung Galaxy A17|Samsung Galaxy A17 5G',
    )
    collect(spider.start())
    listing = HtmlResponse(
        url='https://www.whatmobile.com.pk/Samsung_Mobiles_Prices',
        encoding='utf-8',
        body='<a href="/Samsung_Galaxy-A17">a</a>',
    )

    requests = list(spider.parse_brand(listing, brand='Samsung'))
    assert len(requests) == 1

    item = CommunityOpinionsItem(
        source='whatmobile',
        catalog_name=requests[0].cb_kwargs['catalog_name'],
        opinions=[],
    )
    delivered = list(spider.deliveries(item))

    assert [entry['catalog_name'] for entry in delivered] == [
        'Samsung Galaxy A17',
        'Samsung Galaxy A17 5G',
    ]


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
