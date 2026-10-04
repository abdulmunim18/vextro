from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.models.canonical_product import CanonicalProduct
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.seller import Seller
from app.services.cross_marketplace_matching import clean_product_display_name
from app.services.smartphone_normalization import clean_marketplace_title


def seller_names_by_product(database_session) -> dict[int, list[str]]:
    """Return the store names that sell each canonical product.

    A title's store prefix can only be removed with confidence when the
    store is known, and the listing's own seller is where that is recorded.
    """

    rows = (
        database_session.query(
            ProductVariant.canonical_product_id,
            Seller.name,
        )
        .join(
            ProductListing,
            ProductListing.product_variant_id == ProductVariant.id,
        )
        .join(Seller, Seller.id == ProductListing.seller_id)
        .distinct()
        .all()
    )

    names: dict[int, list[str]] = defaultdict(list)

    for canonical_product_id, seller_name in rows:
        if seller_name and seller_name not in names[canonical_product_id]:
            names[canonical_product_id].append(seller_name)

    return names


def cleaned_title(title: str | None, seller_names: list[str]) -> str:
    """Apply store-name cleaning with every seller known for the product."""

    cleaned = clean_marketplace_title(title)

    for seller_name in seller_names:
        candidate = clean_marketplace_title(cleaned, seller_name)
        if candidate != cleaned:
            cleaned = candidate
            break

    return cleaned


def clean_listing_titles(database_session, product_sellers) -> int:
    """Strip store names out of the listing titles shown in the catalog."""

    updated = 0

    listings = (
        database_session.query(ProductListing, ProductVariant, Seller)
        .join(
            ProductVariant,
            ProductVariant.id == ProductListing.product_variant_id,
        )
        .outerjoin(Seller, Seller.id == ProductListing.seller_id)
        .order_by(ProductListing.id)
        .all()
    )

    for listing, variant, seller in listings:
        seller_names = [seller.name] if seller is not None else []
        seller_names.extend(
            product_sellers.get(variant.canonical_product_id, [])
        )

        cleaned = cleaned_title(listing.title, seller_names)

        if cleaned and cleaned != listing.title:
            listing.title = cleaned[:500]
            updated += 1

    return updated


def run(*, apply_changes: bool) -> tuple[int, int, int, list[str]]:
    """Shorten raw marketplace titles without creating model collisions."""

    database_session = SessionLocal()
    updated = 0
    blocked: list[str] = []

    try:
        products = database_session.query(CanonicalProduct).order_by(
            CanonicalProduct.id
        ).all()
        product_sellers = seller_names_by_product(database_session)

        reserved_models = {
            (product.brand_id, product.model): product.id
            for product in products
            if product.model
        }

        for product in products:
            cleaned = clean_product_display_name(
                cleaned_title(
                    product.name,
                    product_sellers.get(product.id, []),
                )
            )
            if not cleaned or cleaned == product.name:
                continue

            model_clean = cleaned[:120]
            model_key = (product.brand_id, model_clean)
            conflict_id = reserved_models.get(model_key)

            product.name = cleaned[:255]
            if conflict_id not in (None, product.id):
                blocked.append(
                    f"{product.id} name cleaned to {cleaned}; "
                    f"model retained (conflicts with {conflict_id})"
                )
            else:
                old_key = (product.brand_id, product.model)
                if reserved_models.get(old_key) == product.id:
                    reserved_models.pop(old_key)
                product.model = model_clean
                reserved_models[model_key] = product.id
            updated += 1

        listings_updated = clean_listing_titles(
            database_session,
            product_sellers,
        )

        if apply_changes:
            database_session.commit()
        else:
            database_session.rollback()

        return len(products), updated, listings_updated, blocked
    except Exception:
        database_session.rollback()
        raise
    finally:
        database_session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean raw marketplace text from catalog titles.",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    total, updated, listings_updated, blocked = run(
        apply_changes=args.apply,
    )
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(
        f"[{mode}] products={total} updated={updated} "
        f"listings_updated={listings_updated} blocked={len(blocked)}"
    )
    for item in blocked:
        print(f"BLOCKED {item}")


if __name__ == "__main__":
    main()
