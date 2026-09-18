from types import SimpleNamespace

from vextro_scraper.monitoring import ScrapeMonitoringExtension
from vextro_scraper.pipelines import (
    AcquisitionDeliveryError,
    InvalidMarketplacePriceError,
)
from vextro_scraper.spiders.daraz_spider import DarazParserError


class FakeResponse:
    def __init__(self, status_code, body):
        self.status_code = status_code
        self.body = body

    def json(self):
        return self.body


class RecordingSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def build_extension(session):
    return ScrapeMonitoringExtension(
        base_api_url='http://backend.test',
        ingestion_key='monitoring-test-key',
        trigger_type='test',
        request_timeout=6,
        session=session,
    )


def test_extension_records_partial_run_lifecycle_and_counters():
    session = RecordingSession(
        FakeResponse(201, {'id': 55, 'status': 'running'}),
        FakeResponse(200, {'id': 55, 'items_ingested': 1}),
        FakeResponse(201, {'id': 1, 'error_type': 'invalid_price'}),
        FakeResponse(201, {'id': 2, 'error_type': 'backend_timeout'}),
        FakeResponse(200, {'id': 55, 'status': 'partial'}),
    )
    extension = build_extension(session)
    spider = SimpleNamespace(
        name='daraz_smartphones',
        platform_code='daraz',
        parser_version='daraz-v1',
    )

    extension.spider_opened(spider)
    extension.item_scraped(
        {'external_id': 'valid-1'},
        response=None,
        spider=spider,
    )
    extension.item_dropped(
        {
            'external_id': 'invalid-1',
            'product_url': 'https://www.daraz.pk/products/invalid-1',
        },
        response=None,
        exception=InvalidMarketplacePriceError(
            'Invalid marketplace price.',
            raw_value="'Call for Price'",
        ),
        spider=spider,
    )
    extension.item_dropped(
        {
            'external_id': 'failed-1',
            'product_url': 'https://www.daraz.pk/products/failed-1',
        },
        response=None,
        exception=AcquisitionDeliveryError(
            'Secure acquisition timed out.',
            error_type='backend_timeout',
            error_stage='delivery',
        ),
        spider=spider,
    )
    extension.spider_closed(spider, reason='finished')

    assert extension.run_id == 55
    assert extension.counters == {
        'items_discovered': 3,
        'items_ingested': 1,
        'items_rejected': 1,
        'items_failed': 1,
        'error_count': 2,
    }
    assert [(call[0], call[1]) for call in session.calls] == [
        ('POST', 'http://backend.test/api/v1/internal/acquisition/runs'),
        (
            'POST',
            'http://backend.test/api/v1/internal/acquisition/'
            'runs/55/items/ingested',
        ),
        (
            'POST',
            'http://backend.test/api/v1/internal/acquisition/runs/55/errors',
        ),
        (
            'POST',
            'http://backend.test/api/v1/internal/acquisition/runs/55/errors',
        ),
        ('PATCH', 'http://backend.test/api/v1/internal/acquisition/runs/55'),
    ]

    start_payload = session.calls[0][2]['json']
    assert start_payload == {
        'platform': 'daraz',
        'spider_name': 'daraz_smartphones',
        'trigger_type': 'test',
        'parser_version': 'daraz-v1',
    }

    invalid_error = session.calls[2][2]['json']
    assert invalid_error['outcome'] == 'rejected'
    assert invalid_error['error_type'] == 'invalid_price'
    assert invalid_error['error_stage'] == 'validation'
    assert invalid_error['raw_value'] == "'Call for Price'"

    failed_error = session.calls[3][2]['json']
    assert failed_error['outcome'] == 'failed'
    assert failed_error['error_type'] == 'backend_timeout'

    finish_payload = session.calls[4][2]['json']
    assert finish_payload == {
        'crawl_succeeded': True,
        **extension.counters,
    }
    assert all(
        call[2]['headers']['X-Ingestion-Key'] == 'monitoring-test-key'
        for call in session.calls
    )


def test_extension_keeps_priceoye_run_metadata_separate():
    session = RecordingSession(
        FakeResponse(201, {'id': 56, 'status': 'running'}),
        FakeResponse(200, {'id': 56, 'status': 'completed'}),
    )
    extension = build_extension(session)
    spider = SimpleNamespace(
        name='priceoye_smartphones',
        platform_code='priceoye',
        parser_version='priceoye-v1',
    )

    extension.spider_opened(spider)
    extension.spider_closed(spider, reason='finished')

    assert session.calls[0][2]['json']['platform'] == 'priceoye'
    assert session.calls[0][2]['json']['parser_version'] == 'priceoye-v1'
    assert session.calls[1][2]['json']['crawl_succeeded'] is True


def test_extension_marks_abnormal_close_as_failed():
    session = RecordingSession(
        FakeResponse(201, {'id': 57, 'status': 'running'}),
        FakeResponse(200, {'id': 57, 'status': 'failed'}),
    )
    extension = build_extension(session)
    spider = SimpleNamespace(
        name='daraz_smartphones',
        platform_code='daraz',
        parser_version='daraz-v1',
    )

    extension.spider_opened(spider)
    extension.spider_closed(spider, reason='closespider_errorcount')

    assert session.calls[1][2]['json']['crawl_succeeded'] is False


def test_extension_records_parser_failure_without_discovered_item():
    session = RecordingSession(
        FakeResponse(201, {'id': 58, 'status': 'running'}),
        FakeResponse(201, {
            'id': 3,
            'error_type': 'invalid_marketplace_response',
        }),
        FakeResponse(200, {'id': 58, 'status': 'partial'}),
    )
    extension = build_extension(session)
    spider = SimpleNamespace(
        name='daraz_smartphones',
        platform_code='daraz',
        parser_version='daraz-v1',
    )

    extension.spider_opened(spider)
    failure = SimpleNamespace(
        value=DarazParserError('Daraz returned malformed JSON.'),
    )
    response = SimpleNamespace(
        url='https://www.daraz.pk/smartphones/?ajax=true',
    )
    extension.spider_error(failure, response, spider)
    extension.spider_closed(spider, reason='finished')

    error_payload = session.calls[1][2]['json']
    assert error_payload['item_discovered'] is False
    assert error_payload['error_type'] == 'invalid_marketplace_response'
    assert error_payload['error_stage'] == 'parse'
    assert extension.counters['items_discovered'] == 0
    assert extension.counters['items_failed'] == 1


def test_extension_records_review_ingestion_failure_context():
    session = RecordingSession(
        FakeResponse(201, {'id': 59, 'status': 'running'}),
        FakeResponse(201, {
            'id': 4,
            'error_type': 'review_listing_unresolved',
        }),
    )
    extension = build_extension(session)
    spider = SimpleNamespace(
        name='priceoye_smartphones',
        platform_code='priceoye',
        parser_version='priceoye-v2-reviews',
    )
    extension.spider_opened(spider)
    extension.item_dropped(
        {
            'external_listing_id': 'priceoye-review-listing',
            'source_url': (
                'https://priceoye.pk/mobiles/test/phone/reviews'
            ),
            'reviews': [{'rating': 5}],
        },
        response=None,
        exception=AcquisitionDeliveryError(
            'Review listing could not be resolved.',
            error_type='review_listing_unresolved',
            error_stage='ingestion',
        ),
        spider=spider,
    )

    error_payload = session.calls[1][2]['json']
    assert error_payload['external_listing_id'] == (
        'priceoye-review-listing'
    )
    assert error_payload['product_url'].endswith('/reviews')
    assert error_payload['error_type'] == 'review_listing_unresolved'
    assert error_payload['error_stage'] == 'ingestion'


def test_bulk_outcomes_count_items_not_http_requests():
    session = RecordingSession(
        FakeResponse(201, {'id': 60, 'status': 'running'}),
        FakeResponse(200, {'id': 60, 'items_ingested': 1}),
        FakeResponse(201, {'id': 5, 'error_type': 'invalid_listing_data'}),
        FakeResponse(201, {'id': 6, 'error_type': 'listing_ingestion_failed'}),
    )
    extension = build_extension(session)
    spider = SimpleNamespace(
        name='priceoye_smartphones',
        platform_code='priceoye',
        parser_version='priceoye-v2-reviews',
    )
    extension.spider_opened(spider)
    items = [
        {
            'external_id': f'bulk-{index}',
            'product_url': f'https://priceoye.pk/bulk-{index}',
        }
        for index in range(3)
    ]
    for item in items:
        extension.bulk_item_queued(item, spider)
        extension.item_scraped(item, None, spider)

    extension.bulk_item_delivered(
        items[0], {'index': 0, 'status': 'created'}, spider
    )
    extension.bulk_item_failed(
        items[1],
        AcquisitionDeliveryError(
            'Listing validation failed.',
            error_type='invalid_listing_data',
            error_stage='validation',
            outcome='rejected',
            metadata={'batch_index': 1, 'platform': 'priceoye'},
        ),
        spider,
    )
    extension.bulk_item_failed(
        items[2],
        AcquisitionDeliveryError(
            'Listing ingestion failed.',
            error_type='listing_ingestion_failed',
            error_stage='ingestion',
            metadata={'batch_index': 2, 'platform': 'priceoye'},
        ),
        spider,
    )

    assert extension.counters == {
        'items_discovered': 3,
        'items_ingested': 1,
        'items_rejected': 1,
        'items_failed': 1,
        'error_count': 2,
    }
    assert len(session.calls) == 4
    assert session.calls[2][2]['json']['metadata']['batch_index'] == 1
    assert session.calls[3][2]['json']['metadata']['batch_index'] == 2
