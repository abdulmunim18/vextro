"""Authenticated seller-level trust-indicator endpoints."""

from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.api.dependencies.auth import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.seller_trust import SellerTrustResponse
from app.services.seller_trust_service import SellerTrustService


router = APIRouter(prefix="/api/v1/sellers", tags=["seller-trust"])
service = SellerTrustService()


@router.get("/{seller_id}/trust", response_model=SellerTrustResponse)
def get_seller_trust(
    seller_id: int = Path(..., ge=1),
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> SellerTrustResponse:
    """Read persisted evidence-based seller trust indicators."""
    return service.result(session, seller_id)


@router.post("/{seller_id}/trust/recalculate", response_model=SellerTrustResponse)
def recalculate_seller_trust(
    seller_id: int = Path(..., ge=1),
    session: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> SellerTrustResponse:
    """Idempotently recompute one seller's versioned trust analysis."""
    try:
        analysis = service.recalculate(session, seller_id)
        session.commit()
    except Exception:
        session.rollback()
        raise
    seller = service.repository.seller(session, seller_id)
    assert seller is not None
    return service.as_response(seller, analysis)
