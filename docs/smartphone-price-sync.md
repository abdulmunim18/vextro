# Smartphone price synchronisation

How a Daraz or PriceOye price reaches a VEXTRO product page, how its history
is recorded, how reviews arrive, and how the twelve-hour refresh is scheduled.

Scope: smartphones on Daraz and PriceOye.

---

## 1. Current price flow

```
marketplace catalog page
  -> spider parses the offer
  -> VextroCleaningPipeline validates and normalizes it
  -> VextroApiIngestionPipeline
       POST /api/v1/internal/acquisition/resolve-product   (which phone is this?)
       POST /api/v1/internal/acquisition/listings/bulk     (here is its offer)
  -> AcquisitionService.ingest_listing
       update the listing in place, keyed by (platform, external_id)
  -> product_listings.current_price
  -> GET /api/v1/products/{id}/listings
  -> MarketplaceListingCard
```

**The source of truth for a displayed marketplace price is
`product_listings.current_price`**, written by the most recent successful
scrape of that listing. Nothing derived, cached or canonical sits in front of
it: the product-detail API reads the listing row directly.

### Source of truth per platform

| | Daraz | PriceOye |
|---|---|---|
| Current price | `listItems[].price` from `/smartphones/?ajax=true` | `offers.price` in the product page's schema.org `Product` block |
| List price | `listItems[].originalPriceShow` | `.retail-price .summary-price` (struck through) |
| Availability | `listItems[].inStock` | `offers.availability`, then embedded variant data, then purchase controls |
| Rating / review count | `listItems[].ratingScore` / `review` | `aggregateRating` |
| Seller | `sellerName` / `sellerId` | not published per offer |
| Specifications | the packed `description` sheet | specification tables |
| Stable code | `sku` / `skuId` | `productID` |

Daraz's AJAX catalog service is the same backend the product page renders
from, so its `price` is the current selling price; there is no separate
detail-page fetch per item. PriceOye's list page and product page can
disagree, so the product page is always fetched and its structured offer
wins over presentation markup.

A list price at or below the selling price is discarded on both platforms:
it would render as a discount that does not exist.

---

## 2. Price history flow

```
price differs from the newest stored observation
  -> INSERT price_history
price equals the newest stored observation
  -> move that observation's captured_at forward
  -> GET /api/v1/products/{id}/price-history   (per listing, oldest first)
  -> PriceHistoryChart (one line per marketplace listing)
```

History is **per listing**, so a Daraz line and a PriceOye line are never
mixed into one misleading series. Four crawls at 120k, 118k, 118k, 115k
produce three observations and a current price of 115k; the repeated 118k
extends its own observation rather than adding a flat duplicate every twelve
hours. Historical lows and buy/wait guidance read the same observations and
are unaffected.

---

## 3. Review flow

```
Daraz    -> my.daraz.pk/pdp/review/getReviewList (JSON, paged)
PriceOye -> <product-url>/reviews (HTML)
  -> POST /api/v1/internal/acquisition/reviews
  -> ReviewService.ingest_batch
       fingerprint -> insert ... on conflict do nothing
  -> refresh product_listings.rating / review_count from stored reviews
```

Reviews are collected for **existing and newly discovered** listings alike;
a listing's age plays no part. Deduplication prefers the marketplace's own
review ID (`reviewRateId` on Daraz) and otherwise falls back to a SHA-256
fingerprint over reviewer, rating, text and date, so re-reading a review
page never duplicates or deletes anything.

A review batch is resolved by `(platform, external listing id)`, so the
ingestion pipeline flushes any buffered listings **before** sending reviews.
Without that, a brand-new product's reviews arrived before its listing
existed and were rejected as `review_listing_unresolved`.

Review collection is bounded: `MAX_REVIEWS_PER_LISTING` per listing and
`MAX_REVIEW_LISTINGS_PER_RUN` listings per crawl, and Daraz items that
advertise no reviews are never requested.

---

## 4. Product matching

Signals are applied strongest first. Only **EXACT** and **HIGH** tiers are
attached automatically; **MEDIUM** and **LOW** go to the pending-match queue
for an administrator.

### Tier EXACT (confidence 100, no scoring)

1. An administrator-approved mapping for this `(platform, external_id)`.
2. **The listing VEXTRO already stores for this `(platform, external_id)`.**
3. An exact SKU code match.

Step 2 is why prices no longer freeze. A listing's identity is the
marketplace's own ID, so catalog growth can never orphan it mid-refresh.

### Weighted signals (everything else)

| Signal | Weight |
|---|---|
| Normalized title vs product name | 35 |
| Brand | 20 |
| Model | 20 |
| RAM | 10 |
| Storage | 10 |
| Colour | 5 |

Confidence is `score / achievable score`, so absent signals do not punish a
candidate. Tiers: EXACT = 100, HIGH >= 90, MEDIUM >= 75, LOW below that.

### Hard vetoes (a candidate is eliminated, not merely demoted)

- **Model code conflict** — "Galaxy A55" never matches "Galaxy A35".
  Title similarity alone rates those at 90%, which is how real Daraz
  listings for a Camon 50 ended up filed under a Camon 30. A shorter code
  that prefixes a longer one ("A55" against a catalog "A556E") is the same
  phone at different precision, not a conflict.
- **Brand conflict** — a different manufacturer is a different product.
- **RAM or storage conflict** — 8/128 is not 8/256.
- **Colour conflict** — a Titan Blue listing is not filed under a Titan Red
  variant. Because colour is variant-level, the resolution service then
  registers the missing colour as a new variant of the *same* phone rather
  than queueing the listing.

RAM and storage are read from the normalized specification sheet before the
title, because marketplace titles mix extended-RAM marketing with physical
capacity ("3GB+5GB Up to 8GB Extended RAM" is a 3GB phone).

### Ambiguity

The ambiguity margin applies **across different canonical products only**.
Several variants of one phone scoring alike just means the listing did not
spell out its configuration; the ranking prefers the variant whose RAM,
storage and colour were confirmed. Treating that as dangerous ambiguity is
what rejected refreshes of listings VEXTRO already held.

---

## 5. New product discovery

Marketplace category pages remain the only discovery source. The database is
never used as the list of things to scrape.

`POST /api/v1/internal/acquisition/resolve-product` handles all three cases:

| Case | Condition | Result |
|---|---|---|
| A | listing known, or EXACT/HIGH match | reuse that variant |
| B | phone known, configuration new | create the variant under the existing product |
| C | phone unknown | create the product, its variant and its specifications |

Creation is refused — and the item queued for an administrator — unless a
brand resolves and the cleaned model name has at least two words. A
canonical product is identified by **brand + model**; RAM, storage and colour
are variant attributes. Before creating anything, the brand-scoped
cross-marketplace identity key is consulted so a Daraz "8GB/256GB" listing
and a PriceOye "8/256" listing land on one product.

### Every catalog page is crawled

PriceOye renders its "next page" control as `<a rel="next">` with no href,
so following that link ended each crawl after the first 36 phones while the
catalog holds several hundred. The crawl now walks `?page=N` until a page
comes back empty, bounded by `PRICEOYE_MAX_CATALOG_PAGES` (default 40). A
run that discovers nothing is recorded as failed rather than completed: an
empty marketplace crawl means the page stopped parsing, which a green
status used to hide.

### The brand is the manufacturer, not the seller

Daraz publishes the selling store in its `brandName` field, so the catalog
collected brands such as "Carrefour", "OPPO Pakistan Official" and "FAYWA
TRADING (PVT) LTD". Each became its own brand row, which split one phone
into several canonical products and filled the public brand filter with
shops.

A marketplace brand value is trusted only once it is recognised as a
manufacturer; otherwise the title decides, and a value that merely names a
shop is dropped rather than registered. Brand aliases canonicalise the
spellings ("Redmi" is Xiaomi, "vivo ." is Vivo), while a small brand VEXTRO
has no alias for is kept as published. Existing rows are repaired by
`backend/scripts/repair_product_brands.py`, which also merges the duplicate
products the store brands created.

### Accessories are not phones

The marketplace smartphones category also serves cables, chargers, covers
and screen protectors. They were registered as canonical products and
filled the pending-match queue. The crawl now drops them, and the resolver
refuses to create a product for one.

Some words only ever name an accessory; others also appear in a phone's own
copy, where they describe what is in the box ("FREE Charger Included", "No
Charger"). Those are matched only when no inclusion wording sits in front of
them, so a phone that advertises its bundled charger stays a phone.
`backend/scripts/retire_accessory_products.py` deactivates the ones already
stored.

### The title is the phone, not the shop

Daraz sellers publish under their own store name and append a stock code:
`Carrefour Samsung Galaxy A07 4+128GB Green-303662`. Taken literally, that
registers a canonical product called "Carrefour Samsung Galaxy A07" which
the same phone on PriceOye can never match, and the catalog then reports
the phone as unavailable on the other marketplace while it is on sale
there.

Both the scraper and the backend therefore reduce a title to the product it
describes before anything is derived from it, matching included. The store
name is removed when it is the listing's own seller (sent to the matching
endpoints as `seller_name`) or when the title opens with shop words and a
known brand follows; a brand token is never removed, so "Samsung Official
Store" cannot eat the "Samsung" in the phone's name. A trailing stock code
goes with it, while a model year such as "Nokia 130 (2023)" stays.

Existing rows are repaired by `backend/scripts/clean_canonical_product_titles.py`
(it reads each product's sellers from its listings), and duplicates the old
behaviour already created are consolidated by
`backend/scripts/merge_cross_marketplace_products.py`. Both are dry runs
until `--apply` is passed.

---

## 6. Update safety

A scrape that failed to read a field must never erase one VEXTRO holds.

Always overwritten (the facts a crawl exists to collect): `current_price`,
`currency`, `is_available`, `last_seen_at`, `product_variant_id`.

Overwritten only when the scrape carried a value: `title`, `product_url`,
`original_price`, `rating`, `review_count`, `warranty`, `seller_id`.
`raw_payload` is merged rather than replaced.

`rating` and `review_count` matter most here: they are recomputed from stored
reviews, and a listing payload that omitted them used to reset the review
aggregate to empty on every refresh.

Rejected outright and logged, never stored: a price of zero or less, a
non-numeric price, an empty title, an invalid URL, a rating outside 0-5.

Reviews follow it too. Daraz answers review requests with an anti-bot page
carrying HTTP 200 rather than an error status, which produced one parse
failure per listing - 149 in a single crawl. The crawl recognises that page,
records it once, and stops asking for reviews for the rest of the run
instead of repeating a request that cannot succeed.

Images follow the same rule. A capture carries its marketplace gallery in
`image_urls`; those become the listing's images and seed the canonical
product's images, which is what the catalog renders. A capture without
images leaves the stored gallery alone and logs the gap, because a scrape
that failed to read a picture must not blank a working product card.
Galleries captured before images were persisted are restored from the
stored scrape payloads by `backend/scripts/backfill_listing_images.py`.

---

## 7. Scheduler

The scheduler is a **dedicated process**. Spiders run as subprocesses, so a
crawl can never block FastAPI request handling, and no Celery or Redis is
involved.

```bash
python -m vextro_scraper.scheduler
```

| Variable | Default | Meaning |
|---|---|---|
| `SCRAPER_ENABLED` | `true` | Run at all |
| `SCRAPER_RUN_ON_STARTUP` | `true` | Crawl once immediately, then fall into the interval |
| `SCRAPER_INTERVAL_HOURS` | `12` | Hours between crawls |
| `SCRAPER_SPIDERS` | `priceoye_smartphones,daraz_smartphones` | Spiders to run, in order |
| `SCRAPER_LOCK_PATH` | `.runtime/scraper-scheduler.lock` | Single-instance lock |

### Only ever one scheduler

Two schedulers would mean two overlapping twelve-hour crawls writing the same
listings. Three separate guards prevent that:

1. An **operating-system file lock**. A second process cannot take it and
   exits immediately without scheduling anything. Because the lock is held by
   the OS, a scheduler killed without cleanup releases it automatically — no
   stale PID file to clear.
2. APScheduler `max_instances=1` with `coalesce=True`, so a crawl that
   overruns its window is never joined or queued behind itself.
3. A process-wide crawl lock, so a manual run cannot overlap a scheduled one.

### Starting it with the project

Set `SCRAPER_AUTOSTART_WITH_API=true` in `backend/.env` and the API launches
the scheduler process on startup and stops it on shutdown. This is safe under
`uvicorn --reload` and with multiple workers: every copy tries the same lock
and only one survives. It is **off by default** so test runs and CI never
start crawling.

### Windows startup (optional)

Nothing is installed on your machine automatically. To have the scheduler
start at login, register the bundled script yourself:

```powershell
$action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -WindowStyle Hidden -File E:\Vextro\scripts\start-vextro-scheduler.ps1"
$trigger = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "VEXTRO Scraper Scheduler" `
  -Action $action -Trigger $trigger -Description "Starts the VEXTRO smartphone crawl scheduler."
```

Remove it again with `Unregister-ScheduledTask -TaskName "VEXTRO Scraper Scheduler"`.

The code does not depend on Task Scheduler: once the process is running, the
startup crawl and the twelve-hour interval are the scheduler's own doing.

### Refreshing one product when its page is opened

The scheduled crawl leaves a price up to one interval old. To close that gap
for the phone someone is actually looking at, the product page calls
`POST /api/v1/products/{id}/refresh` when it opens. If a marketplace's offers
for that product were last confirmed more than
`ON_DEMAND_REFRESH_MAX_AGE_MINUTES` ago, the backend re-reads just that
product's pages and the page picks up the result about ten seconds later.

Nothing is parsed twice. The refresh runs the marketplace's own spider for
one product (`scrapy crawl <spider> -a product_urls=<url>`), so the listing
goes through the same cleaning, matching and ingestion as a full crawl.

| Variable | Default | Meaning |
|---|---|---|
| `ON_DEMAND_REFRESH_ENABLED` | `true` | Refresh at all |
| `ON_DEMAND_REFRESH_MAX_AGE_MINUTES` | `60` | Offers older than this are re-read |
| `ON_DEMAND_REFRESH_COOLDOWN_SECONDS` | `120` | One refresh per product serves everyone opening it meanwhile |
| `ON_DEMAND_REFRESH_MAX_PARALLEL` | `2` | Refreshes running at once |

**Adding a marketplace.** Two things, both small:

1. Its spider accepts `-a product_urls=<url>[,<url>...]` and, given that
   argument, requests only those pages. `PriceoyeSpider.__init__` and
   `start()` are the pattern to copy.
2. One entry in `TARGETED_SPIDERS` in
   `backend/app/services/listing_refresh_service.py`, mapping the platform
   code to the spider name.

A marketplace belongs there only if one product page states its offers.
Daraz does not qualify: its listings come from the category feed and its
product pages load prices through a signed request. Daraz is as fresh as
the scheduled crawl, which takes about two minutes.

---

## 8. Run tracking

Every crawl opens a `scrape_runs` row and finalizes it on close with
`platform`, `spider_name`, `started_at`, `finished_at`, `status`,
`trigger_type`, `parser_version`, and counters for items discovered /
ingested / rejected / failed plus `products_created`, `listings_created`,
`listings_updated`, `price_changes`, `reviews_added` and an `error_summary`
ranking the failure reasons. Individual rejections are kept as `scrape_errors`
rows. Inspect them at `GET /api/v1/internal/acquisition/runs`.

A crawl that is killed or crashes never reports completion, so its row used
to stay `running` forever and the operations dashboard kept showing a crawl
that had stopped weeks earlier. Starting a crawl now closes any older
`running` row for that platform as failed, and
`ScrapeMonitoringService.reconcile_stale_runs` does the same on demand.

---

## 9. Removing seeded demo data

```bash
# Report only (default)
python scripts/remove_demo_catalog.py

# Commit
python scripts/remove_demo_catalog.py --apply
```

Flags: `--include-test-listings` also removes `NOTIFICATION-E2E-*` test
listings; `--force-drop-alerts` deletes demo records even when a user price
alert points at them.

Demo data is identified only by markers the seeder alone writes — demo
product slugs, `daraz-demo-`/`priceoye-demo-` external IDs, `demo: true` or
`source: vextro_demo_seed` in `raw_payload`, `price_history.source =
'demo_seed'`, the two demo seller IDs, and `placehold.co` imagery. Nothing is
deleted by shape, age or guesswork.

Real data survives because a demo product that still carries any non-demo
listing is **kept and de-branded**, never deleted: deleting it would cascade
into genuine listings, price history and reviews. A record a live price alert
watches is preserved and reported instead of deleted, and such a product
deliberately keeps its demo slug so a later `--force-drop-alerts` run can
still find it. Competitor-watchlist entries that would be removed alongside a
demo listing are reported before the commit.
