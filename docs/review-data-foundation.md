# Review Data Foundation

This module stores normalized marketplace review evidence for later analysis.
It does not calculate sentiment, suspicious-review probability, authenticity,
or seller trust.

## Source capability

| Field | Daraz | PriceOye |
|---|---|---|
| Review text | Unavailable to the current collector | Available per visible review record; a missing value is accepted as a rating-only review |
| Rating | Unavailable to the current collector | Available as 1–5 rendered stars |
| External review ID | Unavailable/unknown | Unavailable in the rendered review record |
| Reviewer display name | Visible on product pages, but unsupported by the current collector | Available |
| Reviewer identifier | Unavailable/unknown | Unavailable |
| Review date | Visible on product pages, but unsupported by the current collector | Available at day precision |
| Helpful votes | Unavailable/unknown | Unavailable |
| Verified purchase | Visible on product pages, but unsupported by the current collector | Available |
| Seller information | Not present in the current category-list collector | Not present on the review record |
| Product rating/count aggregate | Not collected from the current category response | Available on product and review pages |

This classification was based on the existing spiders and saved scrape output,
plus inspection of current public marketplace pages on 2026-09-14. PriceOye's
review DOM exposes `.review-box`, `.user-reivew-name`, `.rating-star`,
`.review-date`, `.user-reivew-description`, and `.verified-user`. No external
review ID, reviewer ID, helpful count, or seller identifier was present in a
review record. Daraz pages visibly contain review data, but the repository only
requests category-list JSON and contains no supported detail/review endpoint or
saved response from which a reliable parser can be built. Daraz extraction is
therefore intentionally not implemented.

## Persistent schema

`raw_reviews` belongs to one `product_listing` and one `platform`. `seller_id`
is copied from that resolved listing and may be null. It stores the external
review ID when available, a SHA-256 fingerprint, reviewer signals, the 1–5
rating, optional text, review time, optional verified/helpful signals, source
URL, bounded raw metadata, and timestamps.

Database constraints enforce a 1–5 rating, non-negative helpful count, a
64-character SHA-256 fingerprint, valid foreign keys, unique
`(platform_id, external_review_id)`, and unique
`(platform_id, review_fingerprint)`.

## Identity and normalization

When `external_review_id` exists, identity is the SHA-256 digest of the
platform and that ID. Otherwise the digest is built from the platform, external
listing ID, reviewer ID/name, rating, normalized review text, and normalized
review timestamp. JSON keys and separators are canonicalized before hashing;
Python's randomized `hash()` is never used.

Text normalization removes HTML markup, decodes character references, collapses
Unicode whitespace, and retains case, punctuation, emoji, and wording. Empty
text becomes null, so rating-only records are valid. Dates are stored in UTC;
date-only marketplace values use UTC midnight and retain day-level meaning.
Identifiers receive whitespace normalization only. Payload metadata is bounded
to 30 keys and 8,000 serialized characters; review text is limited to 10,000
characters.

## Secure ingestion

`POST /api/v1/internal/acquisition/reviews` uses the existing
`X-Ingestion-Key`. A request supplies `platform_code`, the marketplace's
`external_listing_id`, `source_url`, and 1–100 reviews. The backend resolves the
exact `(platform, external listing ID)` pair. It rejects an unknown listing and
never title-matches or accepts a caller-supplied seller ID. All inserts in the
batch commit atomically. Repeated records return `duplicate` and do not create
additional rows.

PriceOye requests the proven `<product URL>/reviews` page after emitting the
listing, parses its server-rendered review records, and emits a separate review
batch acquisition item. `MAX_REVIEWS_PER_LISTING` defaults to 50 and is capped
at the API maximum of 100. The visible `Show More` control does not expose a
documented stable request contract in this project, so the collector does not
guess pagination parameters; it collects the bounded server-rendered records.

Review parsing, fetching, validation/ingestion, and unresolved-listing failures
flow through the existing scrape-run/error system as `review_parse_error`,
`review_fetch_error`, `review_validation_failure`,
`review_ingestion_failure`, or `review_listing_unresolved`. A review batch is
counted once as either ingested or failed.

## Read API

Authenticated application users can call:

`GET /api/v1/products/{product_id}/reviews?page=1&page_size=20`

An optional `listing_id` limits the response to one listing that belongs to the
product. The response includes persisted reviews, total, pagination, arithmetic
average rating, and a 1–5 distribution. It deliberately contains no sentiment,
fake/genuine/suspicious label, probability, or trust score.

## Known limitations

- Daraz review extraction is not enabled because no reliable review response is
  represented in the current collector or fixtures.
- PriceOye exposes no review/reviewer IDs in the inspected DOM, so fallback
  identity is required. A marketplace edit to fingerprint fields can appear as
  a new review because no immutable source ID exists.
- PriceOye helpful counts and seller identity are unavailable. Seller
  association is present only when the already-resolved listing has a seller.
- Only the server-rendered PriceOye review batch is collected; the undocumented
  client-side `Show More` transport is not automated.
