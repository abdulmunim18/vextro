from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.canonical_product import CanonicalProduct
from app.models.platform import Platform
from app.models.price_history import PriceHistory
from app.models.price_forecast import PriceForecast
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


def get_active_variant_for_forecast(
    database_session: Session,
    variant_id: int,
) -> ProductVariant | None:
    """Return an active variant whose canonical product is also active."""

    query = (
        select(ProductVariant)
        .join(
            CanonicalProduct,
            ProductVariant.canonical_product_id == CanonicalProduct.id,
        )
        .where(
            ProductVariant.id == variant_id,
            ProductVariant.is_active.is_(True),
            CanonicalProduct.is_active.is_(True),
        )
    )

    return database_session.scalar(query)


def replace_active_variant_forecast(
    database_session: Session,
    forecast: PriceForecast,
) -> PriceForecast:
    """Activate a new forecast and retire prior versions for its variant."""

    database_session.execute(
        update(PriceForecast)
        .where(
            PriceForecast.product_variant_id == forecast.product_variant_id,
            PriceForecast.is_active.is_(True),
        )
        .values(is_active=False)
    )
    database_session.add(forecast)
    database_session.flush()

    return forecast


def get_active_variant_forecast(
    database_session: Session,
    variant_id: int,
) -> PriceForecast | None:
    """Return the newest active forecast for one exact variant."""

    query = (
        select(PriceForecast)
        .where(
            PriceForecast.product_variant_id == variant_id,
            PriceForecast.is_active.is_(True),
        )
        .order_by(
            PriceForecast.generated_at.desc(),
            PriceForecast.id.desc(),
        )
        .limit(1)
    )

    return database_session.scalar(query)


def get_latest_product_forecast(
    database_session: Session,
    product_id: int,
) -> PriceForecast | None:
    """Return the newest active forecast across a product's variants."""

    query = (
        select(PriceForecast)
        .join(
            ProductVariant,
            PriceForecast.product_variant_id == ProductVariant.id,
        )
        .where(
            ProductVariant.canonical_product_id == product_id,
            ProductVariant.is_active.is_(True),
            PriceForecast.is_active.is_(True),
        )
        .order_by(
            PriceForecast.generated_at.desc(),
            PriceForecast.id.desc(),
        )
        .limit(1)
    )

    return database_session.scalar(query)
