from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.repositories.admin_catalog_repository import (
    AdminCatalogRepository,
)
from app.schemas.admin_catalog import (
    AdminProductListResponse,
    AdminProductResponse,
    AdminProductStatusUpdate,
    AdminListingListResponse,
    AdminListingResponse,
)


class AdminCatalogService:

    """Administrator product-catalog operations."""

    @staticmethod
    def _serialize_product(
        product_record: dict[str, object],
    ) -> AdminProductResponse:
        return AdminProductResponse(
            **product_record,
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
    ) -> AdminProductListResponse:
        products, total_items = (
            AdminCatalogRepository.list_products(
                database_session,
                query=query,
                category_id=category_id,
                brand_id=brand_id,
                is_active=is_active,
                page=page,
                page_size=page_size,
            )
        )

        total_pages = (
            (total_items + page_size - 1)
            // page_size
            if total_items > 0
            else 0
        )

        return AdminProductListResponse(
            items=[
                cls._serialize_product(product)
                for product in products
            ],
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )

    @classmethod
    def update_product_status(
        cls,
        database_session: Session,
        *,
        product_id: int,
        payload: AdminProductStatusUpdate,
    ) -> AdminProductResponse:
        product = (
            AdminCatalogRepository
            .get_product_entity_by_id(
                database_session,
                product_id,
            )
        )

        if product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "PRODUCT_NOT_FOUND",
                    "message": (
                        "The requested product "
                        "does not exist."
                    ),
                },
            )

        if product.is_active == payload.is_active:
            product_record = (
                AdminCatalogRepository
                .get_product_record_by_id(
                    database_session,
                    product.id,
                )
            )

            if product_record is None:
                raise RuntimeError(
                    "Product could not be reloaded."
                )

            return cls._serialize_product(
                product_record
            )

        updated_product = (
            AdminCatalogRepository
            .update_product_status(
                database_session,
                product=product,
                is_active=payload.is_active,
            )
        )

        return cls._serialize_product(
            updated_product
        )
    @staticmethod
    def _serialize_listing(
        listing_record: dict[str, object],
    ) -> AdminListingResponse:
        return AdminListingResponse(
            **listing_record,
        )

    @classmethod
    def list_listings(
        cls,
        database_session: Session,
        *,
        query: str | None,
        platform_id: int | None,
        product_id: int | None,
        is_available: bool | None,
        page: int,
        page_size: int,
    ) -> AdminListingListResponse:
        listings, total_items = (
            AdminCatalogRepository.list_listings(
                database_session,
                query=query,
                platform_id=platform_id,
                product_id=product_id,
                is_available=is_available,
                page=page,
                page_size=page_size,
            )
        )

        total_pages = (
            (total_items + page_size - 1)
            // page_size
            if total_items > 0
            else 0
        )

        return AdminListingListResponse(
            items=[
                cls._serialize_listing(listing)
                for listing in listings
            ],
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )