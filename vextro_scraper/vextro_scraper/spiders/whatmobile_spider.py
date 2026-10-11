"""WhatMobile: phone ratings and the opinions its visitors post.

WhatMobile.com.pk is a price and specification guide, not a shop. It sells
nothing, so nothing here is an offer. What it has that the marketplaces do
not let anyone collect is a public rating for each phone and a page of
visitor opinions, mostly in Roman Urdu.

Those opinions are not buyer reviews. Anyone can post one, none carries a
star rating of its own, and a share of them are people advertising their own
phone for sale, phone number included. They are collected as community
opinions and kept apart from marketplace reviews; contact numbers are
removed before anything leaves this spider.

WhatMobile lists about 2,500 phones, most of them long discontinued. Only
phones VEXTRO already lists are visited.
"""

import re
from datetime import datetime, timezone

import requests
import scrapy

from vextro_scraper.items import CommunityOpinionsItem
from vextro_scraper.normalizers import optional_text, parse_count, parse_price


BASE_URL = 'https://www.whatmobile.com.pk'

# Pakistani mobile numbers as people type them, and any other long digit
# run that could be one: "0323 4004838", "+92-300-1234567", "03036806902".
CONTACT_NUMBER = re.compile(
    r'(?:\+?92|0)[\s-]?3\d{2}[\s-]?\d{3}[\s-]?\d{4}|\b\d[\d\s-]{8,}\d\b'
)
CONTACT_PLACEHOLDER = '[number removed]'

LOST_LINE_BREAK = re.compile(r'(?<=\S)rn(?=[A-Z0-9])|(?<!\S)rn(?=[A-Z]|\s|$)')

# Words that carry no model identity when a phone name is compared.
NAME_NOISE = frozenset({'mobile', 'mobiles', 'phone', 'smartphone', '5g', '4g'})


def name_key(name):
    """Reduce a phone name to the words that identify the model.

    "Samsung Galaxy A27 5G", "Samsung_Galaxy-A27" and "samsung galaxy a27"
    are one phone; the key ignores case, punctuation, word order and the
    network generation, which the two sites state differently.
    """

    tokens = re.findall(r'[a-z0-9]+', str(name or '').lower())

    return ' '.join(sorted(token for token in tokens if token not in NAME_NOISE))


def restore_line_breaks(text):
    """Turn the stray "rn" WhatMobile prints for a line break into a space.

    The site loses the backslashes of "\\r\\n", leaving "mobilernPrice" or
    a trailing " rn". Only an "rn" glued to a capital or a digit, or standing
    alone, is touched, so "return" and "modern" stay as written.
    """

    return LOST_LINE_BREAK.sub(' ', text or '')


def remove_contact_numbers(text):
    """Return ``(text, removed)`` with phone numbers replaced."""

    cleaned, count = CONTACT_NUMBER.subn(
        CONTACT_PLACEHOLDER,
        restore_line_breaks(text),
    )

    return ' '.join(cleaned.split()), count > 0


class WhatmobileSpider(scrapy.Spider):
    name = 'whatmobile_opinions'
    platform_code = 'whatmobile'
    parser_version = 'whatmobile-v1-opinions'
    allowed_domains = ['whatmobile.com.pk']

    custom_settings = {
        'USER_AGENT': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ),
        'DOWNLOAD_DELAY': 1.5,
    }

    NAME_SEPARATOR = '|'

    def __init__(self, phone_names=None, *args, **kwargs):
        """Collect opinions for VEXTRO's phones, or only for those named.

        ``-a phone_names="<name>[|<name>...]"`` narrows a run to those
        phones, for a quick check or a refresh of one product.
        """

        super().__init__(*args, **kwargs)
        self.targeted_names = [
            name
            for name in (
                part.strip()
                for part in str(phone_names or '').split(self.NAME_SEPARATOR)
            )
            if len(name) >= 3
        ]
        # name key -> the name VEXTRO uses for that phone.
        self.wanted = {}

    async def start(self):
        names = self.targeted_names or self.catalog_phone_names()
        self.wanted = {
            name_key(name): name for name in names if name_key(name)
        }

        if not self.wanted:
            self.logger.warning(
                'WhatMobile crawl has no phones to look for; nothing to do.'
            )
            return

        # A phone's page is found through its brand's listing, so only the
        # brands VEXTRO's phones belong to are opened.
        brands = sorted({
            self.brand_slug(name) for name in self.wanted.values()
        } - {''})

        for brand in brands:
            yield scrapy.Request(
                f'{BASE_URL}/{brand}_Mobiles_Prices',
                callback=self.parse_brand,
                cb_kwargs={'brand': brand},
            )

    @staticmethod
    def brand_slug(name):
        """Return WhatMobile's spelling of a phone's brand, for its URL."""

        first = re.sub(r'[^A-Za-z0-9]', '', str(name or '').split(' ')[0])

        return first[:1].upper() + first[1:] if first else ''

    def catalog_phone_names(self):
        """Return the names of the phones VEXTRO lists as on sale."""

        crawler = getattr(self, 'crawler', None)
        if crawler is None:
            return []

        settings = crawler.settings
        base_url = str(
            settings.get('VEXTRO_API_URL', 'http://127.0.0.1:8000')
        ).rstrip('/')
        names = []
        page = 1

        try:
            while True:
                response = requests.get(
                    f'{base_url}/api/v1/products',
                    params={
                        'page': page,
                        'page_size': 100,
                        'is_available': 'true',
                    },
                    timeout=settings.getfloat('VEXTRO_API_TIMEOUT', 20),
                )
                response.raise_for_status()
                body = response.json()
                items = body.get('items') or []
                names.extend(
                    item['name'] for item in items if item.get('name')
                )

                if not items or page >= int(body.get('total_pages') or 0):
                    break

                page += 1
        except (requests.RequestException, ValueError, KeyError) as error:
            self.logger.warning(
                'WhatMobile crawl skipped: VEXTRO catalogue could not be '
                'read (%s).',
                type(error).__name__,
            )
            return []

        return names

    def parse_brand(self, response, brand):
        """Follow the brand's phones that VEXTRO lists."""

        prefix = f'{brand}_'.lower()
        seen = set()

        for href in response.css('a::attr(href)').getall():
            slug = href.strip().lstrip('/')

            if (
                not slug.lower().startswith(prefix)
                or not re.fullmatch(r'[A-Za-z0-9]+_[A-Za-z0-9.+-]+', slug)
                or slug in seen
            ):
                continue

            seen.add(slug)
            catalog_name = self.wanted.get(name_key(slug))

            if catalog_name is None:
                continue

            yield scrapy.Request(
                f'{BASE_URL}/{slug}',
                callback=self.parse_phone,
                cb_kwargs={'slug': slug, 'catalog_name': catalog_name},
            )

    def parse_phone(self, response, slug, catalog_name):
        """Read the phone's rating, then fetch its opinions page."""

        source = response.text
        item = CommunityOpinionsItem()
        item['source'] = self.platform_code
        item['product_name'] = optional_text(
            response.css('h1 ::text').get(),
            max_length=255,
        ) or catalog_name
        item['catalog_name'] = catalog_name
        item['brand'] = optional_text(
            self._structured_value(source, r'"brand"\s*:\s*\{[^}]*"name"'),
            max_length=120,
        ) or slug.split('_', 1)[0]
        item['source_url'] = response.url

        rating = self._structured_value(source, r'"ratingValue"')
        try:
            item['rating'] = round(float(rating), 2) if rating else None
        except ValueError:
            item['rating'] = None

        item['rating_count'] = parse_count(
            self._structured_value(source, r'"reviewCount"')
        ) or 0
        # WhatMobile's price is the manufacturer's listed retail price; it
        # is a reference figure, not something anyone can buy at.
        item['reference_price'] = parse_price(
            self._structured_value(source, r'"[Pp]rice"')
        )
        item['opinions'] = []
        item['scrape_timestamp'] = datetime.now(timezone.utc).isoformat()

        if not item['rating_count']:
            yield item
            return

        yield scrapy.Request(
            f'{BASE_URL}/{slug}_Reviews_0',
            callback=self.parse_opinions,
            errback=self.opinions_unavailable,
            cb_kwargs={'item': item},
            meta={'item': item},
        )

    @staticmethod
    def _structured_value(source, key_pattern):
        """Read one value from the page's product data block.

        The block is not valid JSON (it carries raw line breaks), so the
        fields are read individually.
        """

        match = re.search(
            key_pattern + r'\s*:\s*"?([^",}\n]+)"?',
            source,
        )

        return match.group(1).strip() if match else None

    def _max_opinions(self):
        crawler = getattr(self, 'crawler', None)

        if crawler is None:
            return 50

        return max(0, crawler.settings.getint('MAX_OPINIONS_PER_PHONE', 50))

    def parse_opinions(self, response, item):
        """Read the opinions: a text row, then its date-and-author row."""

        opinions = []

        for position, text_row in enumerate(
            response.css('tr.Borders3'),
            start=1,
        ):
            if len(opinions) >= self._max_opinions():
                break

            raw_text = ' '.join(
                part.strip()
                for part in text_row.css('::text').getall()
                if part.strip()
            )
            text, removed = remove_contact_numbers(raw_text)

            if not text:
                continue

            # WhatMobile prints the text first and the date and author in
            # the row below it; that row is recognised by its two icons.
            header = text_row.xpath(
                'following-sibling::tr[.//img[contains(@src, "uname")]][1]'
            )
            posted_on = optional_text(
                ' '.join(
                    header.xpath(
                        './/td[.//img[contains(@src, "upost")]]//text()'
                    ).getall()
                ),
                max_length=20,
            )
            author = optional_text(
                ' '.join(
                    header.xpath(
                        './/td[.//img[contains(@src, "uname")]]//text()'
                    ).getall()
                ),
                max_length=120,
            )

            opinions.append({
                'position': position,
                'author': author,
                'posted_at': self._parse_date(posted_on),
                'text': text[:2000],
                'contact_removed': removed,
            })

        item['opinions'] = opinions
        item['opinions_url'] = response.url

        yield item

    def opinions_unavailable(self, failure):
        """Deliver the rating even when the opinions page would not load."""

        request = getattr(failure, 'request', None)
        item = request.meta.get('item') if request is not None else None

        if item is not None:
            yield item

    @staticmethod
    def _parse_date(value):
        """Turn WhatMobile's ``dd-mm-yyyy`` into an ISO timestamp."""

        try:
            return datetime.strptime(
                str(value or '').strip(),
                '%d-%m-%Y',
            ).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            return None
