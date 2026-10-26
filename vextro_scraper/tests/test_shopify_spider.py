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
