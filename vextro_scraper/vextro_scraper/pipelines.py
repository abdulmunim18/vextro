import re
from itemadapter import ItemAdapter

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
        if url:
            # Example: grabs "xiaomi-redmi-note-14-pro" from the end of the URL
            adapter['external_id'] = url.rstrip('/').split('/')[-1]

        return item
import requests
import logging

# ... (Your existing VextroCleaningPipeline stays here) ...

class VextroApiIngestionPipeline:
    def __init__(self):
        # This is the local URL your backend team will create.
        # Once deployed, this will change to your live server URL.
        self.api_url = 'http://localhost:8000/api/v1/ingest/priceoye'

    def process_item(self, item, spider):
        # Convert Scrapy item to a standard dictionary
        payload = dict(item)

        try:
            # Fire the data to the backend via POST request
            response = requests.post(self.api_url, json=payload, timeout=5)

            # Log success or failure directly in your VS Code terminal
            if response.status_code in [200, 201]:
                logging.info(f"✅ Successfully ingested: {payload.get('model')}")
            else:
                logging.error(f"❌ Failed to ingest {payload.get('model')}. Status: {response.status_code}")
        
        except requests.exceptions.RequestException as e:
            # This triggers if your FastAPI server isn't running yet
            logging.warning(f"⚠️ Backend offline or unreachable: {e}")

        return item