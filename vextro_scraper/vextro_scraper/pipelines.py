import re
from urllib.parse import urljoin

from itemadapter import ItemAdapter


BRAND_ALIASES = (
    ('Samsung', ('samsung', 'galaxy')),
    ('Apple', ('apple', 'iphone')),
    ('Xiaomi', ('xiaomi', 'redmi', 'poco')),
    ('Infinix', ('infinix',)),
    ('Tecno', ('tecno',)),
    ('Oppo', ('oppo',)),
    ('Vivo', ('vivo',)),
    ('Realme', ('realme',)),
    ('OnePlus', ('oneplus', 'one plus')),
    ('Huawei', ('huawei',)),
    ('Honor', ('honor',)),
    ('Nokia', ('nokia',)),
    ('Google', ('google pixel', 'pixel')),
    ('Motorola', ('motorola', 'moto')),
    ('Itel', ('itel',)),
    ('Sparx', ('sparx',)),
    ('Dcode', ('dcode', 'd-code')),
    ('QMobile', ('qmobile', 'q mobile')),
    ('Faywa', ('faywa',)),
    ('Nothing', ('nothing', 'cmf phone')),
    ('Sego', ('sego',)),
    ('Villaon', ('villaon',)),
    ('LG', ('lg',)),
    ('Balmuda', ('balmuda',)),
    ('Sony', ('sony', 'xperia')),
    ('Sharp', ('sharp', 'aquos')),
    ('ZTE', ('zte', 'nubia')),
    ('VGOTEL', ('vgotel',)),
)


def infer_brand(model, provided_brand=None):
    """Return a clean marketplace brand with title-based fallbacks."""

    if provided_brand:
        cleaned_brand = str(provided_brand).strip()
        if cleaned_brand.lower() not in {
            'n/a', 'na', 'none', 'no brand', 'unbranded',
        }:
            return cleaned_brand

    normalized_model = f" {str(model or '').lower()} "
    for canonical_name, aliases in BRAND_ALIASES:
        if any(
            re.search(rf'(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])', normalized_model)
            for alias in aliases
        ):
            return canonical_name

    return None


def infer_title_specifications(model, specifications=None):
    """Fill common smartphone specifications encoded in listing titles."""

    title = str(model or '')
    inferred = dict(specifications or {})

    patterns = (
        ('ram', (
            r'\b(\d{1,2})\s*GB\s*RAM\b',
            r'\bRAM\s*[:\-]?\s*(\d{1,2})\s*GB\b',
        ), lambda value: f'{value}GB'),
        ('storage_capacity', (
            r'\b(\d{2,4})\s*GB\s*(?:ROM|Storage|Memory)\b',
            r'\b(?:ROM|Storage|Memory)\s*[:\-]?\s*(\d{2,4})\s*GB\b',
        ), lambda value: f'{value}GB'),
        ('battery_capacity', (
            r'\b(\d{3,5})\s*mAh\b',
        ), lambda value: f'{value} mAh'),
        ('display', (
            r'\b(\d{1,2}(?:\.\d{1,2})?)\s*(?:inches|inch|\")\s*(?:display|screen)?',
        ), lambda value: f'{value} inches'),
        ('front_camera', (
            r'\b(\d{1,3})\s*MP\s*Front\s*Camera\b',
            r'\bFront\s*Camera\s*[:\-]?\s*(\d{1,3})\s*MP\b',
        ), lambda value: f'{value}MP'),
    )

    for key, key_patterns, formatter in patterns:
        if key in inferred:
            continue
        for pattern in key_patterns:
            match = re.search(pattern, title, re.I)
            if match:
                inferred[key] = formatter(match.group(1))
                break

    capacity_pair = re.search(
        r'\b(\d{1,2})\s*(?:GB)?\s*[/+|]\s*(\d{2,4})\s*GB\b',
        title,
        re.I,
    )
    if capacity_pair:
        inferred.setdefault('ram', f'{capacity_pair.group(1)}GB')
        inferred.setdefault(
            'storage_capacity',
            f'{capacity_pair.group(2)}GB',
        )

    storage_options = list(dict.fromkeys(
        match.group(1)
        for match in re.finditer(r'\b(\d{2,4})\s*GB\b', title, re.I)
        if int(match.group(1)) >= 32
    ))
    if storage_options:
        inferred.setdefault(
            'storage_options',
            ', '.join(f'{value}GB' for value in storage_options),
        )
    if re.search(r'\bPTA\s*Approved\b', title, re.I):
        inferred.setdefault('pta_status', 'PTA Approved')
    if re.search(r'\bDual\s*SIM\b|\b2\s*SIM\b', title, re.I):
        inferred.setdefault('sim', 'Dual SIM')
    if re.search(r'\bType[ -]?C\b|\bUSB[ -]?C\b', title, re.I):
        inferred.setdefault('charging', 'USB Type-C')
    if re.search(r'\bBluetooth\b', title, re.I):
        inferred.setdefault('connectivity', 'Bluetooth')
    warranty = re.search(r'\b(\d+\s*Year\s*Warranty)\b', title, re.I)
    if warranty:
        inferred.setdefault('warranty', warranty.group(1))

    return inferred

class VextroCleaningPipeline:
    def process_item(self, item, spider):
        adapter = ItemAdapter(item)

        # 1. Clean Price: Convert 'Rs72,999' to numeric 72999.00
        raw_price = adapter.get('price')
        if raw_price:
            clean_price = re.sub(r'[^\d.]', '', raw_price)
            adapter['price'] = float(clean_price) if clean_price else 0.0

        # 2. Clean Availability: Convert 'In Stock' to Boolean (True/False)
        avail = adapter.get('availability', '')
        adapter['is_available'] = True if 'In Stock' in avail else False

        # 3. Generate External ID: Extract the unique slug from the URL
        url = adapter.get('product_url', '')
        if url and not adapter.get('external_id'):
            # Example: grabs "xiaomi-redmi-note-14-pro" from the end of the URL
            adapter['external_id'] = url.rstrip('/').split('/')[-1]

        # 4. Normalize and deduplicate gallery URLs while preserving order.
        normalized_images = []
        for image_url in adapter.get('image_urls') or []:
            if not isinstance(image_url, str) or not image_url.strip():
                continue

            normalized_url = urljoin(url, image_url.strip())
            if (
                normalized_url.startswith(('http://', 'https://'))
                and normalized_url not in normalized_images
            ):
                normalized_images.append(normalized_url)

        adapter['image_urls'] = normalized_images

        adapter['brand'] = infer_brand(
            adapter.get('model'),
            adapter.get('brand'),
        )

        # 5. Keep API-safe, consistently named specification pairs.
        normalized_specifications = {}
        source_specifications = infer_title_specifications(
            adapter.get('model'),
            adapter.get('specifications'),
        )
        for label, value in source_specifications.items():
            normalized_label = re.sub(
                r'[^a-z0-9]+',
                '_',
                str(label).strip().lower(),
            ).strip('_')
            if not normalized_label or value in (None, ''):
                continue

            if isinstance(value, (list, tuple, set)):
                normalized_value = ', '.join(
                    str(part).strip()
                    for part in value
                    if str(part).strip()
                )
            else:
                normalized_value = str(value).strip()

            if normalized_value:
                normalized_specifications[normalized_label[:80]] = (
                    normalized_value[:2000]
                )

        adapter['specifications'] = normalized_specifications

        return item
import requests
import logging

# ... (Your existing VextroCleaningPipeline stays here) ...

class VextroApiIngestionPipeline:
    def __init__(self):
        self.base_api_url = 'http://localhost:8000/api/v1/ingest/'
        self.warehouse_url = 'http://localhost:8000/api/v1/warehouse/scrape-runs'
        self.run_id = None
        self.items_scraped = 0
        self.items_failed = 0

    def open_spider(self, spider):
        platform_name = getattr(spider, 'platform', spider.name.capitalize())
        try:
            res = requests.post(
                f"{self.warehouse_url}/start",
                json={'platform': platform_name, 'triggered_by': 'PIPELINE'},
                timeout=5,
            )
            if res.status_code in [200, 201]:
                data = res.json()
                self.run_id = data.get('id')
                logging.info(f"📊 Registered Warehouse ScrapeRun #{self.run_id} for {platform_name}")
        except requests.exceptions.RequestException as e:
            logging.warning(f"⚠️ Could not register ScrapeRun: {e}")

    def close_spider(self, spider):
        if not self.run_id:
            return
        status_str = "SUCCESS" if self.items_failed == 0 else "FAILED"
        try:
            requests.post(
                f"{self.warehouse_url}/{self.run_id}/finish",
                json={
                    'status': status_str,
                    'items_scraped': self.items_scraped,
                    'items_failed': self.items_failed,
                    'error_message': None if self.items_failed == 0 else f"{self.items_failed} items failed during ingestion",
                },
                timeout=5,
            )
            logging.info(f"🏁 Finished Warehouse ScrapeRun #{self.run_id} ({self.items_scraped} scraped, {self.items_failed} failed)")
        except requests.exceptions.RequestException as e:
            logging.warning(f"⚠️ Could not update ScrapeRun #{self.run_id}: {e}")

    def process_item(self, item, spider):
        payload = dict(item)
        platform_code = payload.get('platform', 'unknown').lower()
        api_url = f"{self.base_api_url}{platform_code}"

        try:
            response = requests.post(api_url, json=payload, timeout=5)
            if response.status_code in [200, 201]:
                self.items_scraped += 1
                logging.info(f"✅ Successfully ingested: {payload.get('model')}")
            else:
                self.items_failed += 1
                logging.error(f"❌ Failed to ingest {payload.get('model')}. Status: {response.status_code}")
        except requests.exceptions.RequestException as e:
            self.items_failed += 1
            logging.warning(f"⚠️ Backend offline or unreachable: {e}")

        return item

