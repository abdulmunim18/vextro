from datetime import datetime
from pathlib import Path
import sys

import pytest
import requests
from scrapy.exceptions import DropItem


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPOSITORY_ROOT / 'backend'

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.acquisition import AcquisitionListingInput
from vextro_scraper.pipelines import (
    AcquisitionDeliveryError,
    BULK_ITEM_DELIVERED,
    BULK_ITEM_FAILED,
    BULK_ITEM_QUEUED,
    VextroApiIngestionPipeline,
)


class FakeResponse:
    def __init__(self, status_code, body=None, malformed=False):
        self.status_code = status_code
        self.body = body
        self.malformed = malformed

    def json(self):
        if self.malformed:
            raise ValueError('not JSON')
        return self.body


class RecordingSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class RecordingSignals:
    def __init__(self):
        self.events = []

    def send_catch_log(self, signal, **kwargs):
        self.events.append((signal, kwargs))


class FakeCrawler:
    def __init__(self):
        self.signals = RecordingSignals()


def build_clean_item():
    return {
        'platform': 'Daraz',
        'external_id': 'daraz-secure-123',
        'model': 'Samsung Galaxy A55 8GB RAM 256GB ROM Black',
        'brand': 'Samsung',
        'price': 120000.0,
        'currency': 'PKR',
        'product_url': 'https://www.daraz.pk/products/a55.html',
        'availability': 'In Stock',
        'is_available': True,
        'seller': 'Daraz Seller',
        'color': 'Black',
        'variant': '8GB/256GB',
        'warranty': '1 Year Brand Warranty',
        'image_urls': ['https://static.daraz.pk/a55.jpg'],
        'specifications': {
            'ram': '8GB',
            'storage_capacity': '256GB',
        },
        'scrape_timestamp': '2026-09-14T12:00:00+00:00',
    }


def build_pipeline(session):
    return VextroApiIngestionPipeline(
        base_api_url='http://backend.test',
        ingestion_key='test-ingestion-key',
        request_timeout=7,
        session=session,
        batch_size=1,
    )


def bulk_result(*, listing_id=90, status='created'):
    return {
        'received': 1,
        'succeeded': int(status in {'created', 'updated'}),
        'duplicates': int(status == 'duplicate'),
        'rejected': 0,
        'failed': 0,
        'results': [{
            'index': 0,
            'status': status,
            'listing_id': listing_id,
            'price_history_created': status != 'duplicate',
            'alerts_triggered': 0,
            'competitor_alerts_triggered': 0,
        }],
    }


def test_pipeline_requires_environment_backed_ingestion_key():
    class FakeSettings:
        @staticmethod
        def get(name, default=None):
            values = {
                'VEXTRO_API_URL': 'http://backend.test',
                'INGESTION_API_KEY': None,
            }
            return values.get(name, default)

        @staticmethod
        def getfloat(name, default=None):
            return default

    class FakeCrawler:
        settings = FakeSettings()

    with pytest.raises(RuntimeError, match='INGESTION_API_KEY'):
        VextroApiIngestionPipeline.from_crawler(FakeCrawler())


def test_pipeline_matches_then_uses_secure_listing_contract():
    session = RecordingSession(
        FakeResponse(200, {
            'matched': True,
            'confidence': 96,
            'product_variant_id': 42,
            'canonical_product_id': 7,
            'reason': 'matched',
        }),
        FakeResponse(200, bulk_result()),
    )
    pipeline = build_pipeline(session)
    item = build_clean_item()

    assert pipeline.process_item(item, spider=None) is item

    assert [call[0] for call in session.calls] == [
        'http://backend.test/api/v1/internal/acquisition/match-product',
        'http://backend.test/api/v1/internal/acquisition/listings/bulk',
    ]
    assert all(
        '/api/v1/ingest/' not in call[0]
        for call in session.calls
    )
    assert all(
        call[1]['headers']['X-Ingestion-Key']
        == 'test-ingestion-key'
        for call in session.calls
    )
    assert all(call[1]['timeout'] == 7 for call in session.calls)

    match_payload = session.calls[0][1]['json']
    assert match_payload == {
        'platform_code': 'daraz',
        'external_id': 'daraz-secure-123',
        'title': 'Samsung Galaxy A55 8GB RAM 256GB ROM Black',
        'brand': 'Samsung',
        'model': None,
        'ram_gb': 8,
        'storage_gb': 256,
        'color': 'Black',
    }

    listing_payload = session.calls[1][1]['json']['items'][0]
    validated = AcquisitionListingInput.model_validate(listing_payload)

    assert validated.platform_code == 'daraz'
    assert validated.product_variant_id == 42
    assert validated.external_id == 'daraz-secure-123'
    assert float(validated.current_price) == 120000.0
    assert validated.seller is not None
    assert validated.seller.name == 'Daraz Seller'
    assert validated.scraped_at.tzinfo is not None


def test_valid_priceoye_price_uses_secure_listing_contract():
    session = RecordingSession(
        FakeResponse(200, {
            'matched': True,
            'confidence': 94,
            'product_variant_id': 43,
            'canonical_product_id': 8,
            'reason': 'matched',
        }),
        FakeResponse(200, bulk_result(listing_id=91)),
    )
    item = {
        **build_clean_item(),
        'platform': 'PriceOye',
        'external_id': 'priceoye-secure-123',
        'product_url': 'https://priceoye.pk/mobiles/samsung/a55',
        'price': 119999.5,
    }

    build_pipeline(session).process_item(item, spider=None)

    listing_payload = session.calls[1][1]['json']['items'][0]
    validated = AcquisitionListingInput.model_validate(listing_payload)
    assert validated.platform_code == 'priceoye'
    assert validated.product_variant_id == 43
    assert float(validated.current_price) == 119999.5


@pytest.mark.parametrize('status_code', [401, 403, 422, 500])
def test_pipeline_rejects_failed_secure_api_delivery(status_code):
    session = RecordingSession(
        FakeResponse(status_code, {'detail': 'rejected'}),
    )

    with pytest.raises(AcquisitionDeliveryError):
        build_pipeline(session).process_item(
            build_clean_item(),
            spider=None,
        )

    assert len(session.calls) == 1


def test_pipeline_does_not_ingest_an_unmatched_product():
    session = RecordingSession(
        FakeResponse(200, {
            'matched': False,
            'confidence': 54,
            'product_variant_id': None,
            'reason': 'No safe automatic match.',
        }),
        FakeResponse(201, {
            'id': 81,
            'platform_code': 'daraz',
            'external_id': 'daraz-secure-123',
            'status': 'pending',
        }),
    )

    with pytest.raises(DropItem):
        build_pipeline(session).process_item(
            build_clean_item(),
            spider=None,
        )

    assert len(session.calls) == 2
    assert session.calls[0][0].endswith('/match-product')
    assert session.calls[1][0].endswith('/pending-matches')
    pending_payload = session.calls[1][1]['json']
    assert pending_payload['external_id'] == 'daraz-secure-123'
    assert pending_payload['match_confidence'] == 54
    assert 'product_variant_id' not in pending_payload['listing_payload']


def test_pipeline_rejects_timeout_and_malformed_response():
    timeout_session = RecordingSession(requests.Timeout())

    with pytest.raises(AcquisitionDeliveryError):
        build_pipeline(timeout_session).process_item(
            build_clean_item(),
            spider=None,
        )

    malformed_session = RecordingSession(
        FakeResponse(200, malformed=True),
    )

    with pytest.raises(AcquisitionDeliveryError):
        build_pipeline(malformed_session).process_item(
            build_clean_item(),
            spider=None,
        )


def test_pipeline_adds_timezone_to_legacy_naive_timestamp():
    payload = VextroApiIngestionPipeline._build_listing_payload(
        {
            **build_clean_item(),
            'scrape_timestamp': '2026-09-14T12:00:00',
        },
        product_variant_id=42,
    )

    parsed_timestamp = datetime.fromisoformat(payload['scraped_at'])
    assert parsed_timestamp.tzinfo is not None


def test_pipeline_delivers_review_batch_without_product_matching():
    session = RecordingSession(
        FakeResponse(200, {
            'platform_code': 'priceoye',
            'listing_id': 91,
            'seller_id': None,
            'created_count': 1,
            'duplicate_count': 0,
            'items': [],
        }),
    )
    item = {
        'platform': 'PriceOye',
        'external_listing_id': 'priceoye-secure-123',
        'source_url': (
            'https://priceoye.pk/mobiles/test/phone/reviews'
        ),
        'reviews': [{
            'rating': 5,
            'review_text': 'Sanitized review',
        }],
    }

    assert build_pipeline(session).process_item(item, None) is item
    assert len(session.calls) == 1
    assert session.calls[0][0].endswith('/acquisition/reviews')
    assert session.calls[0][1]['json']['platform_code'] == 'priceoye'


def test_listing_buffer_submits_three_three_and_final_one():
    responses = []
    next_listing_id = 100
    for item_index in range(7):
        responses.append(FakeResponse(200, {
            'matched': True,
            'confidence': 95,
            'product_variant_id': 42,
            'canonical_product_id': 7,
            'reason': 'matched',
        }))
        if item_index in {2, 5}:
            responses.append(FakeResponse(200, {
                'received': 3,
                'succeeded': 3,
                'duplicates': 0,
                'rejected': 0,
                'failed': 0,
                'results': [
                    {
                        'index': index,
                        'status': 'created',
                        'listing_id': next_listing_id + index,
                    }
                    for index in range(3)
                ],
            }))
            next_listing_id += 3
    responses.append(FakeResponse(200, bulk_result(listing_id=106)))
    session = RecordingSession(*responses)
    pipeline = VextroApiIngestionPipeline(
        base_api_url='http://backend.test',
        ingestion_key='test-ingestion-key',
        request_timeout=7,
        session=session,
        batch_size=3,
    )

    for index in range(7):
        item = {**build_clean_item(), 'external_id': f'buffered-{index}'}
        assert pipeline.process_item(item, spider=None) is item
    pipeline.close_spider(spider=None)

    bulk_calls = [
        call for call in session.calls
        if call[0].endswith('/acquisition/listings/bulk')
    ]
    assert [len(call[1]['json']['items']) for call in bulk_calls] == [3, 3, 1]
    assert pipeline.listing_buffer == []


def test_whole_bulk_http_failure_emits_failure_for_every_item():
    session = RecordingSession(
        FakeResponse(200, {
            'matched': True,
            'confidence': 95,
            'product_variant_id': 42,
            'canonical_product_id': 7,
            'reason': 'matched',
        }),
        FakeResponse(200, {
            'matched': True,
            'confidence': 95,
            'product_variant_id': 42,
            'canonical_product_id': 7,
            'reason': 'matched',
        }),
        FakeResponse(500, {'detail': 'internal failure'}),
    )
    crawler = FakeCrawler()
    pipeline = VextroApiIngestionPipeline(
        base_api_url='http://backend.test',
        ingestion_key='test-ingestion-key',
        session=session,
        batch_size=2,
        crawler=crawler,
    )
    items = [
        {**build_clean_item(), 'external_id': f'failed-bulk-{index}'}
        for index in range(2)
    ]
    for item in items:
        assert pipeline.process_item(item, spider=None) is item

    signals = [event[0] for event in crawler.signals.events]
    assert signals.count(BULK_ITEM_QUEUED) == 2
    assert signals.count(BULK_ITEM_FAILED) == 2
    assert BULK_ITEM_DELIVERED not in signals
    failures = [
        event[1]['exception']
        for event in crawler.signals.events
        if event[0] is BULK_ITEM_FAILED
    ]
    assert all(error.error_type == 'backend_server_error' for error in failures)


@pytest.mark.parametrize('status_code', [404, 422, 500])
def test_pipeline_marks_review_delivery_failures(status_code):
    session = RecordingSession(
        FakeResponse(status_code, {'detail': 'rejected'}),
    )
    item = {
        'platform': 'PriceOye',
        'external_listing_id': 'missing-listing',
        'source_url': 'https://priceoye.pk/mobiles/test/reviews',
        'reviews': [{'rating': 5}],
    }

    with pytest.raises(AcquisitionDeliveryError) as captured:
        build_pipeline(session).process_item(item, None)

    expected = (
        'review_listing_unresolved'
        if status_code == 404
        else (
            'review_validation_failure'
            if status_code == 422
            else 'review_ingestion_failure'
        )
    )
    assert captured.value.error_type == expected
    assert captured.value.error_stage == 'ingestion'


def test_structured_source_payloads_name_the_option_and_allow_catalog_create():
    """PriceOye variant items carry their option into title and matcher.

    One product page yields several listings now, so the listing title
    must name the colour and storage option, and the match request
    must opt in to catalog creation so a phone the catalog has never
    seen (or a missing configuration) is added instead of parked.
    """

    item = {
        'platform': 'PriceOye',
        'structured_source': True,
        'external_id': 'infinix-gt-50-pro--red_blaze--256gb-12gb-ram',
        'model': 'Infinix GT 50 Pro',
        'brand': 'Infinix',
        'color': 'Red Blaze',
        'variant': '256GB - 12GB RAM',
        'price': 162999.0,
        'original_price': 189999.0,
        'is_available': True,
        'rating': 5,
        'review_count': 1,
        'stock_quantity': 3,
        'product_url': 'https://priceoye.pk/mobiles/infinix/infinix-gt-50-pro',
        'scrape_timestamp': '2026-10-02T10:00:00+00:00',
        'specifications': {'ram': '12GB', 'storage_capacity': '256GB'},
        'image_urls': ['https://images.priceoye.pk/a-500x500.webp'],
    }

    match_payload = VextroApiIngestionPipeline._build_match_payload(item)
    assert match_payload['title'] == 'Infinix GT 50 Pro'
    assert match_payload['color'] == 'Red Blaze'
    assert match_payload['ram_gb'] == 12
    assert match_payload['storage_gb'] == 256
    assert match_payload['allow_catalog_create'] is True
    assert match_payload['specifications']['ram'] == '12GB'

    listing_payload = VextroApiIngestionPipeline._build_listing_payload(
        item, 113,
    )
    assert listing_payload['title'] == (
        'Infinix GT 50 Pro (Red Blaze, 256GB - 12GB RAM)'
    )
    assert listing_payload['original_price'] == 189999.0
    assert listing_payload['rating'] == 5
    assert listing_payload['review_count'] == 1
    assert listing_payload['raw_payload']['stock_quantity'] == 3
    assert listing_payload['raw_payload']['image_urls'] == [
        'https://images.priceoye.pk/a-500x500.webp',
    ]
    # The payload must still satisfy the backend contract exactly.
    AcquisitionListingInput.model_validate(listing_payload)


def test_free_text_source_does_not_request_catalog_creation():
    """Daraz-style items keep going through manual review when unmatched."""

    match_payload = VextroApiIngestionPipeline._build_match_payload(
        {
            'platform': 'Daraz',
            'external_id': '1966046217',
            'model': 'Infinix GT 50 Pro - 12GB RAM 256GB ROM',
            'color': 'N/A',
            'specifications': {},
        }
    )
    assert 'allow_catalog_create' not in match_payload
