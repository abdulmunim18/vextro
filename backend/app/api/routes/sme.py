"""API routes for SME business intelligence."""

from fastapi import (
    APIRouter,
    Depends,
    File,
    Path,
    Query,
    UploadFile,
    status,
)
from sqlalchemy.orm import Session

from app.api.dependencies.roles import sme_or_admin
from app.core.database import get_db
from app.models.user import User
from app.schemas.sme import (
    BusinessProductCreate,
    BusinessProductListResponse,
    BusinessProductResponse,
    BusinessProductUpdate,
    CompetitorWatchlistCreate,
    CompetitorWatchlistListResponse,
    CompetitorWatchlistResponse,
    CompetitorWatchlistStatusUpdate,
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.schemas.sales import (
    SalesImportListResponse,
    SalesImportResponse,
    SalesImportResultResponse,
    SalesRecordListResponse,
)
from app.services.sales_service import SalesService
from app.services.sme_service import SMEService


router = APIRouter(
    prefix="/api/v1/sme",
    tags=["sme-business-intelligence"],
)


sme_service = SMEService()
sales_service = SalesService()


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization_endpoint(
    payload: OrganizationCreate,
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> OrganizationResponse:
    """Create an organization owned by the current SME."""

    return sme_service.create_organization(
        database_session,
        user_id=current_user.id,
        payload=payload,
    )


@router.get(
    "/organizations",
    response_model=OrganizationListResponse,
)
def list_organizations_endpoint(
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> OrganizationListResponse:
    """Return organizations accessible to the current user."""

    return sme_service.list_organizations(
        database_session,
        user_id=current_user.id,
    )


@router.get(
    "/organizations/{organization_id}",
    response_model=OrganizationResponse,
)
def read_organization_endpoint(
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> OrganizationResponse:
    """Return one organization accessible to the user."""

    return sme_service.read_organization(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
    )


@router.patch(
    "/organizations/{organization_id}",
    response_model=OrganizationResponse,
)
def update_organization_endpoint(
    payload: OrganizationUpdate,
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> OrganizationResponse:
    """Update an organization accessible to the user."""

    return sme_service.update_organization(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.post(
    "/organizations/{organization_id}/products",
    response_model=BusinessProductResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_business_product_endpoint(
    payload: BusinessProductCreate,
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> BusinessProductResponse:
    """Create a product inside an SME organization."""

    return sme_service.create_business_product(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get(
    "/organizations/{organization_id}/products",
    response_model=BusinessProductListResponse,
)
def list_business_products_endpoint(
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    query: str | None = Query(
        default=None,
        max_length=255,
        description="Search by product name or SKU.",
    ),
    is_active: bool | None = Query(
        default=None,
        description="Filter by active status.",
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Pagination page.",
    ),
    page_size: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Items returned per page.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> BusinessProductListResponse:
    """Return filtered organization products."""

    return sme_service.list_business_products(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
        query=query,
        is_active=is_active,
        page=page,
        page_size=page_size,
    )


@router.get(
    (
        "/organizations/{organization_id}"
        "/products/{product_id}"
    ),
    response_model=BusinessProductResponse,
)
def read_business_product_endpoint(
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    product_id: int = Path(
        ge=1,
        description="Business product ID.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> BusinessProductResponse:
    """Return one business product."""

    return sme_service.read_business_product(
        database_session,
        organization_id=organization_id,
        product_id=product_id,
        user_id=current_user.id,
    )


@router.patch(
    (
        "/organizations/{organization_id}"
        "/products/{product_id}"
    ),
    response_model=BusinessProductResponse,
)
def update_business_product_endpoint(
    payload: BusinessProductUpdate,
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    product_id: int = Path(
        ge=1,
        description="Business product ID.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> BusinessProductResponse:
    """Update one organization product."""

    return sme_service.update_business_product(
        database_session,
        organization_id=organization_id,
        product_id=product_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.post(
    (
        "/organizations/{organization_id}"
        "/competitors"
    ),
    response_model=CompetitorWatchlistResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_competitor_watchlist_endpoint(
    payload: CompetitorWatchlistCreate,
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> CompetitorWatchlistResponse:
    """Add a marketplace listing to competitor monitoring."""

    return sme_service.create_watchlist_entry(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get(
    (
        "/organizations/{organization_id}"
        "/competitors"
    ),
    response_model=CompetitorWatchlistListResponse,
)
def list_competitor_watchlist_endpoint(
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    is_active: bool | None = Query(
        default=None,
        description="Filter by monitoring status.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> CompetitorWatchlistListResponse:
    """Return competitor entries for an organization."""

    return sme_service.list_watchlist_entries(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
        is_active=is_active,
    )


@router.patch(
    (
        "/organizations/{organization_id}"
        "/competitors/{watchlist_id}/status"
    ),
    response_model=CompetitorWatchlistResponse,
)
def update_competitor_watchlist_status_endpoint(
    payload: CompetitorWatchlistStatusUpdate,
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    watchlist_id: int = Path(
        ge=1,
        description="Competitor watchlist entry ID.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> CompetitorWatchlistResponse:
    """Activate or deactivate competitor monitoring."""

    return sme_service.update_watchlist_status(
        database_session,
        organization_id=organization_id,
        watchlist_id=watchlist_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.post(
    (
        "/organizations/{organization_id}"
        "/sales/imports"
    ),
    response_model=SalesImportResultResponse,
    status_code=status.HTTP_201_CREATED,
)
async def import_sales_csv_endpoint(
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    file: UploadFile = File(
        description=(
            "UTF-8 CSV containing SME sales rows."
        ),
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> SalesImportResultResponse:
    """Upload, validate and store one SME sales CSV."""

    try:
        file_content = await file.read()
        original_filename = file.filename

    finally:
        await file.close()

    return sales_service.process_csv_import(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
        filename=original_filename,
        file_content=file_content,
    )


@router.get(
    (
        "/organizations/{organization_id}"
        "/sales/imports"
    ),
    response_model=SalesImportListResponse,
)
def list_sales_imports_endpoint(
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Pagination page.",
    ),
    page_size: int = Query(
        default=10,
        ge=1,
        le=100,
        description="Items returned per page.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> SalesImportListResponse:
    """Return paginated sales imports for an organization."""

    return sales_service.list_sales_imports(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )


@router.get(
    (
        "/organizations/{organization_id}"
        "/sales/imports/{sales_import_id}"
    ),
    response_model=SalesImportResponse,
)
def read_sales_import_endpoint(
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    sales_import_id: int = Path(
        ge=1,
        description="Sales import ID.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> SalesImportResponse:
    """Return one sales import belonging to an organization."""

    return sales_service.read_sales_import(
        database_session,
        organization_id=organization_id,
        sales_import_id=sales_import_id,
        user_id=current_user.id,
    )


@router.get(
    (
        "/organizations/{organization_id}"
        "/sales/imports/{sales_import_id}"
        "/records"
    ),
    response_model=SalesRecordListResponse,
)
def list_sales_records_endpoint(
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    sales_import_id: int = Path(
        ge=1,
        description="Sales import ID.",
    ),
    page: int = Query(
        default=1,
        ge=1,
        description="Pagination page.",
    ),
    page_size: int = Query(
        default=20,
        ge=1,
        le=100,
        description="Items returned per page.",
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> SalesRecordListResponse:
    """Return accepted sales records from one import."""

    return sales_service.list_sales_records(
        database_session,
        organization_id=organization_id,
        sales_import_id=sales_import_id,
        user_id=current_user.id,
        page=page,
        page_size=page_size,
    )
