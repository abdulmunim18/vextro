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