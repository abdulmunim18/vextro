"""Internal API routes for marketplace acquisition ingestion."""

from fastapi import (
    APIRouter,
    Depends,
    Response,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies.ingestion import (
    require_ingestion_key,
)
from app.core.database import get_db
from app.schemas.acquisition import (
    AcquisitionListingInput,
    AcquisitionListingResponse,
    AcquisitionBulkInput,
    AcquisitionBulkResponse,
)
from app.schemas.product_matching import (
    ProductMatchRequest,
    ProductMatchResponse,
    ProductResolveRequest,
    ProductResolveResponse,
)
from app.schemas.pending_product_match import (
    PendingProductMatchCreate,
    PendingProductMatchResponse,
)
from app.schemas.scrape_monitoring import (
    ScrapeErrorInput,
    ScrapeErrorResponse,
    ScrapeRunDetailResponse,
    ScrapeRunFinishInput,
    ScrapeRunResponse,
    ScrapeRunStartInput,
)
from app.schemas.reviews import ReviewBatchInput, ReviewBatchResponse
from app.services.acquisition_service import (
    AcquisitionService,
)
from app.services.product_matching_service import (
    ProductMatchingService,
)
from app.services.product_resolution_service import (
    ProductResolutionService,
)
from app.services.pending_product_match_service import PendingProductMatchService
from app.services.scrape_monitoring_service import ScrapeMonitoringService
from app.services.review_service import ReviewService


router = APIRouter(
    prefix="/api/v1/internal/acquisition",
    tags=["internal-acquisition"],
    dependencies=[
        Depends(require_ingestion_key),
    ],
)


acquisition_service = AcquisitionService()
product_matching_service = ProductMatchingService()
product_resolution_service = ProductResolutionService()
scrape_monitoring_service = ScrapeMonitoringService()
review_service = ReviewService()
pending_product_match_service = PendingProductMatchService()


@router.post(
    "/runs",
    response_model=ScrapeRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def start_scrape_run(
    payload: ScrapeRunStartInput,
    database_session: Session = Depends(get_db),
) -> ScrapeRunResponse:
    """Create one persistent record for a spider execution."""

    return scrape_monitoring_service.start_run(database_session, payload)


@router.post(
    "/runs/{run_id}/items/ingested",
    response_model=ScrapeRunResponse,
)
def record_scrape_ingestion(
    run_id: int,
    database_session: Session = Depends(get_db),
) -> ScrapeRunResponse:
    """Count one item that completed secure acquisition."""

    return scrape_monitoring_service.record_ingested_item(
        database_session,
        run_id,
    )


@router.post(
    "/runs/{run_id}/errors",
    response_model=ScrapeErrorResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_scrape_error(
    run_id: int,
    payload: ScrapeErrorInput,
    database_session: Session = Depends(get_db),
) -> ScrapeErrorResponse:
    """Persist one bounded scraper rejection or failure."""

    return scrape_monitoring_service.record_error(
        database_session,
        run_id,
        payload,
    )


@router.patch(
    "/runs/{run_id}",
    response_model=ScrapeRunResponse,
)
def finish_scrape_run(
    run_id: int,
    payload: ScrapeRunFinishInput,
    database_session: Session = Depends(get_db),
) -> ScrapeRunResponse:
    """Finalize one spider execution and reconcile its counters."""

    return scrape_monitoring_service.finish_run(
        database_session,
        run_id,
        payload,
    )


@router.get(
    "/runs",
    response_model=list[ScrapeRunResponse],
)
def list_scrape_runs(
    limit: int = 20,
    database_session: Session = Depends(get_db),
) -> list[ScrapeRunResponse]:
    """Return recent runs for operational inspection."""

    safe_limit = max(1, min(limit, 100))
    return scrape_monitoring_service.list_runs(
        database_session,
        limit=safe_limit,
    )


@router.get(
    "/runs/{run_id}",
    response_model=ScrapeRunDetailResponse,
)
def get_scrape_run(
    run_id: int,
    database_session: Session = Depends(get_db),
) -> ScrapeRunDetailResponse:
    """Return one run and its durable error evidence."""

    return scrape_monitoring_service.get_run(database_session, run_id)


@router.post(
    "/reviews",
    response_model=ReviewBatchResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid ingestion key.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": "Marketplace listing could not be resolved.",
        },
        status.HTTP_422_UNPROCESSABLE_ENTITY: {
            "description": "Review batch validation failed.",
        },
    },
)
def ingest_marketplace_reviews(
    payload: ReviewBatchInput,
    database_session: Session = Depends(get_db),
) -> ReviewBatchResponse:
    """Persist a bounded, deduplicated review batch for one listing."""

    return review_service.ingest_batch(database_session, payload)


@router.post(
    "/listings",
    response_model=AcquisitionListingResponse,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_201_CREATED: {
            "description": (
                "A new marketplace listing was created."
            ),
        },
        status.HTTP_401_UNAUTHORIZED: {
            "description": "Invalid ingestion key.",
        },
        status.HTTP_404_NOT_FOUND: {
            "description": (
                "Platform or product variant was not found."
            ),
        },
        status.HTTP_409_CONFLICT: {
            "description": (
                "The product or variant is inactive."
            ),
        },
    },
)
def ingest_marketplace_listing(
    payload: AcquisitionListingInput,
    response: Response,
    database_session: Session = Depends(get_db),
) -> AcquisitionListingResponse:
    """Create or update one normalized marketplace listing."""

    result = acquisition_service.ingest_listing(
        database_session,
        payload,
    )

    if result.status == "created":
        response.status_code = (
            status.HTTP_201_CREATED
        )

    return result


@router.post(
    "/listings/bulk",
    response_model=AcquisitionBulkResponse,
    status_code=status.HTTP_200_OK,
)
def ingest_marketplace_listings_bulk(
    payload: AcquisitionBulkInput,
    database_session: Session = Depends(get_db),
) -> AcquisitionBulkResponse:
    """Ingest a bounded batch with isolated per-item transactions."""

    return acquisition_service.ingest_bulk(database_session, payload)


@router.post(
    "/match-product",
    response_model=ProductMatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Match marketplace product to VEXTRO variant",
)
def match_marketplace_product(
    payload: ProductMatchRequest,
    database_session: Session = Depends(get_db),
) -> ProductMatchResponse:
    """Match scraped marketplace product data to a catalog variant."""

    return product_matching_service.match_product(
        database_session,
        payload,
    )


@router.post(
    "/resolve-product",
    response_model=ProductResolveResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve or register a marketplace smartphone",
)
def resolve_marketplace_product(
    payload: ProductResolveRequest,
    database_session: Session = Depends(get_db),
) -> ProductResolveResponse:
    """Return a usable catalog variant, registering new phones when safe.

    This is the endpoint the crawler uses. Unlike ``/match-product`` it also
    covers newly discovered marketplace smartphones, so a crawl can grow the
    catalog instead of queueing every unknown phone for an administrator.
    """

    return product_resolution_service.resolve_product(
        database_session,
        payload,
    )


@router.post(
    "/pending-matches",
    response_model=PendingProductMatchResponse,
    status_code=status.HTTP_201_CREATED,
)
def record_pending_product_match(
    payload: PendingProductMatchCreate,
    database_session: Session = Depends(get_db),
) -> PendingProductMatchResponse:
    """Persist or refresh one unresolved marketplace product mapping."""

    return pending_product_match_service.record(database_session, payload)
