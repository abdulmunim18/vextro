from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from sqlalchemy import func


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.api.routes.ingest import (
    infer_brand_name,
    infer_title_specifications,
)
from app.core.database import SessionLocal
from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct


def brand_slug(name: str) -> str:
    """Return a compact URL-safe slug for one brand."""

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "brand"


def get_or_create_brand(database_session, name: str) -> Brand:
    """Resolve a brand case-insensitively, creating it when necessary."""

    existing = database_session.query(Brand).filter(
        func.lower(Brand.name) == name.lower()
    ).first()
    if existing:
        return existing

    slug_base = brand_slug(name)
    slug = slug_base
    suffix = 2
    while database_session.query(Brand).filter(Brand.slug == slug).first():
        slug = f"{slug_base}-{suffix}"
        suffix += 1

    brand = Brand(name=name, slug=slug, is_active=True)
    database_session.add(brand)
    database_session.flush()
    return brand


def run(*, apply_changes: bool) -> tuple[int, int, int]:
    """Backfill safe title-derived brand and specification metadata."""

    database_session = SessionLocal()
    brand_updates = 0
    specification_updates = 0

    try:
        products = database_session.query(CanonicalProduct).all()

        for product in products:
            source_text = product.name or product.model or ""

            if product.brand_id is None:
                inferred_brand = infer_brand_name(source_text)
                if inferred_brand:
                    brand = get_or_create_brand(
                        database_session,
                        inferred_brand,
                    )
                    product.brand_id = brand.id
                    brand_updates += 1

            inferred_specs = infer_title_specifications(source_text)
            merged_specs = dict(product.specifications or {})
            before = dict(merged_specs)
            for key, value in inferred_specs.items():
                merged_specs.setdefault(key, value)

            if merged_specs != before:
                product.specifications = merged_specs
                specification_updates += 1

        if apply_changes:
            database_session.commit()
        else:
            database_session.rollback()

        return len(products), brand_updates, specification_updates
    except Exception:
        database_session.rollback()
        raise
    finally:
        database_session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill scraped VEXTRO brand/specification metadata.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Persist changes. Without this flag the script is a dry run.",
    )
    args = parser.parse_args()

    total, brands, specifications = run(apply_changes=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(
        f"[{mode}] products={total} "
        f"brand_updates={brands} "
        f"specification_updates={specifications}"
    )


if __name__ == "__main__":
    main()
