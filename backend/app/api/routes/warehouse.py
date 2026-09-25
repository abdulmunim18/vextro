from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import BigInteger, Sequence, func, select, text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.canonical_product import CanonicalProduct
from app.models.platform import Platform
from app.models.price_history import PriceHistory
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing
from app.models.product_variant import ProductVariant
from app.models.scrape_run import ScrapeRun

router = APIRouter(prefix="/warehouse", tags=["Data Warehouse & Monitoring"])


# --- Schemas ---

class ScrapeRunStartPayload(BaseModel):
    platform: str = Field(..., description="Marketplace name, e.g. PriceOye or Daraz")
    triggered_by: str = Field(default="MANUAL", description="SCHEDULED, MANUAL, or PIPELINE")


class ScrapeRunFinishPayload(BaseModel):
    status: str = Field(..., description="SUCCESS, FAILED, or CANCELLED")
    items_scraped: int = Field(default=0, ge=0)
    items_failed: int = Field(default=0, ge=0)
    error_message: str | None = Field(default=None)


class ScrapeRunResponse(BaseModel):
    id: int
    platform: str
    status: str
    triggered_by: str
    items_scraped: int
    items_failed: int
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None


class WarehouseMetricsResponse(BaseModel):
    canonical_products_count: int
    product_variants_count: int
    product_listings_count: int
    price_history_observations_count: int
    total_scrape_runs_count: int
    platform_summary: list[dict[str, Any]]
    data_health: dict[str, Any]


class AuditReportResponse(BaseModel):
    audit_timestamp: datetime
    total_canonical_products: int
    total_listings: int
    unlinked_listings_count: int
    missing_image_listings_count: int
    listings_without_price_history_count: int
    health_score_percentage: float
    status: str


# --- Endpoints ---

@router.post("/scrape-runs/start", response_model=ScrapeRunResponse, status_code=status.HTTP_201_CREATED)
def start_scrape_run(
    payload: ScrapeRunStartPayload,
    db: Session = Depends(get_db),
) -> ScrapeRun:
    """Register the start of a scraper execution run."""
    run = ScrapeRun(
        platform=payload.platform,
        status="RUNNING",
        triggered_by=payload.triggered_by,
        items_scraped=0,
        items_failed=0,
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.post("/scrape-runs/{run_id}/finish", response_model=ScrapeRunResponse)
def finish_scrape_run(
    run_id: int,
    payload: ScrapeRunFinishPayload,
    db: Session = Depends(get_db),
) -> ScrapeRun:
    """Mark a scrape run complete with final counts and status."""
    run = db.get(ScrapeRun, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Scrape run ID {run_id} not found.",
        )

    run.status = payload.status
    run.items_scraped = payload.items_scraped
    run.items_failed = payload.items_failed
    run.error_message = payload.error_message
    run.finished_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(run)
    return run


@router.get("/scrape-runs", response_model=list[ScrapeRunResponse])
def list_scrape_runs(
    platform: str | None = Query(None, description="Filter by platform name"),
    status_filter: str | None = Query(None, alias="status", description="Filter by status"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> Sequence[ScrapeRun]:
    """Retrieve audit history log of past scraper execution runs."""
    stmt = select(ScrapeRun).order_by(ScrapeRun.started_at.desc())

    if platform:
        stmt = stmt.where(ScrapeRun.platform.ilike(platform))
    if status_filter:
        stmt = stmt.where(ScrapeRun.status.ilike(status_filter))

    stmt = stmt.limit(limit).offset(offset)
    return db.scalars(stmt).all()


@router.get("/metrics", response_model=WarehouseMetricsResponse)
def get_warehouse_metrics(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Get high-level warehouse statistics, storage footprint, and system health status."""
    canonical_count = db.scalar(select(func.count(CanonicalProduct.id))) or 0
    variant_count = db.scalar(select(func.count(ProductVariant.id))) or 0
    listing_count = db.scalar(select(func.count(ProductListing.id))) or 0
    history_count = db.scalar(select(func.count(PriceHistory.id))) or 0
    scrape_run_count = db.scalar(select(func.count(ScrapeRun.id))) or 0

    # Platform summary
    platforms = db.scalars(select(Platform)).all()
    platform_summary = []

    for p in platforms:
        p_listings_count = db.scalar(
            select(func.count(ProductListing.id)).where(ProductListing.platform_id == p.id)
        ) or 0

        # Last scrape run for platform
        last_run = db.scalar(
            select(ScrapeRun)
            .where(ScrapeRun.platform.ilike(p.name))
            .order_by(ScrapeRun.started_at.desc())
            .limit(1)
        )

        platform_summary.append({
            "id": p.id,
            "name": p.name,
            "code": p.code,
            "domain": p.base_url,
            "listings_count": p_listings_count,
            "last_scrape_at": last_run.started_at.isoformat() if last_run else None,
            "last_scrape_status": last_run.status if last_run else "NO_RUNS",
            "last_scrape_items": last_run.items_scraped if last_run else 0,
        })

    # Data health metrics
    missing_images_count = db.scalar(
        select(func.count(ProductListing.id))
        .outerjoin(ProductImage, ProductImage.listing_id == ProductListing.id)
        .where(ProductImage.id.is_(None))
    ) or 0

    listings_no_history = db.scalar(
        select(func.count(ProductListing.id))
        .outerjoin(PriceHistory, PriceHistory.listing_id == ProductListing.id)
        .where(PriceHistory.id.is_(None))
    ) or 0

    total_items = max(listing_count, 1)
    health_score = round(max(0.0, 100.0 - ((missing_images_count + listings_no_history) / total_items * 100.0)), 1)

    return {
        "canonical_products_count": canonical_count,
        "product_variants_count": variant_count,
        "product_listings_count": listing_count,
        "price_history_observations_count": history_count,
        "total_scrape_runs_count": scrape_run_count,
        "platform_summary": platform_summary,
        "data_health": {
            "health_score_percentage": health_score,
            "missing_images_count": missing_images_count,
            "listings_without_price_history_count": listings_no_history,
            "status": "EXCELLENT" if health_score >= 90 else "GOOD" if health_score >= 70 else "NEEDS_ATTENTION",
        },
    }


@router.post("/maintenance/audit", response_model=AuditReportResponse)
def run_warehouse_data_audit(
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Execute a data integrity audit scan over canonical products, listings, and price observations."""
    total_canonical = db.scalar(select(func.count(CanonicalProduct.id))) or 0
    total_listings = db.scalar(select(func.count(ProductListing.id))) or 0

    # Unlinked variants / listings check
    unlinked_listings = db.scalar(
        select(func.count(ProductListing.id))
        .where(ProductListing.product_variant_id.is_(None))
    ) or 0

    # Missing images
    missing_images = db.scalar(
        select(func.count(ProductListing.id))
        .outerjoin(ProductImage, ProductImage.listing_id == ProductListing.id)
        .where(ProductImage.id.is_(None))
    ) or 0


    # Missing price history
    no_history = db.scalar(
        select(func.count(ProductListing.id))
        .outerjoin(PriceHistory, PriceHistory.listing_id == ProductListing.id)
        .where(PriceHistory.id.is_(None))
    ) or 0

    total_denom = max(total_listings, 1)
    issues_count = unlinked_listings + missing_images + no_history
    health_score = max(0.0, round(100.0 - (issues_count / total_denom * 100.0), 1))

    return {
        "audit_timestamp": datetime.now(timezone.utc),
        "total_canonical_products": total_canonical,
        "total_listings": total_listings,
        "unlinked_listings_count": unlinked_listings,
        "missing_image_listings_count": missing_images,
        "listings_without_price_history_count": no_history,
        "health_score_percentage": health_score,
        "status": "HEALTHY" if health_score >= 80 else "DEGRADED",
    }
