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
    )

    with pytest.raises(DropItem):
        build_pipeline(session).process_item(
            build_clean_item(),
            spider=None,
        )

    assert len(session.calls) == 1
    assert session.calls[0][0].endswith('/match-product')


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
