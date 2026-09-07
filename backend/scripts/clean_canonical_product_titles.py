from __future__ import annotations

import argparse
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.models.canonical_product import CanonicalProduct
from app.services.cross_marketplace_matching import clean_product_display_name


def run(*, apply_changes: bool) -> tuple[int, int, list[str]]:
    """Shorten raw marketplace titles without creating model collisions."""

    database_session = SessionLocal()
    updated = 0
    blocked: list[str] = []

    try:
        products = database_session.query(CanonicalProduct).order_by(
            CanonicalProduct.id
        ).all()

        reserved_models = {
            (product.brand_id, product.model): product.id
            for product in products
            if product.model
        }

        for product in products:
            cleaned = clean_product_display_name(product.name)
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

        if apply_changes:
            database_session.commit()
        else:
            database_session.rollback()

        return len(products), updated, blocked
    except Exception:
        database_session.rollback()
        raise
    finally:
        database_session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clean raw marketplace text from canonical titles.",
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    total, updated, blocked = run(apply_changes=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(
        f"[{mode}] products={total} updated={updated} "
        f"blocked={len(blocked)}"
    )
    for item in blocked:
        print(f"BLOCKED {item}")


if __name__ == "__main__":
    main()
