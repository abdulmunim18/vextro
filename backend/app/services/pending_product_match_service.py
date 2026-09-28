"""Create, resolve, and replay unresolved marketplace product matches."""

from datetime import datetime, timezone
from math import ceil

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.models.pending_product_match import PendingProductMatch
from app.repositories.acquisition_repository import AcquisitionRepository
from app.repositories.pending_product_match_repository import (
    PendingProductMatchRepository,
)
from app.schemas.acquisition import AcquisitionListingInput
from app.schemas.pending_product_match import (
    PendingProductMatchCreate,
    PendingProductMatchListResponse,
    PendingProductMatchReplayResponse,
    PendingProductMatchResolve,
    PendingProductMatchResponse,
    ProductVariantOption,
    ProductVariantOptionListResponse,
)
from app.services.acquisition_service import AcquisitionService


class PendingProductMatchService:
    def __init__(self) -> None:
        self.repository = PendingProductMatchRepository()
        self.acquisition_repository = AcquisitionRepository()
        self.acquisition_service = AcquisitionService()

    @staticmethod
    def _variant_label(match: PendingProductMatch) -> str | None:
        variant = match.assigned_product_variant
        if variant is None:
            return None
        parts = []
        if variant.ram_gb:
            parts.append(f"{variant.ram_gb} GB RAM")
        if variant.storage_gb:
            parts.append(f"{variant.storage_gb} GB")
        if variant.color:
            parts.append(variant.color)
        return " / ".join(parts) or variant.sku or f"Variant {variant.id}"

    def as_response(self, match: PendingProductMatch) -> PendingProductMatchResponse:
        variant = match.assigned_product_variant
        product = variant.canonical_product if variant is not None else None
        return PendingProductMatchResponse(
            id=match.id,
            platform_code=match.platform_code,
            external_id=match.external_id,
            title=match.title,
            product_url=match.product_url,
            match_payload=match.match_payload,
            listing_payload=match.listing_payload,
            match_confidence=match.match_confidence,
            match_reason=match.match_reason,
            suggested_product_variant_id=match.suggested_product_variant_id,
            assigned_product_variant_id=match.assigned_product_variant_id,
            assigned_product_name=product.name if product is not None else None,
            assigned_variant_label=self._variant_label(match),
            status=match.status,
            resolved_by_user_id=match.resolved_by_user_id,
            resolved_at=match.resolved_at,
            replayed_at=match.replayed_at,
            replay_result=match.replay_result,
            created_at=match.created_at,
            updated_at=match.updated_at,
        )

    def record(
        self,
        session: Session,
        payload: PendingProductMatchCreate,
    ) -> PendingProductMatchResponse:
        match = self.repository.get_by_source(
            session,
            platform_code=payload.platform_code,
            external_id=payload.external_id,
        )
        values = payload.model_dump(mode="json")
        if match is None:
            match = PendingProductMatch(**values, status="pending")
            session.add(match)
        else:
            match.title = payload.title
            match.product_url = str(payload.product_url)
            match.match_payload = values["match_payload"]
            match.listing_payload = values["listing_payload"]
            match.match_confidence = payload.match_confidence
            match.match_reason = payload.match_reason
            match.suggested_product_variant_id = payload.suggested_product_variant_id
            if match.assigned_product_variant_id is None:
                match.status = "pending"
        session.commit()
        session.refresh(match)
        match = self.repository.get(session, match.id)
        assert match is not None
        return self.as_response(match)

    def list(
        self,
        session: Session,
        *,
        query: str | None,
        platform_code: str | None,
        match_status: str | None,
        page: int,
        page_size: int,
    ) -> PendingProductMatchListResponse:
        items, total = self.repository.list(
            session,
            query=query,
            platform_code=platform_code,
            status=match_status,
            page=page,
            page_size=page_size,
        )
        return PendingProductMatchListResponse(
            items=[self.as_response(item) for item in items],
            page=page,
            page_size=page_size,
            total_items=total,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def resolve(
        self,
        session: Session,
        *,
        match_id: int,
        user_id: int,
        payload: PendingProductMatchResolve,
    ) -> PendingProductMatchResponse:
        match = self.repository.get(session, match_id)
        if match is None:
            raise HTTPException(status_code=404, detail="Pending product match not found.")
        variant = self.acquisition_repository.get_product_variant(
            session, payload.product_variant_id
        )
        if (
            variant is None
            or not variant.is_active
            or variant.canonical_product is None
            or not variant.canonical_product.is_active
        ):
            raise HTTPException(status_code=409, detail="Selected catalog variant is unavailable.")
        match.assigned_product_variant_id = variant.id
        match.resolved_by_user_id = user_id
        match.resolved_at = datetime.now(timezone.utc)
        match.status = "resolved"
        match.replay_result = {}
        session.commit()
        refreshed = self.repository.get(session, match.id)
        assert refreshed is not None
        return self.as_response(refreshed)

    def replay(
        self,
        session: Session,
        *,
        match_id: int,
    ) -> PendingProductMatchReplayResponse:
        match = self.repository.get(session, match_id)
        if match is None:
            raise HTTPException(status_code=404, detail="Pending product match not found.")
        if match.assigned_product_variant_id is None:
            raise HTTPException(status_code=409, detail="Resolve the catalog variant before replaying this item.")
        raw_payload = {
            **match.listing_payload,
            "product_variant_id": match.assigned_product_variant_id,
        }
        try:
            listing = AcquisitionListingInput.model_validate(raw_payload)
        except ValidationError as error:
            details = [
                {
                    "field": ".".join(str(part) for part in item["loc"]),
                    "message": item["msg"],
                    "type": item["type"],
                }
                for item in error.errors(include_url=False)
            ]
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"message": "Stored listing payload is invalid.", "errors": details},
            ) from error
        result = self.acquisition_service.ingest_listing(session, listing)
        match = self.repository.get(session, match_id)
        assert match is not None
        match.status = "replayed"
        match.replayed_at = datetime.now(timezone.utc)
        match.replay_result = result.model_dump(mode="json")
        session.commit()
        refreshed = self.repository.get(session, match.id)
        assert refreshed is not None
        return PendingProductMatchReplayResponse(
            pending_match=self.as_response(refreshed),
            ingestion=result,
        )

    def delete(
        self,
        session: Session,
        *,
        match_id: int,
    ) -> None:
        """Permanently remove one administrator-reviewed queue item."""

        match = self.repository.get(session, match_id)
        if match is None:
            raise HTTPException(
                status_code=404,
                detail="Pending product match not found.",
            )

        self.repository.delete(session, match)
        session.commit()

    def variant_options(
        self,
        session: Session,
        *,
        query: str,
        limit: int,
    ) -> ProductVariantOptionListResponse:
        rows = self.repository.variant_options(session, query=query, limit=limit)
        return ProductVariantOptionListResponse(
            items=[
                ProductVariantOption(
                    id=variant.id,
                    canonical_product_id=product.id,
                    product_name=product.name,
                    brand_name=brand.name if brand is not None else None,
                    model=product.model,
                    sku=variant.sku,
                    ram_gb=variant.ram_gb,
                    storage_gb=variant.storage_gb,
                    color=variant.color,
                )
                for variant, product, brand in rows
            ]
        )
