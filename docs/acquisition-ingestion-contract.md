# VEXTRO Acquisition Ingestion Contract

## Purpose

This contract defines how the VEXTRO scraper sends a normalized Daraz or PriceOye marketplace listing to the FastAPI backend.

The scraper is responsible for collecting permitted marketplace data, parsing platform-specific responses, cleaning prices and basic fields, and providing a matched VEXTRO product variant ID.

The backend is responsible for authenticating the ingestion request, verifying the platform and product variant, creating or updating the seller and marketplace listing, creating a historical price observation, evaluating applicable price alerts, and returning an ingestion summary.

## Endpoint

```http
POST /api/v1/internal/acquisition/listings
```

## Authentication

```http
X-Ingestion-Key: <configured-secret>
```

The ingestion key must be stored in environment variables and must never be committed to Git.

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
- Current and original price must be zero or greater
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

## Initial Implementation Files

```text
backend/app/schemas/acquisition.py
backend/app/repositories/acquisition_repository.py
backend/app/services/acquisition_service.py
backend/app/api/dependencies/ingestion.py
backend/app/api/routes/acquisition.py
backend/tests/test_acquisition.py
```
