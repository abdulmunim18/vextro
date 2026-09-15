# Explainable suspicious-review analysis (`review-risk-v1`)

This module evaluates *suspicious characteristics*, not proven fraud. It uses persisted `raw_reviews` only. The source text remains unchanged; text comparison uses Unicode NFKC, case-folding, and collapsed whitespace. Near similarity additionally removes punctuation and uses Dice similarity over unique character trigrams. Texts shorter than 20 comparable characters or four words are excluded from duplicate similarity to avoid elevating generic praise such as “Good”. Strong near similarity starts at 0.85; moderate similarity starts at 0.75. Exact normalized-text matches take precedence so duplicate weights do not stack.

## Capability matrix

| Signal | Status | Evidence/guard |
| --- | --- | --- |
| Exact text duplicate, near duplicate | Implemented | Listing-local persisted text and similarity counts |
| Review length and very short extreme rating | Implemented | Character/word counts; short rating is only +3 |
| Rating/text disagreement | Conditionally implemented | English-only limited lexicon, two unnegated polarity words; no claim of general sentiment accuracy |
| Excess capitalization, punctuation, repeated words | Conditionally implemented | Text-present weak signal; ordinary punctuation alone does not score |
| Verified purchase | Conditionally implemented | `true` reduces risk; `false` and `null` add no risk |
| Reviewer repetition / repeated wording | Conditionally implemented | Same non-null marketplace reviewer ID and strong wording similarity on the same listing; display names never assert identity |
| Temporal burst / review timing | Conditionally implemented | At least three strongly similar reviews with real `reviewed_at` values within 24 hours; same day alone is not a signal |
| Rating distribution and listing concentration | Conditionally implemented | Factual 1–5 counts; +3 only for >=10 reviews, >=90% one extreme rating, and wording similarity |
| Repeated identical rating patterns, overall text diversity, helpful counts, seller review concentration | Conditionally available but not scored | Raw ratings/text/helpful counts/optional seller IDs exist, but these are not defensible standalone authenticity signals in v1 |
| Reviewer history across platforms, verified reviewer identity, Daraz review extraction | Not available | Current data/contract cannot support these signals |

## Scoring

Weights and thresholds are centralized in `review_risk_engine.py`. The score is the sum of activated weights, clamped to 0–100. Exact and near duplicate tiers are mutually exclusive. Scores 0–29 are **low**, 30–59 **medium**, 60–100 **high**.

| Signal | Weight / activation |
| --- | --- |
| Exact normalized text duplicate | +40, comparable text and >=1 other distinct review |
| Strong near duplicate | +25, max trigram Dice >=0.85 and not exact |
| Moderate similarity | +12, max similarity >=0.75 and <0.85 |
| Rating/text conflict | +15, rating <=2 with >=2 positive words or >=4 with >=2 negative words, no opposing words; local two-word negation guard |
| Similar review burst | +15, >=2 strongly similar peers timestamped within 24h of review |
| Reviewer repeated wording | +10, same non-null marketplace reviewer ID and strong similarity |
| Short extreme rating | +3, 1–2 words with rating 1 or 5 |
| Excessive formatting | +4, repeated word triple or combined >=80% uppercase and >=4 repeated `!`/`?` with >=12 letters |
| Extreme rating context | +3, >=10 listing reviews, >=90% 1-star or 5-star and at least moderate text similarity |
| Verified purchase | −10, only when marketplace evidence is explicitly `true` |

`signals.applied_weights` records each activated component; reasons are human-readable and avoid fraud certainty. `duplicate_similarity_score` records factual maximum similarity as 0–100, while text/rating/temporal/reviewer anomaly fields record component-weight contributions for later academic analysis.

## Integration and API

Secure batch ingestion analyzes all reviews on the affected listing **only when new reviews were inserted**, within the same transaction. An unexpected analysis failure rolls back the batch, following existing operational error handling; a high-suspicion result is normal data, not a scrape error. Existing reviews can be reanalyzed via authenticated `POST /api/v1/products/{product_id}/review-analysis/run?listing_id=...`. This upserts on `(raw_review_id, analysis_version)` rather than creating duplicates. The authenticated `GET /api/v1/products/{product_id}/review-analysis` accepts optional `listing_id`, `page`, and `page_size` and returns total/analyzed counts, low/medium/high counts, high percentage, average score, exact/near counts, and paged review evidence. `GET /api/v1/products/{product_id}/reviews/{review_id}/analysis` reads one persisted result. Listing and review scoping are checked against the requested canonical product.

## Evaluation and limits

`backend/tests/fixtures/review_risk_scenarios.json` contains artificial, sanitized **scenario** data—not fraud ground truth or production data. Tests measure expected rule behavior and false-positive guards. Accuracy, precision, recall, and F1 are **not claimed**. The English polarity lexicon misses other languages, sarcasm, and nuanced negation. Display names are not trusted as identities. Optional timestamps/reviewer IDs/verified status may be absent. PriceOye review extraction is supported; Daraz remains unsupported until a reliable response contract is verified. Ordinary similar or enthusiastic reviews can be legitimate, so even high suspicion must be reviewed as evidence rather than a verdict. The synchronous all-listing pairwise comparison is suitable for the current FYP scale but is O(n²) and should be capacity-tested before large-volume production ingestion. Future rule changes require a new `analysis_version` and reanalysis rather than silently changing the meaning of persisted v1 scores.
