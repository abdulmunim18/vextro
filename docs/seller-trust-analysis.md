# Seller trust indicators (`seller-trust-v1`)

Seller trust is an **evidence-based estimate**, not proof that a marketplace seller is safe, fraudulent, or legitimate. It consumes persisted `review-risk-v1` results and never runs a second review classifier. The current spiders do not populate `SmartphoneItem.seller`, despite the field and backend seller schema existing. Seller analysis therefore becomes meaningful only when a marketplace acquisition supplies a stable external seller ID and reviews can be consistently associated with that seller.

## Marketplace capability audit

| Signal | Daraz | PriceOye | Reliability for v1 |
| --- | --- | --- | --- |
| Seller ID | Unavailable from current spider; conditionally available through secure acquisition payload | Unavailable from current spider; conditionally available through secure acquisition payload | Scored only when a non-empty `external_seller_id` is persisted; name-only seller rows are insufficient |
| Seller name | Conditionally available through acquisition | Conditionally available through acquisition | Display only; name fallback is not proof of identity |
| Listing association | Conditionally available when seller payload is supplied | Conditionally available when seller payload is supplied | Current listing `seller_id` and review `seller_id` must agree |
| Review association | Unavailable through current Daraz review extraction | Conditionally available from PriceOye reviews when listing has stable seller association | Missing `seller_id` review rows are excluded rather than reassigned by name |
| Marketplace seller rating and rating count | Conditionally present in backend schema; not extracted by current spider | Conditionally present in backend schema; not extracted by current spider | Not scored: defaults/unknown provenance are not reliable evidence |
| Verified-store status | Conditionally present in backend schema; not extracted by current spider | Conditionally present in backend schema; not extracted by current spider | Not scored: backend default `false` cannot distinguish unknown from unverified |
| Multiple listings | Conditionally available for one persisted stable seller ID | Conditionally available for one persisted stable seller ID | Aggregated across current consistently linked listings; not a verified seller performance history |

The `Seller` model has optional profile URL and rating, a non-null name, review count, and `is_verified`; none of those marketplace metadata fields contributes to v1 because the current spider pipeline does not substantiate their values. `ProductListing.first_seen_at`/`last_seen_at` support listing observation history but not seller reliability or fulfillment history.

## Formula and thresholds

The score requires a stable external seller ID, **at least five analyzed seller-linked reviews**, and **at least 60% `review-risk-v1` analysis coverage**. Otherwise `trust_score=null`, `trust_level=insufficient_data`, and a reason explains the missing evidence. Unanalyzed reviews are never assumed low risk.

For eligible sellers:

```text
high_rate = high_suspicion_review_count / analyzed_reviews
mean_risk = average persisted review suspicion score / 100
review_penalty = min(60, 40 × high_rate + 35 × mean_risk)
verified_bonus = 5 × (verified reviews / reviews with known purchase status)
                 only when >=5 statuses are known and >=50% of reviews have known status
trust_score = clamp(round(80 - review_penalty + verified_bonus), 0, 100)
```

Higher scores mean stronger trust indicators: **high** ≥75, **moderate** 60–74, **low** 0–59. The base of 80 is never assigned when evidence is insufficient. The high-rate term identifies the severe tail, while the mean-risk term covers broader medium risk. Their combined review penalty is capped at 60. Duplicate wording, burst, reviewer repetition, rating/text conflict, and distribution statistics are supporting explanations only—already represented within persisted review-risk scores—and receive **no extra seller penalty**. The small verified bonus is capped at five points; null status is unknown and adds neither bonus nor penalty. Persisted review-risk scores themselves already include verified-purchase reductions, so this is a limited second supportive contribution, not independent validation.

## Separate confidence

`coverage = analyzed_reviews / total_reviews`. The volume component is 0 for <5 analyzed reviews, 10 for 5–9, 20 for 10–19, 35 for 20–49, and 50 for ≥50. `confidence_score = min(100, volume_component + round(50 × coverage))`. Confidence is **low** below 70, **medium** from 70–89, **high** at ≥90. Review volume affects confidence, **not** the trust score. An otherwise clean seller with six analyzed reviews can therefore have a high trust-indicator score and low confidence.

## Other factual outputs and missing data

The versioned analysis records all seller listings, total/covered reviews, low/medium/high risk counts, high-risk percentage, average persisted risk, exact/near duplicate counts, purchase-status known count, verified count and known-status ratio, rating distribution, rating average, and population variance. A high rating alone is never a penalty. Seller-null listings return `insufficient_data` without an invented seller ID or neutral score. Name-only sellers also return `insufficient_data`. Fewer than five analyses or <60% coverage does not produce a numeric score. An evidence signature detects stale results if review scores, associations, or counts change; stale GET results hide the old score and request recalculation.

## Persistence and API

`seller_trust_analyses` is unique on `(seller_id, analysis_version)`, with check constraints for score/level, confidence, coverage, and counts. Review ingestion recomputes the relevant seller after new `review-risk-v1` results, within the source-review transaction. Authenticated product review-risk reruns also recompute the associated seller. Manual authenticated recomputation is `POST /api/v1/sellers/{seller_id}/trust/recalculate`; retrieval is `GET /api/v1/sellers/{seller_id}/trust`. `GET /api/v1/products/{product_id}/listings/{listing_id}/seller-trust` provides listing-scoped availability and safely handles a missing seller. APIs return score/level, confidence, evidence counts, version, timestamp, factual signals, and human-readable reasons. Scores never use labels such as “fake seller” or “safe seller”.

## Evaluation and limitations

`backend/tests/fixtures/seller_trust_scenarios.json` is artificial and sanitized scenario data, not marketplace observations or verified fraud ground truth. Tests assert expected rule behavior and false-positive guards; no accuracy, precision, recall, or F1 is claimed. Real seller identity coverage is currently sparse because neither spider extracts seller identifiers, and Daraz review extraction remains unsupported. Acquisition can fall back to seller-name matching, so even rows with an external ID are not independently verified identities. Review-risk-v1 is heuristic/statistical and its errors propagate into seller estimates. Listing ownership can change without a complete seller-history record. Before production, validate identity provenance, data volume, coverage, and outcomes against independently labelled evidence.
