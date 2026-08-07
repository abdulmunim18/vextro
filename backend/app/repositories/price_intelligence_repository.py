from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.canonical_product import CanonicalProduct
from app.models.platform import Platform
from app.models.price_history import PriceHistory
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.seller import Seller


@dataclass(slots=True)
class ListingPriceHistoryRecord:
    """A marketplace listing with its platform and historical prices."""

    listing: ProductListing
    platform_name: str
    seller_name: str | None
    points: list[PriceHistory] = field(default_factory=list)


def get_product_for_price_history(
    database_session: Session,
    product_id: int,
) -> CanonicalProduct | None:
    """Return an active canonical product for price-history requests."""

    query = select(CanonicalProduct).where(
        CanonicalProduct.id == product_id,
        CanonicalProduct.is_active.is_(True),
    )

    return database_session.scalar(query)


def list_product_price_history(
    database_session: Session,
    product_id: int,
    *,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> list[ListingPriceHistoryRecord]:
    """Return product listings and their filtered historical prices."""

    listings_query = (
        select(
            ProductListing,
            Platform.name.label("platform_name"),
            Seller.name.label("seller_name"),
        )
        .join(
            ProductVariant,
            ProductListing.product_variant_id == ProductVariant.id,
        )
        .join(
            Platform,
            ProductListing.platform_id == Platform.id,
        )
        .outerjoin(
            Seller,
            ProductListing.seller_id == Seller.id,
        )
        .where(
            ProductVariant.canonical_product_id == product_id,
            ProductVariant.is_active.is_(True),
        )
        .order_by(
            ProductListing.current_price.asc(),
            ProductListing.id.asc(),
        )
    )

    listing_rows = database_session.execute(
        listings_query
    ).all()

    if not listing_rows:
        return []

    listing_ids = [
        listing.id
        for listing, _platform_name, _seller_name in listing_rows
    ]

    history_filters = [
        PriceHistory.listing_id.in_(listing_ids),
    ]

    if date_from is not None:
        history_filters.append(
            PriceHistory.captured_at >= date_from
        )

    if date_to is not None:
        history_filters.append(
            PriceHistory.captured_at <= date_to
        )

    history_query = (
        select(PriceHistory)
        .where(*history_filters)
        .order_by(
            PriceHistory.listing_id.asc(),
            PriceHistory.captured_at.asc(),
            PriceHistory.id.asc(),
        )
    )

    history_points = list(
        database_session.scalars(
            history_query
        ).all()
    )

    points_by_listing: dict[int, list[PriceHistory]] = {
        listing_id: []
        for listing_id in listing_ids
    }

    for point in history_points:
        points_by_listing[point.listing_id].append(point)

    return [
        ListingPriceHistoryRecord(
            listing=listing,
            platform_name=platform_name,
            seller_name=seller_name,
            points=points_by_listing[listing.id],
        )
        for listing, platform_name, seller_name in listing_rows
    ]