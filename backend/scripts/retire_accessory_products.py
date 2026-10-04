"""Remove phone accessories that were registered as catalog products.

The marketplace smartphones category also serves cables, chargers, covers
and screen protectors. Before the crawl learned to recognise them, titles
such as "Original Samsung 45W GaN Charger for GALAXY S25" passed the brand
and model checks and became canonical products that shoppers can browse and
compare as if they were phones.

Accessories are deactivated rather than deleted: their price history stays
intact, and an administrator can reactivate anything this script judges
wrongly.
"""

from __future__ import annotations

import argparse
import io
import sys
from pathlib import Path


sys.stdout = io.TextIOWrapper(
    sys.stdout.buffer,
    encoding="utf-8",
    errors="replace",
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal
from app.models.canonical_product import CanonicalProduct
from app.models.pending_product_match import PendingProductMatch
from app.services.smartphone_normalization import (
    is_accessory_product_name,
    is_accessory_title,
)


def run(*, apply_changes: bool) -> dict[str, object]:
    database_session = SessionLocal()
    retired: list[str] = []
    dropped_matches = 0

    try:
        products = (
            database_session.query(CanonicalProduct)
            .filter(CanonicalProduct.is_active.is_(True))
            .order_by(CanonicalProduct.id)
            .all()
        )

        for product in products:
            # Only the product's own identity is judged. A phone listing
            # often advertises what comes in the box ("free cover and
            # charger"), and reading those titles retired real phones.
            if not (
                is_accessory_product_name(product.name)
                or is_accessory_title(product.model)
            ):
                continue

            product.is_active = False
            retired.append(f"{product.id} {str(product.name)[:70]!r}")

        # Pending matches for accessories will never be resolved to a phone.
        pending = (
            database_session.query(PendingProductMatch)
            .filter(PendingProductMatch.status == "pending")
            .all()
        )
        for match in pending:
            if is_accessory_title(match.title):
                database_session.delete(match)
                dropped_matches += 1

        if apply_changes:
            database_session.commit()
        else:
            database_session.rollback()

        return {
            "products": len(products),
            "retired": retired,
            "dropped_matches": dropped_matches,
        }
    except Exception:
        database_session.rollback()
        raise
    finally:
        database_session.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deactivate accessories registered as phone products.",
    )
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    result = run(apply_changes=args.apply)
    mode = "APPLIED" if args.apply else "DRY RUN"
    print(
        f"[{mode}] active_products={result['products']} "
        f"retired={len(result['retired'])} "
        f"pending_matches_dropped={result['dropped_matches']}"
    )

    if args.verbose:
        for line in result["retired"]:
            print(f"RETIRED {line}")


if __name__ == "__main__":
    main()
