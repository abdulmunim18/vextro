#!/usr/bin/env python3
"""Recompute ``product_listings.rating`` and ``review_count`` from raw_reviews.

The ingestion pipeline populates these two columns for any listing that
receives NEW reviews after the aggregate service landed, but existing
listings whose reviews were captured earlier still show stale zeros in
the UI ("★ 0.0 (0 reviews)" on offer cards even where 7 real reviews
exist in ``raw_reviews``).

Run this once after the aggregate service is deployed to fill in the
history. It is safe to re-run — the aggregate is idempotent and the
script commits per listing so a mid-run crash never leaves partial
values on the wrong row.

Usage (from repo root, with backend/.env loaded):

    python scripts/backfill_listing_review_aggregates.py
"""

from __future__ import annotations

import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_ROOT = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND_ROOT))

# ``app.core.config`` uses pydantic-settings, which reads from the
# process environment by default and only auto-discovers a ``.env``
# next to CWD. Load ``backend/.env`` explicitly so this script works
# regardless of where the caller invokes it from.
try:
    from dotenv import load_dotenv
except ImportError as exc:
    raise SystemExit(
        "python-dotenv is required. Run this from the backend venv."
    ) from exc
load_dotenv(BACKEND_ROOT / ".env")


def main() -> int:
    from sqlalchemy import distinct, select
    from app.core.database import SessionLocal
    from app.models.raw_review import RawReview
    from app.repositories.review_repository import ReviewRepository

    repository = ReviewRepository()
    updated = 0

    with SessionLocal() as database_session:
        listing_ids = list(
            database_session.scalars(
                select(distinct(RawReview.product_listing_id)),
            )
        )
        print(
            f"Found {len(listing_ids)} listings with at least one review.",
        )
        for listing_id in listing_ids:
            average, count = repository.refresh_listing_aggregate(
                database_session,
                listing_id=listing_id,
            )
            database_session.commit()
            updated += 1
            print(
                f"  listing_id={listing_id:>5}  rating={average}  count={count}"
            )

    print(f"Done. Refreshed aggregate on {updated} listings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
