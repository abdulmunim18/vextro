"""Parser and delivery tests for the smartphone price-sync fixes.

The marketplace payloads below are trimmed copies of what Daraz and PriceOye
actually served while this work was done, so a parser change that stops
reading the real current price fails here.
"""

import json

import pytest
from scrapy.http import HtmlResponse, Request, TextResponse

from vextro_scraper.items import ReviewBatchItem
from vextro_scraper.normalizers import (
    extract_json_ld_products,
    json_ld_availability,
    parse_daraz_specification_sheet,
    parse_price,
    parse_rating,
)
from vextro_scraper.pipelines import (
    REVIEWS_INGESTED,
    VextroApiIngestionPipeline,
    VextroCleaningPipeline,
)
from vextro_scraper.spiders.daraz_spider import (
    DarazReviewParserError,
    DarazSpider,
)
from vextro_scraper.spiders.priceoye_spider import PriceoyeSpider


# --------------------------------------------------------------------------
# Daraz catalog payload (trimmed from https://www.daraz.pk/smartphones/?ajax=true)
# --------------------------------------------------------------------------

DARAZ_DISCOUNTED_ITEM = {
    "itemId": "1968128816",
    "itemUrl": "//www.daraz.pk/products/realme-c100i-i1968128816.html",
    "name": "Realme C100i 4GB/128GB",
    "brandName": "Realme",
    "price": "46999",
    "priceShow": "Rs. 46,999",
    "originalPriceShow": "Rs. 52,999",
    "ratingScore": "5.0",
    "review": "3",
    "sellerName": "Realme Flagship Store",
    "sellerId": "6005214672679",
    "sku": "1968128816_PK",
    "skuId": "14051764075",
    "inStock": True,
    "image": "//static-01.daraz.pk/p/realme-c100i.png",
    "description": [
        "General FeaturesRelease Date05 Aug 2026SIM SupportDual Nano SIM"
        "Operating SystemAndroid 16DisplayScreen Size6.74-inch HD+ Display"
        "MemoryInternal Memory128GBRAM4GB RAM+4GB Extendable RAM"
        "PerformanceProcessorOcta-CoreBatteryType5000 mAh"
        "CameraFront Camera5MPBack Camera8MP"
        "ConnectivityBluetoothYes5GN/ANFCN/A"
    ],
}

DARAZ_NO_BRAND_ITEM = {
    "itemId": "1968648084",
    "itemUrl": "//www.daraz.pk/products/vgotel-onyx-2-i1968648084.html",
    "name": "VGOTEL ONYX 2 = 3GB RAM = 32GB ROM = 3000mAh BATTERY",
    "brandName": "No Brand",
    "price": "17499",
    "originalPriceShow": "",
    "ratingScore": "",
    "review": "",
    "sellerName": "T.R Communication",
    "sellerId": "6005214672679",
    "inStock": True,
}


def daraz_catalog_response(*items):
    """Return a Daraz AJAX catalog response holding the given items."""

    return TextResponse(
        url="https://www.daraz.pk/smartphones/?ajax=true",
        body=json.dumps(
            {
                "mods": {"listItems": list(items)},
                "mainInfo": {
                    "page": "1",
                    "pageSize": "40",
                    "totalResults": str(len(items)),
                },
            }
        ).encode("utf-8"),
    )


def daraz_items(*items):
    """Return only the smartphone items a Daraz catalog page yields."""

    results = list(DarazSpider().parse(daraz_catalog_response(*items)))

    return [
        result
        for result in results
        if not isinstance(result, Request)
    ]


def test_daraz_reads_the_current_and_list_price():
    """``price`` is the selling price; ``originalPriceShow`` is the list price."""

    item = daraz_items(DARAZ_DISCOUNTED_ITEM)[0]

    assert item["price"] == 46999.0
    assert item["original_price"] == 52999.0


def test_daraz_reads_the_review_aggregate_and_seller():
    """Marketplace rating, review count and seller now reach the listing."""

    item = daraz_items(DARAZ_DISCOUNTED_ITEM)[0]

    assert item["rating"] == 5.0
    assert item["review_count"] == 3
    assert item["seller"] == {
        "name": "Realme Flagship Store",
        "external_seller_id": "6005214672679",
        "is_verified": False,
    }
    assert item["sku"] == "1968128816_PK"


def test_daraz_drops_empty_marketplace_fields():
    """Empty strings are absent data, not zero ratings or free discounts."""

    item = daraz_items(DARAZ_NO_BRAND_ITEM)[0]

    assert item["original_price"] is None
    assert item["rating"] is None
    assert item["review_count"] == 0
    # "No Brand" is a Daraz placeholder; the title still identifies VGOTEL.
    assert item["brand"] == "No Brand"


def test_daraz_no_longer_invents_placeholder_variants():
    """Colour, variant and warranty are left empty unless the page says so."""

    item = daraz_items(DARAZ_DISCOUNTED_ITEM)[0]

    assert item["color"] is None
    assert item["variant"] is None
    assert item["warranty"] is None


def test_daraz_description_sheet_becomes_specifications():
    """The packed description sheet is Daraz's richest specification source."""

    item = daraz_items(DARAZ_DISCOUNTED_ITEM)[0]
    specifications = item["specifications"]

    assert specifications["Internal Memory"] == "128GB"
    # Daraz writes "4GB RAM+4GB Extendable RAM". Splitting on its own labels
    # keeps the first, physical figure, so extended-RAM marketing cannot
    # inflate the variant to 8GB and break matching.
    assert specifications["RAM"] == "4GB"
    assert specifications["Battery Capacity"] == "5000 mAh"
    # "Display" is also a section heading, so the trailing word ends the
    # value. The screen size itself, which is what matching uses, survives.
    assert specifications["Screen Size"] == "6.74-inch HD+"
    assert specifications["Operating System"] == "Android 16"
    assert specifications["Front Camera"] == "5MP"
    assert specifications["Back Camera"] == "8MP"
    # Placeholder values are dropped rather than stored as "N/A".
    assert "NFC" not in specifications


def test_daraz_specification_sheet_parser_handles_empty_input():
    """A missing or unrecognised sheet yields no specifications."""

    assert parse_daraz_specification_sheet(None) == {}
    assert parse_daraz_specification_sheet("") == {}
    assert parse_daraz_specification_sheet("nothing recognisable") == {}


def test_daraz_requests_reviews_only_for_items_that_have_them():
    """A review request is issued per reviewed item, and only for those."""

    requests = [
        result
        for result in DarazSpider().parse(
            daraz_catalog_response(
                DARAZ_DISCOUNTED_ITEM,
                DARAZ_NO_BRAND_ITEM,
            )
        )
        if isinstance(result, Request)
    ]
    review_requests = [
        request
        for request in requests
        if "getReviewList" in request.url
    ]

    assert len(review_requests) == 1
    assert "itemId=1968128816" in review_requests[0].url


# --------------------------------------------------------------------------
# Daraz review API (trimmed from my.daraz.pk/pdp/review/getReviewList)
# --------------------------------------------------------------------------

DARAZ_REVIEW_PAYLOAD = {
    "success": True,
    "model": {
        "items": [
            {
                "reviewRateId": 84441280428816,
                "buyerId": 6005704928656,
                "buyerName": "Bushra",
                "rating": 5,
                "reviewContent": (
                    "fast delivery, packing is good, received as shown in pic"
                ),
                "boughtDate": "20 Sep 2026",
                "reviewTime": "2 weeks ago",
                "isPurchased": True,
                "upVotes": 2,
                "images": [
                    {"url": "https://lzd-u.slatic.net/review-one.jpg"},
                ],
            },
            {
                "reviewRateId": 84441280428817,
                "buyerName": None,
                "rating": 0,
                "reviewContent": "",
                "boughtDate": "20 Sep 2026",
                "isPurchased": False,
                "upVotes": -1,
            },
        ],
        "paging": {"currentPage": 1, "totalPages": 1, "totalItems": 2},
        "ratings": {"average": 5, "reviewCount": 2},
    },
}


def daraz_review_response(payload):
    return TextResponse(
        url=(
            "https://my.daraz.pk/pdp/review/getReviewList"
            "?itemId=1968128816&pageSize=20&filter=0&sort=0&pageNo=1"
        ),
        body=json.dumps(payload).encode("utf-8"),
    )


def test_daraz_review_parser_builds_a_deduplicable_batch():
    """Daraz's own review ID is carried through as the dedupe key."""

    batches = list(
        DarazSpider().parse_reviews(
            daraz_review_response(DARAZ_REVIEW_PAYLOAD),
            external_listing_id="1968128816",
        )
    )

    assert len(batches) == 1
    batch = batches[0]

    assert isinstance(batch, ReviewBatchItem)
    assert batch["platform"] == "Daraz"
    assert batch["external_listing_id"] == "1968128816"

    # The second record has an impossible rating and is skipped, not faked.
    assert len(batch["reviews"]) == 1
    review = batch["reviews"][0]

    assert review["external_review_id"] == "84441280428816"
    assert review["reviewer_external_id"] == "6005704928656"
    assert review["reviewer_display_name"] == "Bushra"
    assert review["rating"] == 5
    assert review["verified_purchase"] is True
    assert review["helpful_count"] == 2
    assert review["reviewed_at"].startswith("2026-09-20")
    assert review["raw_metadata"]["image_urls"] == [
        "https://lzd-u.slatic.net/review-one.jpg"
    ]


def test_daraz_review_parser_rejects_a_broken_contract():
    """A payload that is not the documented shape is a monitorable error."""

    spider = DarazSpider()

    with pytest.raises(DarazReviewParserError):
        list(
            spider.parse_reviews(
                daraz_review_response({"success": True}),
                external_listing_id="1968128816",
            )
        )

    with pytest.raises(DarazReviewParserError):
        list(
            spider.parse_reviews(
                TextResponse(
                    url="https://my.daraz.pk/pdp/review/getReviewList",
                    body=b"not-json",
                ),
                external_listing_id="1968128816",
            )
        )


def test_daraz_review_parser_is_quiet_when_there_are_no_reviews():
    """An item with zero reviews yields nothing rather than failing."""

    assert (
        list(
            DarazSpider().parse_reviews(
                daraz_review_response(
                    {
                        "success": True,
                        "model": {
                            "items": [],
                            "paging": {"totalPages": 0},
                        },
                    }
                ),
                external_listing_id="1968128816",
            )
        )
        == []
    )


# --------------------------------------------------------------------------
# PriceOye product page (trimmed from priceoye.pk product markup)
# --------------------------------------------------------------------------

PRICEOYE_PRODUCT_HTML = """
<html><body>
<script type="application/ld+json">
{"@context":"http:\\/\\/schema.org","@type":"Product",
 "name":"Infinix Note 60 Pro (8GB-256GB)","productID":14912,
 "brand":"Infinix",
 "offers":{"@type":"Offer","price":"119999.00","priceCurrency":"PKR",
  "availability":"http:\\/\\/schema.org\\/InStock"},
 "aggregateRating":{"@type":"AggregateRating","ratingValue":5,
  "ratingCount":38}}
</script>
<div class="product-price po-price-border"><div class="product-prcing-section">
  <span class="summary-price price-size-lg"><sup>Rs</sup>119,999</span>
  <div class="save-retail-pricebox"><div class="retail-price market-price">
    <span class="summary-price line-through stock-info"><sup>Rs</sup>125,999</span>
  </div></div>
  <div class="save-price-section"><span class="save-price">5% OFF </span></div>
</div></div>
<div class="po-variant-card"><div class="product-variant">
  <ul class="colors">
    <li class="active"><a><div class="title"><div class="color-name">Ocean Blue</div></div></a></li>
    <li><a><div class="title"><div class="color-name">Torino Black</div></div></a></li>
  </ul>
</div></div>
<img class="main-product-img" src="/images/note-60-pro.webp" />
<script>var variantData = {"product_availability":"Out Of Stock"};</script>
</body></html>
"""


def priceoye_product_response():
    return HtmlResponse(
        url=(
            "https://priceoye.pk/mobiles/infinix/"
            "infinix-note-60-pro-256gb-8gb"
        ),
        body=PRICEOYE_PRODUCT_HTML.encode("utf-8"),
        encoding="utf-8",
        request=Request(
            url=(
                "https://priceoye.pk/mobiles/infinix/"
                "infinix-note-60-pro-256gb-8gb"
            ),
            meta={
                "item": {
                    "platform": "PriceOye",
                    "model": "Infinix Note 60 Pro (8GB-256GB)",
                }
            },
        ),
    )


def priceoye_item():
    response = priceoye_product_response()
    response.meta["item"] = {
        "platform": "PriceOye",
        "model": "Infinix Note 60 Pro (8GB-256GB)",
    }

    return list(PriceoyeSpider().parse_product(response))[0]


def test_priceoye_prefers_its_own_structured_offer():
    """The schema.org offer, not the pricing markup, states the price."""

    item = priceoye_item()

    assert item["price"] == 119999.0
    assert item["original_price"] == 125999.0
    assert item["sku"] == "14912"
    assert item["brand"] == "Infinix"


def test_priceoye_reads_the_structured_review_aggregate():
    """Rating and review count come from the product page, not /reviews."""

    item = priceoye_item()

    assert item["rating"] == 5.0
    assert item["review_count"] == 38


def test_priceoye_availability_trusts_the_product_level_offer():
    """A sold-out colour must not mark the whole product unavailable.

    The embedded variant data reports "Out Of Stock" for the selected
    colour while the product offer reports InStock. The product-level
    statement is the one the shopper's "View on PriceOye" button honours.
    """

    item = priceoye_item()

    assert item["availability"] == "In Stock"


def test_priceoye_records_the_selected_colour_only():
    """The active colour swatch is the variant; memory options are not."""

    item = priceoye_item()

    assert item["color"] == "Ocean Blue"
    assert item["variant"] == "(8GB-256GB)"


def test_priceoye_falls_back_to_markup_without_structured_data():
    """Removing the JSON-LD block must not lose the current price."""

    body = PRICEOYE_PRODUCT_HTML.split("</script>", 1)[1]
    url = "https://priceoye.pk/mobiles/infinix/note-60-pro"
    response = HtmlResponse(
        url=url,
        body=f"<html><body>{body}".encode("utf-8"),
        encoding="utf-8",
        request=Request(
            url=url,
            meta={
                "item": {
                    "platform": "PriceOye",
                    "model": "Infinix Note 60 Pro (8GB-256GB)",
                }
            },
        ),
    )

    item = list(PriceoyeSpider().parse_product(response))[0]

    assert item["price"] == 119999.0
    assert item["original_price"] == 125999.0


# --------------------------------------------------------------------------
# Normalizer units
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Rs. 17,499", 17499.0),
        ("Rs119,999", 119999.0),
        ("46999", 46999.0),
        ("119999.00", 119999.0),
        (46999, 46999.0),
        ("", None),
        ("   ", None),
        (None, None),
        ("Call for price", None),
        (0, None),
        (-5, None),
        (True, None),
    ],
)
def test_price_parser_accepts_every_marketplace_spelling(raw, expected):
    assert parse_price(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("5.0", 5.0), ("4.65", 4.65), ("", None), ("6", None), ("0", None)],
)
def test_rating_parser_bounds_its_output(raw, expected):
    assert parse_rating(raw) == expected


def test_json_ld_availability_reads_both_spellings():
    products = extract_json_ld_products(PRICEOYE_PRODUCT_HTML)

    assert len(products) == 1
    assert json_ld_availability(products[0]) is True
    assert json_ld_availability({"offers": {"availability": "OutOfStock"}}) is (
        False
    )
    assert json_ld_availability({}) is None


# --------------------------------------------------------------------------
# Delivery ordering
# --------------------------------------------------------------------------


class _Response:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _Session:
    """Record every delivery the pipeline makes, in order."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))

        return self._responses.pop(0)


class _Crawler:
    def __init__(self):
        self.sent = []

        class _Signals:
            def __init__(self, sent):
                self._sent = sent

            def send_catch_log(self, signal, **kwargs):
                self._sent.append((signal, kwargs))

        self.signals = _Signals(self.sent)


def test_review_delivery_flushes_pending_listings_first():
    """A new product's listing is delivered before its reviews are sent.

    Reviews are resolved by (platform, external listing id). While listings
    sat in the bulk buffer, a brand-new product's reviews arrived before the
    listing existed and were rejected as "listing unresolved".
    """

    session = _Session(
        # resolve-product
        _Response(200, {
            "matched": True,
            "confidence": 100,
            "match_tier": "EXACT",
            "product_variant_id": 42,
            "canonical_product_id": 7,
            "product_created": True,
            "reason": "created",
        }),
        # listings/bulk, flushed by the review item below
        _Response(200, {
            "received": 1,
            "succeeded": 1,
            "duplicates": 0,
            "rejected": 0,
            "failed": 0,
            "results": [{
                "index": 0,
                "status": "created",
                "price_changed": False,
            }],
        }),
        # reviews
        _Response(200, {
            "listing_id": 500,
            "created_count": 1,
            "duplicate_count": 0,
        }),
    )
    crawler = _Crawler()
    pipeline = VextroApiIngestionPipeline(
        base_api_url="http://backend.test",
        ingestion_key="test-key",
        session=session,
        # A batch size above one keeps the listing buffered on purpose.
        batch_size=25,
        crawler=crawler,
    )

    listing_item = VextroCleaningPipeline().process_item(
        {
            "platform": "Daraz",
            "external_id": "1968128816",
            "model": "Realme C100i 4GB/128GB",
            "brand": "Realme",
            "price": 46999.0,
            "original_price": 52999.0,
            "rating": 5.0,
            "review_count": 3,
            "availability": "In Stock",
            "product_url": (
                "https://www.daraz.pk/products/realme-c100i.html"
            ),
            "image_urls": [],
            "specifications": {"RAM": "4GB", "Internal Memory": "128GB"},
            "scrape_timestamp": "2026-10-03T06:00:00+00:00",
        },
        spider=None,
    )
    pipeline.process_item(listing_item, spider=None)

    # Nothing has been flushed yet: the listing is still buffered.
    assert [url for url, _ in session.calls] == [
        "http://backend.test/api/v1/internal/acquisition/resolve-product",
    ]

    review_batch = ReviewBatchItem()
    review_batch["platform"] = "Daraz"
    review_batch["external_listing_id"] = "1968128816"
    review_batch["source_url"] = (
        "https://my.daraz.pk/pdp/review/getReviewList?itemId=1968128816"
    )
    review_batch["reviews"] = [{
        "external_review_id": "84441280428816",
        "rating": 5,
    }]
    pipeline.process_item(review_batch, spider=None)

    assert [url for url, _ in session.calls] == [
        "http://backend.test/api/v1/internal/acquisition/resolve-product",
        "http://backend.test/api/v1/internal/acquisition/listings/bulk",
        "http://backend.test/api/v1/internal/acquisition/reviews",
    ]

    listing_payload = session.calls[1][1]["json"]["items"][0]
    assert listing_payload["original_price"] == 52999.0
    assert listing_payload["rating"] == 5.0
    assert listing_payload["review_count"] == 3

    review_signals = [
        kwargs
        for signal, kwargs in crawler.sent
        if signal is REVIEWS_INGESTED
    ]
    assert review_signals == [{
        "created_count": 1,
        "duplicate_count": 0,
        "spider": None,
    }]


def test_daraz_marks_official_mall_stores_as_verified():
    """Daraz's "Mall" badge identifies a vetted official store."""

    seller = DarazSpider.extract_seller({
        "sellerName": "Samsung Flagship Store",
        "sellerId": "6005425472002",
        "icons": [{"bizType": "coins"}, {"bizType": "lazMall"}],
    })

    assert seller["is_verified"] is True
