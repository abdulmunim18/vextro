# VEXTRO Acquisition Ingestion Contract

## Purpose

This contract defines how the VEXTRO scraper sends a normalized Daraz or PriceOye marketplace listing to the FastAPI backend.

The scraper is responsible for collecting permitted marketplace data, parsing platform-specific responses, cleaning prices and basic fields, obtaining a safe match through the existing product-matching endpoint, and providing that matched VEXTRO product variant ID to listing ingestion.

The backend is responsible for authenticating the ingestion request, verifying the platform and product variant, creating or updating the seller and marketplace listing, creating a historical price observation, evaluating applicable price alerts, and returning an ingestion summary.

## Endpoint

The active scraper first resolves a canonical variant:

```http
POST /api/v1/internal/acquisition/match-product
```

It then submits the normalized listing:

```http
POST /api/v1/internal/acquisition/listings
```

Scheduled scraper delivery uses the bounded bulk route:

```http
POST /api/v1/internal/acquisition/listings/bulk
```

The single-listing route remains supported for manual diagnosis and backward
compatibility. Both routes execute the same `AcquisitionService` listing
logic.

Both requests use the authentication header below. The older
`/api/v1/ingest/{platform}` API remains deprecated for compatibility and is
not the active Daraz/PriceOye delivery path.

## Authentication

```http
X-Ingestion-Key: <configured-secret>
```

The ingestion key must be stored in environment variables and must never be committed to Git.

The scraper reads the shared `INGESTION_API_KEY` environment variable. Its
backend base URL can be overridden with `VEXTRO_API_URL`; local development
defaults to `http://127.0.0.1:8000`. `VEXTRO_API_TIMEOUT` optionally controls
the HTTP timeout in seconds. `VEXTRO_INGESTION_BATCH_SIZE` controls listing
delivery buffering, defaults to `25`, and is clamped to the backend-supported
range of `1` through `100`.

## Request Body

```json
{
  "platform_code": "daraz",
  "product_variant_id": 1,
  "external_id": "DARAZ-ITEM-10001",
  "title": "Samsung Galaxy A55 8GB 256GB",
  "product_url": "https://www.daraz.pk/products/example",
  "current_price": 124999,
  "original_price": 129999,
  "currency": "PKR",
  "rating": 4.6,
  "review_count": 210,
  "warranty": "1 Year Brand Warranty",
  "is_available": true,
  "scraped_at": "2026-08-06T00:30:00Z",
  "seller": {
    "external_seller_id": "DARAZ-SELLER-501",
    "name": "Example Daraz Seller",
    "profile_url": "https://www.daraz.pk/shop/example",
    "rating": 4.8,
    "review_count": 1250,
    "is_verified": true
  },
  "raw_payload": {
    "source": "daraz",
    "collection_mode": "fixture"
  }
}
```

## Required Fields

- `platform_code`
- `product_variant_id`
- `external_id`
- `title`
- `product_url`
- `current_price`
- `currency`
- `is_available`
- `scraped_at`

## Optional Fields

- `original_price`
- `rating`
- `review_count`
- `warranty`
- `seller`
- `raw_payload`

## Validation Rules

- Supported platforms: `daraz` and `priceoye`
- `product_variant_id` must exist
- Current price must be finite and greater than zero
- Original price, when supplied, must be finite and greater than zero
- Currency must contain exactly three uppercase letters
- Ratings must be between `0` and `5`
- Review counts must be zero or greater
- URLs must use HTTP or HTTPS
- `scraped_at` must be an ISO 8601 timestamp

## Seller Upsert

Find a seller using:

```text
platform_id + external_seller_id
```

When the external seller ID is unavailable, use:

```text
platform_id + normalized seller name
```

## Listing Upsert

Find a listing using:

```text
platform_id + external_id
```

Existing listings must refresh seller, title, URL, prices, rating, reviews, warranty, availability, raw payload, and last-seen time.

## Price History Rule

Every new marketplace capture creates a historical price record.

Retries must not create duplicate history for:

```text
platform_code + external_id + scraped_at
```

## Successful Response

```json
{
  "status": "created",
  "platform_code": "daraz",
  "listing_id": 25,
  "seller_id": 8,
  "price_history_id": 140,
  "listing_created": true,
  "seller_created": false,
  "price_history_created": true,
  "alerts_triggered": 0,
  "captured_at": "2026-08-06T00:30:00Z"
}
```

Possible status values:

```text
created
updated
duplicate
```

## Bulk Listing Contract

The bulk request contains between 1 and 100 raw listing objects. Each object is
validated independently with the existing `AcquisitionListingInput` schema so
one malformed listing does not reject otherwise valid captures:

```json
{
  "items": [
    {
      "platform_code": "daraz",
      "product_variant_id": 1,
      "external_id": "DARAZ-ITEM-10001",
      "title": "Samsung Galaxy A55 8GB 256GB",
      "product_url": "https://www.daraz.pk/products/example",
      "current_price": 124999,
      "currency": "PKR",
      "is_available": true,
      "scraped_at": "2026-08-06T00:30:00Z"
    }
  ]
}
```

Empty batches, batches above 100 items, malformed outer bodies, and invalid
ingestion keys reject the entire HTTP request. A valid outer request returns
one ordered result per item:

```json
{
  "received": 3,
  "succeeded": 1,
  "duplicates": 1,
  "rejected": 0,
  "failed": 1,
  "results": [
    {
      "index": 0,
      "status": "created",
      "platform_code": "daraz",
      "external_id": "DARAZ-ITEM-10001",
      "listing_id": 25,
      "price_history_id": 140,
      "price_history_created": true,
      "alerts_triggered": 1,
      "competitor_alerts_triggered": 0
    },
    {
      "index": 1,
      "status": "duplicate",
      "platform_code": "daraz",
      "external_id": "DARAZ-ITEM-10002",
      "listing_id": 26,
      "price_history_id": 141,
      "price_history_created": false,
      "alerts_triggered": 0,
      "competitor_alerts_triggered": 0
    },
    {
      "index": 2,
      "status": "failed",
      "platform_code": "daraz",
      "external_id": "DARAZ-ITEM-10003",
      "error_code": "product_variant_not_found",
      "error_stage": "ingestion",
      "message": "The requested product variant was not found."
    }
  ]
}
```

`succeeded` counts `created` and `updated`; idempotent captures are reported
separately as `duplicates`. Schema-invalid items are `rejected`. Validated
items that cannot be ingested are `failed`. Error messages are bounded to
known validation/business messages or a generic unexpected-failure message;
stack traces and credentials are never returned.

## Error Responses

- `401 Unauthorized` — invalid ingestion key
- `404 Not Found` — unknown platform or product variant
- `409 Conflict` — inactive product or variant
- `422 Unprocessable Entity` — invalid request data

## Transaction Rule

Seller, listing, and price-history changes must run in one database transaction. Any failure must roll back the complete ingestion request.

Bulk ingestion uses **partial-success semantics**. Every item calls the same
single-listing service, which commits or rolls back its seller, listing,
history, price-alert, and competitor-alert work as one item transaction. A
failed item cannot roll back earlier successful items and cannot leave its own
partial writes. Replaying a batch preserves the existing `(listing,
scraped_at)` capture deduplication and does not create duplicate price history.

The scraper still performs product matching before buffering because the
established ingestion contract accepts a canonical `product_variant_id`.
Matched listings are sent when the configured batch size is reached. Pipeline
shutdown flushes the last partial batch, so a final buffer smaller than the
configured size is not silently discarded. Reviews continue through their
separate bounded review route.

## Persistent Scrape Monitoring

Every normal Daraz and PriceOye spider execution creates one authenticated
`scrape_runs` record through:

```http
POST /api/v1/internal/acquisition/runs
```

The run starts as `running`. Item outcomes are persisted as follows:

- `discovered`: an item reached a terminal pipeline outcome.
- `ingested`: secure acquisition completed successfully, including an
  idempotent duplicate response.
- `rejected`: the item was intentionally dropped because its data was invalid.
- `failed`: processing, matching, delivery, or spider execution failed.

`completed` means the spider closed normally without rejections or failures.
`partial` means it closed normally with at least one rejection or failure.
`failed` means Scrapy reported an abnormal close reason. Every finalized run
receives `finished_at`.

Meaningful errors are written through:

```http
POST /api/v1/internal/acquisition/runs/{run_id}/errors
```

Supported stages are `fetch`, `parse`, `validation`, `matching`, `delivery`,
and `ingestion`. Error text and metadata are bounded, and known credential
fields are redacted. `daraz-v1` and `priceoye-v2-reviews` identify the current
parsers.
The scheduler records `trigger_type=scheduler`; direct `scrapy crawl` commands
default to `manual`.

Recent evidence can be inspected with the same `X-Ingestion-Key` using:

```http
GET /api/v1/internal/acquisition/runs
GET /api/v1/internal/acquisition/runs/{run_id}
```

If the backend itself is unavailable, neither acquisition nor monitoring can
be persisted; the existing console/file logs remain the fallback evidence.

For bulk listings, counters represent item results rather than HTTP request
count. The pipeline emits a queued signal before Scrapy reports the item and
then emits delivered or failed/rejected signals from the corresponding batch
result. A 20-item response containing 18 successful outcomes, one rejection,
and one failure therefore records `ingested += 18`, `rejected += 1`, and
`failed += 1`. Whole-request timeout, authentication, malformed-response, or
backend failures mark every buffered item failed; the batch is never counted
as one successful item. Persisted error metadata is limited to safe batch
index, platform, external listing ID, stage, code, and bounded message.

## Initial Implementation Files

```text
backend/app/schemas/acquisition.py
backend/app/repositories/acquisition_repository.py
backend/app/services/acquisition_service.py
backend/app/api/dependencies/ingestion.py
backend/app/api/routes/acquisition.py
backend/tests/test_acquisition.py
```

## Review acquisition

Review batches use `POST /api/v1/internal/acquisition/reviews` with the same
`X-Ingestion-Key` as listing acquisition. Each bounded request identifies a
supported platform and marketplace external listing ID; the backend resolves
the exact existing listing, derives its seller, normalizes review fields, and
deduplicates using an external review ID or deterministic SHA-256 fingerprint.
See `docs/review-data-foundation.md` for the schema, source capability matrix,
limits, read endpoint, monitoring behavior, and known marketplace limitations.
