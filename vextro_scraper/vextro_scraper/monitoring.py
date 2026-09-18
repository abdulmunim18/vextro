"""Scrapy signal integration for durable acquisition-run monitoring."""

import logging

import requests
from itemadapter import ItemAdapter
from scrapy import signals

from vextro_scraper.pipelines import (
    BULK_ITEM_DELIVERED,
    BULK_ITEM_FAILED,
    BULK_ITEM_QUEUED,
    InvalidMarketplacePriceError,
)


class ScrapeMonitoringExtension:
    """Persist one run per spider and terminal outcomes per emitted item."""

    RUNS_PATH = '/api/v1/internal/acquisition/runs'

    def __init__(
        self,
        base_api_url,
        ingestion_key,
        trigger_type='manual',
        request_timeout=5,
        session=None,
    ):
        self.base_api_url = str(base_api_url).rstrip('/')
        self.ingestion_key = ingestion_key
        self.trigger_type = trigger_type
        self.request_timeout = float(request_timeout)
        self.session = session or requests.Session()
        self.run_id = None
        self.counters = {
            'items_discovered': 0,
            'items_ingested': 0,
            'items_rejected': 0,
            'items_failed': 0,
            'error_count': 0,
        }
        self.bulk_item_ids = set()

    @classmethod
    def from_crawler(cls, crawler):
        extension = cls(
            base_api_url=crawler.settings.get(
                'VEXTRO_API_URL',
                'http://127.0.0.1:8000',
            ),
            ingestion_key=crawler.settings.get('INGESTION_API_KEY'),
            trigger_type=crawler.settings.get(
                'VEXTRO_SCRAPE_TRIGGER',
                'manual',
            ),
            request_timeout=crawler.settings.getfloat(
                'VEXTRO_API_TIMEOUT',
                5,
            ),
        )
        crawler.signals.connect(extension.spider_opened, signals.spider_opened)
        crawler.signals.connect(extension.item_scraped, signals.item_scraped)
        crawler.signals.connect(extension.item_dropped, signals.item_dropped)
        crawler.signals.connect(extension.item_error, signals.item_error)
        crawler.signals.connect(extension.spider_error, signals.spider_error)
        crawler.signals.connect(extension.spider_closed, signals.spider_closed)
        crawler.signals.connect(extension.bulk_item_queued, BULK_ITEM_QUEUED)
        crawler.signals.connect(extension.bulk_item_delivered, BULK_ITEM_DELIVERED)
        crawler.signals.connect(extension.bulk_item_failed, BULK_ITEM_FAILED)
        return extension

    @property
    def headers(self):
        return {
            'X-Ingestion-Key': self.ingestion_key or '',
            'Accept': 'application/json',
        }

    def _safe_message(self, value):
        message = str(value or 'Unknown scraper failure')[:500]
        if self.ingestion_key:
            message = message.replace(self.ingestion_key, '[REDACTED]')
        return message

    @staticmethod
    def _item_context(item):
        adapter = ItemAdapter(item)
        return {
            'external_listing_id': (
                str(
                    adapter.get('external_id')
                    or adapter.get('external_listing_id')
                )[:150]
                if (
                    adapter.get('external_id') is not None
                    or adapter.get('external_listing_id') is not None
                )
                else None
            ),
            'product_url': (
                str(
                    adapter.get('product_url')
                    or adapter.get('source_url')
                )[:2000]
                if (
                    adapter.get('product_url') is not None
                    or adapter.get('source_url') is not None
                )
                else None
            ),
        }

    def _request(self, method, path, *, payload=None):
        try:
            response = self.session.request(
                method,
                f'{self.base_api_url}{path}',
                headers=self.headers,
                json=payload,
                timeout=self.request_timeout,
            )
            if response.status_code not in {200, 201}:
                logging.error(
                    'Scrape monitoring request failed: method=%s path=%s '
                    'status=%s.',
                    method,
                    path,
                    response.status_code,
                )
                return None
            body = response.json()
            return body if isinstance(body, dict) else None
        except (requests.RequestException, ValueError) as exc:
            logging.error(
                'Scrape monitoring backend unavailable: method=%s path=%s '
                'error=%s.',
                method,
                path,
                type(exc).__name__,
            )
            return None

    def spider_opened(self, spider):
        platform = getattr(spider, 'platform_code', None)
        parser_version = getattr(spider, 'parser_version', None)
        if platform not in {'daraz', 'priceoye'} or not parser_version:
            logging.error(
                'Scrape monitoring not started: spider=%s lacks '
                'platform/version metadata.',
                spider.name,
            )
            return

        result = self._request(
            'POST',
            self.RUNS_PATH,
            payload={
                'platform': platform,
                'spider_name': spider.name,
                'trigger_type': self.trigger_type,
                'parser_version': parser_version,
            },
        )
        if result and result.get('id'):
            self.run_id = int(result['id'])
            logging.info(
                'Started persistent scrape run: run_id=%s platform=%s.',
                self.run_id,
                platform,
            )
        else:
            logging.error(
                'Scrape run could not be persisted; continuing with logs.'
            )

    def item_scraped(self, item, response, spider):
        self.counters['items_discovered'] += 1
        if id(item) in self.bulk_item_ids:
            return
        self.counters['items_ingested'] += 1
        if self.run_id is not None:
            self._request(
                'POST',
                f'{self.RUNS_PATH}/{self.run_id}/items/ingested',
            )

    def bulk_item_queued(self, item, spider):
        self.bulk_item_ids.add(id(item))

    def bulk_item_delivered(self, item, result, spider):
        self.counters['items_ingested'] += 1
        if self.run_id is not None:
            self._request(
                'POST',
                f'{self.RUNS_PATH}/{self.run_id}/items/ingested',
            )

    def bulk_item_failed(self, item, exception, spider):
        self._record_error(
            outcome=getattr(exception, 'outcome', 'failed'),
            item=item,
            exception=exception,
            item_discovered=False,
            default_type='listing_ingestion_failed',
            default_stage='ingestion',
        )

    def _record_error(
        self,
        *,
        outcome,
        item,
        exception,
        item_discovered,
        default_type,
        default_stage,
    ):
        if item_discovered:
            self.counters['items_discovered'] += 1
        self.counters[
            'items_rejected' if outcome == 'rejected' else 'items_failed'
        ] += 1
        self.counters['error_count'] += 1

        if self.run_id is None:
            return

        context = self._item_context(item) if item is not None else {
            'external_listing_id': None,
            'product_url': None,
        }
        metadata = getattr(exception, 'metadata', {})
        if not isinstance(metadata, dict):
            metadata = {}

        self._request(
            'POST',
            f'{self.RUNS_PATH}/{self.run_id}/errors',
            payload={
                'outcome': outcome,
                'item_discovered': item_discovered,
                **context,
                'error_type': getattr(
                    exception,
                    'error_type',
                    default_type,
                ),
                'error_stage': getattr(
                    exception,
                    'error_stage',
                    default_stage,
                ),
                'message': self._safe_message(exception),
                'raw_value': getattr(exception, 'raw_value', None),
                'metadata': metadata,
            },
        )

    def item_dropped(self, item, response, exception, spider):
        rejected = (
            isinstance(exception, InvalidMarketplacePriceError)
            or getattr(exception, 'outcome', None) == 'rejected'
        )
        self._record_error(
            outcome='rejected' if rejected else 'failed',
            item=item,
            exception=exception,
            item_discovered=True,
            default_type='item_dropped',
            default_stage='validation' if rejected else 'delivery',
        )

    def item_error(self, item, response, spider, failure):
        exception = getattr(failure, 'value', failure)
        self._record_error(
            outcome='failed',
            item=item,
            exception=exception,
            item_discovered=True,
            default_type='pipeline_error',
            default_stage='delivery',
        )

    def spider_error(self, failure, response, spider):
        exception = getattr(failure, 'value', failure)
        exception_name = type(exception).__name__.lower()
        response_metadata = getattr(response, 'meta', {}) or {}
        is_fetch_error = any(
            marker in exception_name
            for marker in (
                'dns',
                'timeout',
                'connection',
                'http',
            )
        )
        self._record_error(
            outcome='failed',
            item=(
                {
                    'product_url': getattr(response, 'url', None),
                    'external_listing_id': response_metadata.get(
                        'external_listing_id'
                    ),
                }
                if response is not None
                else None
            ),
            exception=exception,
            item_discovered=False,
            default_type=(
                'network_request_failure'
                if is_fetch_error
                else 'spider_error'
            ),
            default_stage='fetch' if is_fetch_error else 'parse',
        )

    def spider_closed(self, spider, reason):
        if self.run_id is None:
            logging.error(
                'Scrape run could not be finalized because no run ID exists.'
            )
            return

        result = self._request(
            'PATCH',
            f'{self.RUNS_PATH}/{self.run_id}',
            payload={
                'crawl_succeeded': reason == 'finished',
                **self.counters,
            },
        )
        if result is None:
            logging.error(
                'Scrape run finalization could not be persisted: '
                'run_id=%s reason=%s counters=%s.',
                self.run_id,
                reason,
                self.counters,
            )
            return

        logging.info(
            'Finalized scrape run: run_id=%s status=%s counters=%s.',
            self.run_id,
            result.get('status'),
            self.counters,
        )
