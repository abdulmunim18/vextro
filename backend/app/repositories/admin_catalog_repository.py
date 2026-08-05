from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.brand import Brand
from app.models.canonical_product import CanonicalProduct
from app.models.category import Category
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant

from app.models.platform import Platform
from app.models.seller import Seller

class AdminCatalogRepository:
    """Administrator catalog database queries."""

    @staticmethod
    def _product_projection():
        variant_count = (
            select(func.count(ProductVariant.id))
            .where(
                ProductVariant.canonical_product_id
                == CanonicalProduct.id
            )
            .correlate(CanonicalProduct)
            .scalar_subquery()
        )

        listing_count = (
            select(func.count(ProductListing.id))
            .select_from(ProductListing)
            .join(
                ProductVariant,
                ProductListing.product_variant_id
                == ProductVariant.id,
            )
            .where(
                ProductVariant.canonical_product_id
                == CanonicalProduct.id
            )
            .correlate(CanonicalProduct)
            .scalar_subquery()
        )

        available_listing_count = (
            select(func.count(ProductListing.id))
            .select_from(ProductListing)
            .join(
                ProductVariant,
                ProductListing.product_variant_id
                == ProductVariant.id,
            )
            .where(
                ProductVariant.canonical_product_id
                == CanonicalProduct.id,
                ProductListing.is_available.is_(True),
            )
            .correlate(CanonicalProduct)
            .scalar_subquery()
        )

        return (
            select(
                CanonicalProduct.id.label("id"),
                CanonicalProduct.name.label("name"),
                CanonicalProduct.slug.label("slug"),
                CanonicalProduct.model.label("model"),
                CanonicalProduct.category_id.label(
                    "category_id"
                ),
                Category.name.label("category_name"),
                CanonicalProduct.brand_id.label(
                    "brand_id"
                ),
                Brand.name.label("brand_name"),
                CanonicalProduct.is_active.label(
                    "is_active"
                ),
                func.coalesce(
                    variant_count,
                    0,
                ).label("variant_count"),
                func.coalesce(
                    listing_count,
                    0,
                ).label("listing_count"),
                func.coalesce(
                    available_listing_count,
                    0,
                ).label(
                    "available_listing_count"
                ),
                CanonicalProduct.created_at.label(
                    "created_at"
                ),
                CanonicalProduct.updated_at.label(
                    "updated_at"
                ),
            )
            .select_from(CanonicalProduct)
            .join(
                Category,
                Category.id
                == CanonicalProduct.category_id,
            )
            .outerjoin(
                Brand,
                Brand.id == CanonicalProduct.brand_id,
            )
        )

    @classmethod
    def list_products(
        cls,
        database_session: Session,
        *,
        query: str | None,
        category_id: int | None,
        brand_id: int | None,
        is_active: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, object]], int]:
        """Return filtered products and matching count."""

        product_statement = (
            cls._product_projection()
        )

        count_statement = (
            select(func.count())
            .select_from(CanonicalProduct)
            .join(
                Category,
                Category.id
                == CanonicalProduct.category_id,
            )
            .outerjoin(
                Brand,
                Brand.id == CanonicalProduct.brand_id,
            )
        )

        filters = []

        if query:
            normalized_query = query.strip()

            if normalized_query:
                search_pattern = (
                    f"%{normalized_query}%"
                )

                filters.append(
                    or_(
                        CanonicalProduct.name.ilike(
                            search_pattern
                        ),
                        CanonicalProduct.slug.ilike(
                            search_pattern
                        ),
                        CanonicalProduct.model.ilike(
                            search_pattern
                        ),
                        Brand.name.ilike(
                            search_pattern
                        ),
                        Category.name.ilike(
                            search_pattern
                        ),
                    )
                )

        if category_id is not None:
            filters.append(
                CanonicalProduct.category_id
                == category_id
            )

        if brand_id is not None:
            filters.append(
                CanonicalProduct.brand_id == brand_id
            )

        if is_active is not None:
            filters.append(
                CanonicalProduct.is_active.is_(
                    is_active
                )
            )

        if filters:
            product_statement = (
                product_statement.where(*filters)
            )

            count_statement = (
                count_statement.where(*filters)
            )

        total_items = int(
            database_session.scalar(
                count_statement
            )
            or 0
        )

        offset = (page - 1) * page_size

        product_statement = (
            product_statement.order_by(
                CanonicalProduct.created_at.desc(),
                CanonicalProduct.id.desc(),
            )
            .offset(offset)
            .limit(page_size)
        )

        product_rows = (
            database_session.execute(
                product_statement
            )
            .mappings()
            .all()
        )

        products = [
            dict(product_row)
            for product_row in product_rows
        ]

        return products, total_items

    @classmethod
    def get_product_record_by_id(
        cls,
        database_session: Session,
        product_id: int,
    ) -> dict[str, object] | None:
        """Return one administrator product record."""

        statement = (
            cls._product_projection()
            .where(
                CanonicalProduct.id == product_id
            )
        )

        product_row = (
            database_session.execute(statement)
            .mappings()
            .one_or_none()
        )

        if product_row is None:
            return None

        return dict(product_row)

    @staticmethod
    def get_product_entity_by_id(
        database_session: Session,
        product_id: int,
    ) -> CanonicalProduct | None:
        """Return one canonical-product ORM entity."""

        statement = select(
            CanonicalProduct
        ).where(
            CanonicalProduct.id == product_id
        )

        return database_session.scalar(statement)

    @classmethod
    def update_product_status(
        cls,
        database_session: Session,
        *,
        product: CanonicalProduct,
        is_active: bool,
    ) -> dict[str, object]:
        """Update product status and return its admin record."""

        try:
            product.is_active = is_active

            database_session.commit()
        except Exception:
            database_session.rollback()
            raise

        product_record = (
            cls.get_product_record_by_id(
                database_session,
                product.id,
            )
        )

        if product_record is None:
            raise RuntimeError(
                "Updated product could not be reloaded."
            )

        return product_record
    @staticmethod
    def list_listings(
        database_session: Session,
        *,
        query: str | None,
        platform_id: int | None,
        product_id: int | None,
        is_available: bool | None,
        page: int,
        page_size: int,
    ) -> tuple[list[dict[str, object]], int]:
        """Return filtered marketplace listings."""

        listing_statement = (
            select(
                ProductListing.id.label("id"),
                ProductListing.external_id.label(
                    "external_id"
                ),
                ProductListing.title.label("title"),
                ProductListing.product_url.label(
                    "product_url"
                ),
                Platform.id.label("platform_id"),
                Platform.name.label("platform_name"),
                Platform.code.label("platform_code"),
                CanonicalProduct.id.label(
                    "product_id"
                ),
                CanonicalProduct.name.label(
                    "product_name"
                ),
                CanonicalProduct.model.label(
                    "product_model"
                ),
                ProductVariant.id.label(
                    "variant_id"
                ),
                ProductVariant.sku.label(
                    "variant_sku"
                ),
                ProductVariant.ram_gb.label(
                    "ram_gb"
                ),
                ProductVariant.storage_gb.label(
                    "storage_gb"
                ),
                ProductVariant.color.label(
                    "color"
                ),
                Seller.id.label("seller_id"),
                Seller.name.label("seller_name"),
                Seller.is_verified.label(
                    "seller_is_verified"
                ),
                ProductListing.current_price.label(
                    "current_price"
                ),
                ProductListing.original_price.label(
                    "original_price"
                ),
                ProductListing.currency.label(
                    "currency"
                ),
                ProductListing.rating.label(
                    "rating"
                ),
                ProductListing.review_count.label(
                    "review_count"
                ),
                ProductListing.warranty.label(
                    "warranty"
                ),
                ProductListing.is_available.label(
                    "is_available"
                ),
                ProductListing.first_seen_at.label(
                    "first_seen_at"
                ),
                ProductListing.last_seen_at.label(
                    "last_seen_at"
                ),
            )
            .select_from(ProductListing)
            .join(
                Platform,
                Platform.id
                == ProductListing.platform_id,
            )
            .join(
                ProductVariant,
                ProductVariant.id
                == ProductListing.product_variant_id,
            )
            .join(
                CanonicalProduct,
                CanonicalProduct.id
                == ProductVariant.canonical_product_id,
            )
            .outerjoin(
                Seller,
                Seller.id
                == ProductListing.seller_id,
            )
        )

        count_statement = (
            select(func.count())
            .select_from(ProductListing)
            .join(
                Platform,
                Platform.id
                == ProductListing.platform_id,
            )
            .join(
                ProductVariant,
                ProductVariant.id
                == ProductListing.product_variant_id,
            )
            .join(
                CanonicalProduct,
                CanonicalProduct.id
                == ProductVariant.canonical_product_id,
            )
            .outerjoin(
                Seller,
                Seller.id
                == ProductListing.seller_id,
            )
        )

        filters = []

        if query:
            normalized_query = query.strip()

            if normalized_query:
                search_pattern = (
                    f"%{normalized_query}%"
                )

                filters.append(
                    or_(
                        ProductListing.title.ilike(
                            search_pattern
                        ),
                        ProductListing.external_id.ilike(
                            search_pattern
                        ),
                        CanonicalProduct.name.ilike(
                            search_pattern
                        ),
                        CanonicalProduct.model.ilike(
                            search_pattern
                        ),
                        Seller.name.ilike(
                            search_pattern
                        ),
                    )
                )

        if platform_id is not None:
            filters.append(
                ProductListing.platform_id
                == platform_id
            )

        if product_id is not None:
            filters.append(
                CanonicalProduct.id == product_id
            )

        if is_available is not None:
            filters.append(
                ProductListing.is_available.is_(
                    is_available
                )
            )

        if filters:
            listing_statement = (
                listing_statement.where(*filters)
            )

            count_statement = (
                count_statement.where(*filters)
            )

        total_items = int(
            database_session.scalar(
                count_statement
            )
            or 0
        )

        offset = (page - 1) * page_size

        listing_statement = (
            listing_statement.order_by(
                ProductListing.last_seen_at.desc(),
                ProductListing.id.desc(),
            )
            .offset(offset)
            .limit(page_size)
        )

        listing_rows = (
            database_session.execute(
                listing_statement
            )
            .mappings()
            .all()
        )

        listings = [
            dict(listing_row)
            for listing_row in listing_rows
        ]

        return listings, total_items