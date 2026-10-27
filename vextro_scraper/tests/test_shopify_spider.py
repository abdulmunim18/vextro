"""The Shopify store adapter, read against feeds shaped like the stores' own."""

import json

import pytest
from scrapy.http import Request, TextResponse

from vextro_scraper.spiders.shopify_spider import PAGE_SIZE, ShopifyStoreSpider


class StoreSpider(ShopifyStoreSpider):
    name = 'teststore_acs'
    platform_code = 'friendshome'
    base_url = 'https://friendshome.pk'
    catalog_category = 'air-conditioners'
    collections = ('air-conditioners-ac-in-pakistan',)


def product(product_id=1, *, title='HAIER 1.5 TON T3 INVERTER AC Model HSU-19HFAB W',
            vendor='HAIER', variants=None, options=None):
    return {
        'id': product_id,
        'title': title,
        'handle': f'haier-ac-{product_id}',
        'vendor': vendor,
        'options': options or [{'name': 'Title', 'position': 1, 'values': ['Default Title']}],
        'variants': variants if variants is not None else [
            {'id': 100 + product_id, 'title': 'Default Title', 'option1': 'Default Title',
             'price': '154000.00', 'compare_at_price': '160000.00', 'available': True},
        ],
        'images': [{'src': f'https://cdn.shopify.com/ac-{product_id}.jpg'}],
    }


def page(url, products):
    return TextResponse(
        url=url,
        body=json.dumps({'products': products}).encode(),
        encoding='utf-8',
        request=Request(url),
    )


def read(spider, products, *, page_number=1):
    collection = spider.collections[0]
    response = page(
        f'{spider.base_url}/collections/{collection}/products.json?limit=250&page={page_number}',
        products,
    )
    return list(spider.parse_collection(response, collection, page_number))


def test_a_product_becomes_one_listing_with_its_price_and_stock():
    spider = StoreSpider()
    [item] = read(spider, [product()])

    assert item['platform'] == 'friendshome'
    assert item['external_id'] == '1'
    assert item['model'] == 'HAIER 1.5 TON T3 INVERTER AC Model HSU-19HFAB W'
    assert item['brand'] == 'HAIER'
    assert item['price'] == 154000
    assert item['original_price'] == 160000
    assert item['availability'] == 'In Stock'
    assert item['variant'] is None
    assert item['exact_model_title'] is True
    assert item['product_url'] == 'https://friendshome.pk/products/haier-ac-1'
    assert item['image_urls'] == ['https://cdn.shopify.com/ac-1.jpg']


def test_each_colour_is_a_listing_of_its_own():
    spider = StoreSpider()
    items = read(spider, [product(
        options=[{'name': 'Color', 'position': 1, 'values': ['White', 'Black']}],
        variants=[
            {'id': 11, 'title': 'White', 'option1': 'White', 'price': '100000', 'available': True},
            {'id': 12, 'title': 'Black', 'option1': 'Black', 'price': '102000', 'available': False},
        ],
    )])

    assert [(item['external_id'], item['color'], item['availability']) for item in items] == [
        ('1-11', 'White', 'In Stock'),
        ('1-12', 'Black', 'Out of Stock'),
    ]
    assert items[1]['product_url'].endswith('?variant=12')


def test_a_series_sold_as_one_product_names_each_model_in_its_listing():
    spider = StoreSpider()
    items = read(spider, [product(
        title='Kenwood Glory Pro DC Inverter Split Air Conditioner with Official Warranty',
        options=[{'name': 'Model', 'position': 1, 'values': ['KGP-12C01S - 1.0 Ton', 'KGP-18C01S - 1.5 Ton']}],
        variants=[
            {'id': 21, 'title': 'KGP-12C01S  -  1.0 Ton', 'option1': 'KGP-12C01S - 1.0 Ton',
             'price': '116999', 'available': True},
            {'id': 22, 'title': 'KGP-18C01S - 1.5 Ton', 'option1': 'KGP-18C01S - 1.5 Ton',
             'price': '143499', 'available': True},
        ],
    )])

    assert [item['model'] for item in items] == [
        'Kenwood Glory Pro DC Inverter Split Air Conditioner with Official Warranty KGP-12C01S - 1.0 Ton',
        'Kenwood Glory Pro DC Inverter Split Air Conditioner with Official Warranty KGP-18C01S - 1.5 Ton',
    ]
    assert [item['color'] for item in items] == [None, None]


def test_a_variant_at_rs_0_is_not_an_offer():
    spider = StoreSpider()
    items = read(spider, [product(variants=[
        {'id': 5, 'title': 'Default Title', 'price': '0.00', 'available': False},
    ])])

    assert items == []
    assert spider.unpriced_count == 1


def test_a_store_whose_vendor_is_itself_sends_no_brand():
    class Jalal(StoreSpider):
        name = 'testjalal_acs'
        vendor_is_brand = False

    [item] = read(Jalal(), [product(vendor='Jalal Electronics')])

    assert item['brand'] is None


def test_a_marketplace_only_joins_products_others_catalogued():
    class Telemart(StoreSpider):
        name = 'testtelemart_acs'
        match_only = True

    [item] = read(Telemart(), [product()])

    assert item['exact_model_title'] is False


def test_a_full_page_asks_for_the_next_and_a_short_one_finishes():
    spider = StoreSpider()
    full = read(spider, [product(number) for number in range(1, PAGE_SIZE + 1)])

    follow = [entry for entry in full if isinstance(entry, Request)]
    assert len(follow) == 1
    assert follow[0].url.endswith('page=2')
    assert not spider.full_crawl_completed

    read(spider, [product(PAGE_SIZE + 1)], page_number=2)

    assert spider.full_crawl_completed


def test_a_product_in_two_collections_is_sent_once():
    spider = StoreSpider()

    assert len(read(spider, [product(), product()])) == 1


def test_an_answer_that_is_not_a_feed_leaves_the_crawl_incomplete():
    spider = StoreSpider()
    collection = spider.collections[0]
    response = TextResponse(
        url=f'{spider.base_url}/collections/{collection}/products.json',
        body=b'<html>Just a moment...</html>',
        encoding='utf-8',
        request=Request(f'{spider.base_url}/collections/{collection}/products.json'),
    )

    assert list(spider.parse_collection(response, collection, 1)) == []
    assert not spider.full_crawl_completed


@pytest.mark.parametrize(
    ('url', 'handle'),
    [
        ('https://friendshome.pk/products/haier-ac-1', 'haier-ac-1'),
        ('https://www.friendshome.pk/collections/acs/products/haier-ac-1?variant=3', 'haier-ac-1'),
        ('https://jalalelectronics.com/products/haier-ac-1', None),
        ('https://friendshome.pk/collections/acs', None),
    ],
)
def test_only_this_stores_product_pages_are_refreshed(url, handle):
    assert StoreSpider().product_handle(url) == handle


def test_a_refresh_reads_each_product_on_its_own():
    spider = StoreSpider(product_urls='https://friendshome.pk/products/haier-ac-1')
    response = TextResponse(
        url='https://friendshome.pk/products/haier-ac-1.json',
        body=json.dumps({'product': product()}).encode(),
        encoding='utf-8',
        request=Request('https://friendshome.pk/products/haier-ac-1.json'),
    )

    [item] = list(spider.parse_product(response))

    assert item['external_id'] == '1'
    assert not spider.full_crawl_completed


# --------------------------------------------------------------------------
# Judge.me reviews on the product page
# --------------------------------------------------------------------------


def judgeme_review(review_id, score, *, handle='haier-ac-1', title='', body='', verified='true'):
    return (
        f"<div class='jdgm-rev' data-review-id='{review_id}' data-verified-buyer='{verified}'"
        f" data-product-url='/products/{handle}' data-thumb-up-count='2'>"
        f"<span class='jdgm-rev__rating' data-score='{score}'></span>"
        f"<span class='jdgm-rev__timestamp' data-content='2026-01-13 14:24:31 UTC'></span>"
        f"<span class='jdgm-rev__author'>Umer</span>"
        f"<b class='jdgm-rev__title'>{title}</b>"
        f"<div class='jdgm-rev__body'><p>{body}</p></div></div>"
    )


def judgeme_page(reviews, *, average='4.50', count='2', carousel=''):
    widget = (
        f"<div class='jdgm-rev-widg' data-average-rating='{average}' "
        f"data-number-of-reviews='{count}'>{''.join(reviews)}</div>"
    )
    # Some pages print the widget twice; a store-wide carousel sits apart.
    html = f"<html><body>{widget}{widget}<div class='jdgm-carousel'>{carousel}</div></body></html>"
    url = 'https://friendshome.pk/products/haier-ac-1'
    return TextResponse(url=url, body=html.encode(), encoding='utf-8', request=Request(url))


class ReviewingStore(StoreSpider):
    name = 'teststore_reviews'
    reads_judgeme_reviews = True


def test_a_reviewing_store_reads_each_product_page_before_sending_its_listings():
    spider = ReviewingStore()
    [request] = read(spider, [product()])

    assert isinstance(request, Request)
    assert request.url == 'https://friendshome.pk/products/haier-ac-1'
    assert [item['external_id'] for item in request.cb_kwargs['items']] == ['1']


def test_the_product_rating_goes_on_its_listings_and_its_reviews_are_sent_once():
    from vextro_scraper.items import ReviewBatchItem

    spider = ReviewingStore()
    [request] = read(spider, [product()])
    page = judgeme_page([
        judgeme_review('r-1', 5, title='Excellent', body='Cooling is fast.'),
        judgeme_review('r-2', 4, body='Good value.', verified='false'),
    ])

    out = list(spider.parse_review_page(page, **request.cb_kwargs))
    [item] = [entry for entry in out if not isinstance(entry, ReviewBatchItem)]
    [batch] = [entry for entry in out if isinstance(entry, ReviewBatchItem)]

    assert item['rating'] == 4.5
    assert item['review_count'] == 2
    assert batch['platform'] == 'friendshome'
    assert batch['external_listing_id'] == '1'
    # The widget is printed twice; each review is sent once.
    assert [review['external_review_id'] for review in batch['reviews']] == ['r-1', 'r-2']
    first, second = batch['reviews']
    assert first['rating'] == 5
    assert first['review_text'] == 'Excellent. Cooling is fast.'
    assert first['reviewed_at'] == '2026-01-13T14:24:31+00:00'
    assert first['verified_purchase'] is True
    assert second['verified_purchase'] is False


def test_reviews_of_other_products_on_the_page_are_not_this_products():
    from vextro_scraper.items import ReviewBatchItem

    spider = ReviewingStore()
    [request] = read(spider, [product()])
    page = judgeme_page(
        [judgeme_review('r-9', 5, handle='westpoint-toaster', body='Nice toaster.')],
        average='0.00',
        count='0',
        carousel=judgeme_review('r-8', 5, handle='gree-ac', body='Store-wide.'),
    )

    out = list(spider.parse_review_page(page, **request.cb_kwargs))

    assert not [entry for entry in out if isinstance(entry, ReviewBatchItem)]
    [item] = out
    assert item['rating'] is None
    assert item['review_count'] == 0


def test_a_product_page_that_fails_still_sends_the_listings():
    from types import SimpleNamespace

    spider = ReviewingStore()
    [request] = read(spider, [product()])
    failure = SimpleNamespace(request=request, getErrorMessage=lambda: 'timeout')

    [item] = list(spider.review_page_failed(failure))

    assert item['external_id'] == '1'
    assert item['price'] == 154000


def test_friends_home_and_jalal_read_reviews_and_telemart_does_not():
    from vextro_scraper.spiders.shopify_spider import (
        FriendsHomeStore,
        JalalStore,
        TelemartStore,
    )

    assert FriendsHomeStore.reads_judgeme_reviews is True
    assert JalalStore.reads_judgeme_reviews is True
    assert TelemartStore.reads_judgeme_reviews is False
