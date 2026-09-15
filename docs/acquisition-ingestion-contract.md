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
the HTTP timeout in seconds.

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

## Error Responses

- `401 Unauthorized` — invalid ingestion key
- `404 Not Found` — unknown platform or product variant
- `409 Conflict` — inactive product or variant
- `422 Unprocessable Entity` — invalid request data

## Transaction Rule

Seller, listing, and price-history changes must run in one database transaction. Any failure must roll back the complete ingestion request.

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
