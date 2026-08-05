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
)
from app.services.acquisition_service import (
    AcquisitionService,
)


router = APIRouter(
    prefix="/api/v1/internal/acquisition",
    tags=["internal-acquisition"],
    dependencies=[
        Depends(require_ingestion_key),
    ],
)


acquisition_service = AcquisitionService()


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