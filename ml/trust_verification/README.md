# Review-risk input boundary

The executable `review-risk-v1` detector lives in `backend/app/services/review_risk_engine.py` because review evidence is persisted and API-served by the backend. It is deterministic, local, and does not contain a trained classifier. Its versioned outputs are stored in `review_analyses` and can be used as evidence by future trust-verification work.

This package does **not** compute a seller-trust score or label any review as definitively fake. See `docs/review-risk-analysis.md` for its capability matrix, weights, thresholds, and limitations.
Seller-level `seller-trust-v1` now consumes persisted review-risk results through backend services; it remains separate from this package and is documented in `docs/seller-trust-analysis.md`.
