"""Delivering a guide site's rating and opinions to the backend."""

import pytest

from vextro_scraper.items import CommunityOpinionsItem
from vextro_scraper.pipelines import (
    AcquisitionDeliveryError,
    VextroApiIngestionPipeline,
    VextroCleaningPipeline,
)


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

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def build_pipeline(session):
    return VextroApiIngestionPipeline(
        base_api_url='http://backend.test',
        ingestion_key='test-ingestion-key',
        session=session,
    )


def opinions_item():
    return CommunityOpinionsItem(
        source='whatmobile',
        product_name='Infinix Hot 70 Pro',
        catalog_name='Infinix Hot 70 Pro',
        brand='Infinix',
        source_url='https://www.whatmobile.com.pk/Infinix_Hot-70-Pro',
        opinions_url='https://www.whatmobile.com.pk/Infinix_Hot-70-Pro_Reviews_0',
        rating=2.8,
        rating_count=22,
        reference_price=89999.0,
        scrape_timestamp='2026-10-10T18:00:00+00:00',
        opinions=[
            {
                'position': 1,
                'author': 'visitor1',
                'posted_at': '2026-09-18T00:00:00+00:00',
                'text': 'IPS display in this expensive phone.',
                'contact_removed': False,
            },
            {
                'position': 2,
                'author': 'visitor2',
                'posted_at': None,
                'text': 'Sale karna hai rabta [number removed]',
                'contact_removed': True,
            },
        ],
    )


def test_an_opinions_item_skips_the_listing_checks():
    """It has no price or seller title for the cleaning step to judge."""

    item = opinions_item()

    assert VextroCleaningPipeline().process_item(item, None) is item


def test_opinions_go_to_their_own_endpoint_not_the_listing_one():
    session = RecordingSession(FakeResponse(200, {
        'matched': True,
        'canonical_product_id': 7,
        'created_count': 2,
        'duplicate_count': 0,
    }))
    item = opinions_item()

    assert build_pipeline(session).process_item(item, None) is item

    assert len(session.calls) == 1
    url, request = session.calls[0]
    assert url == (
        'http://backend.test/api/v1/internal/acquisition/community-opinions'
    )
    assert request['headers']['X-Ingestion-Key'] == 'test-ingestion-key'

    payload = request['json']
    assert payload['source'] == 'whatmobile'
    assert payload['catalog_name'] == 'Infinix Hot 70 Pro'
    assert payload['rating'] == 2.8
    assert payload['rating_count'] == 22
    assert payload['reference_price'] == 89999.0
    assert [opinion['text'] for opinion in payload['opinions']] == [
        'IPS display in this expensive phone.',
        'Sale karna hai rabta [number removed]',
    ]
    assert payload['opinions'][1]['contact_removed'] is True


def test_a_page_for_a_phone_vextro_does_not_list_is_recorded_as_rejected():
    """Guide-site pages never create products, so this is not a failure."""

    session = RecordingSession(FakeResponse(200, {'matched': False}))

    with pytest.raises(AcquisitionDeliveryError) as raised:
        build_pipeline(session).process_item(opinions_item(), None)

    assert raised.value.error_type == 'product_unmatched'
    assert raised.value.outcome == 'rejected'
