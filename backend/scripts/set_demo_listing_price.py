"""Change the local demo listing price and run price-alert delivery.

Run from the ``backend`` directory::

    python -m scripts.set_demo_listing_price 90000

This script is deliberately locked to the VEXTRO demo listing. It records a
price-history observation, evaluates product/listing alerts, commits the price
capture, and then dispatches queued email/Web Push notifications.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from sqlalchemy import func, select

from app.core.database import SessionLocal
from app.models.canonical_product import CanonicalProduct
from app.models.notification import Notification
from app.models.notification_event import NotificationEvent
from app.models.platform import Platform
from app.models.price_history import PriceHistory
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.services.notification_dispatcher import dispatch_pending_deliveries
from app.services.price_alert_service import evaluate_price_alerts_for_capture


DEMO_PLATFORM_CODE = "vextro-demo"
DEMO_EXTERNAL_ID = "vextro-demo-email-alert-001"
MONEY_PRECISION = Decimal("0.01")


def positive_price(raw_value: str) -> Decimal:
    """Parse one positive PKR value for argparse."""

    try:
        value = Decimal(raw_value.replace(",", "")).quantize(
            MONEY_PRECISION,
            rounding=ROUND_HALF_UP,
        )
    except (InvalidOperation, AttributeError) as error:
        raise argparse.ArgumentTypeError(
            "Price must be a valid number, for example 90000."
        ) from error

    if value <= 0:
        raise argparse.ArgumentTypeError("Price must be greater than zero.")

    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Set the Demo Email Alert Product price and trigger eligible "
            "notification/email deliveries."
        ),
    )
    parser.add_argument(
        "price",
        type=positive_price,
        help="New demo price in PKR, for example 90000",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the intended change without updating the database.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    database_session = SessionLocal()

    try:
        platform = database_session.scalar(
            select(Platform).where(Platform.code == DEMO_PLATFORM_CODE)
        )
        if platform is None:
            print("Demo platform was not found. Create the demo listing first.")
            return 1

        listing = database_session.scalar(
            select(ProductListing).where(
                ProductListing.platform_id == platform.id,
                ProductListing.external_id == DEMO_EXTERNAL_ID,
            )
        )
        if listing is None:
            print("Demo listing was not found. Create the demo listing first.")
            return 1

        if not (
            listing.raw_payload.get("test_product") is True
            and listing.raw_payload.get("email_alert_test") is True
        ):
            print("Safety check failed: the matched listing is not a demo listing.")
            return 1

        variant = database_session.get(
            ProductVariant,
            listing.product_variant_id,
        )
        product = (
            database_session.get(CanonicalProduct, variant.canonical_product_id)
            if variant is not None
            else None
        )
        if variant is None or product is None:
            print("Demo listing has an invalid product relationship.")
            return 1

        previous_price = listing.current_price
        new_price = arguments.price

        if arguments.dry_run:
            print(
                {
                    "dry_run": True,
                    "product_id": product.id,
                    "listing_id": listing.id,
                    "previous_price": str(previous_price),
                    "new_price": str(new_price),
                }
            )
            return 0

        captured_at = datetime.now(timezone.utc)
        listing.current_price = new_price
        listing.last_seen_at = captured_at
        listing.raw_payload = {
            **(listing.raw_payload or {}),
            "last_manual_demo_price": str(new_price),
            "last_manual_demo_capture_at": captured_at.isoformat(),
        }
        database_session.add(listing)
        database_session.add(
            PriceHistory(
                listing_id=listing.id,
                price=new_price,
                original_price=listing.original_price,
                currency=listing.currency,
                is_available=listing.is_available,
                source="manual_demo",
                captured_at=captured_at,
            )
        )

        previous_max_event_id = database_session.scalar(
            select(func.max(NotificationEvent.id))
        ) or 0
        alerts_triggered = evaluate_price_alerts_for_capture(
            database_session,
            canonical_product_id=product.id,
            listing_id=listing.id,
            current_price=new_price,
            currency=listing.currency,
            marketplace_name=platform.name,
        )
        new_event_ids = list(
            database_session.scalars(
                select(NotificationEvent.id)
                .join(
                    Notification,
                    Notification.id == NotificationEvent.notification_id,
                )
                .where(
                    NotificationEvent.id > previous_max_event_id,
                    Notification.canonical_product_id == product.id,
                )
            ).all()
        )
        database_session.commit()

        delivery_summary = {
            "attempted": 0,
            "delivered": 0,
            "failed": 0,
        }
        if alerts_triggered:
            delivery_summary = dispatch_pending_deliveries(
                database_session,
                event_ids=new_event_ids,
            )

        print(
            {
                "updated": True,
                "product_id": product.id,
                "listing_id": listing.id,
                "previous_price": str(previous_price),
                "new_price": str(new_price),
                "alerts_triggered": alerts_triggered,
                "deliveries": delivery_summary,
            }
        )

        if not alerts_triggered:
            print(
                "No active alert was hit. Create an alert whose target is "
                "greater than or equal to the new demo price, then run the "
                "script again with a qualifying price."
            )

        return 0

    except Exception as error:  # noqa: BLE001 - CLI must rollback cleanly.
        database_session.rollback()
        print(f"Demo price update failed: {type(error).__name__}: {error}")
        return 1

    finally:
        database_session.close()


if __name__ == "__main__":
    sys.exit(main())
