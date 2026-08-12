from datetime import date
from decimal import Decimal
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
from fastapi.responses import Response
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
    CompetitorIntelligenceResponse,
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
    OrganizationUpdate,
)
from app.schemas.sales import (
    SalesAnalyticsResponse,
    SalesImportListResponse,
    SalesImportResponse,
    SalesImportResultResponse,
    SalesRecordListResponse,
)
from app.schemas.pricing_advisor import (
    PricingAdvisorResponse,
    PricingScenarioInput,
)
from app.services.pricing_advisor_service import (
    PricingAdvisorService,
)
from app.services.sales_service import SalesService
from app.services.sme_service import SMEService
from app.services.competitor_report_service import (
    build_competitor_pdf,
    build_competitor_xlsx,
)


router = APIRouter(
    prefix="/api/v1/sme",
    tags=["sme-business-intelligence"],
)


sme_service = SMEService()
sales_service = SalesService()
pricing_advisor_service = PricingAdvisorService()


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

@router.get(
    (
        "/organizations/{organization_id}"
        "/sales/analytics"
    ),
    response_model=SalesAnalyticsResponse,
    summary="Read SME Sales Analytics",
)
def read_sales_analytics_endpoint(
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    start_date: date | None = Query(
        default=None,
        description=(
            "Optional inclusive sales start date."
        ),
    ),
    end_date: date | None = Query(
        default=None,
        description=(
            "Optional inclusive sales end date."
        ),
    ),
    current_user: User = Depends(
        sme_or_admin,
    ),
    database_session: Session = Depends(
        get_db,
    ),
) -> SalesAnalyticsResponse:
    """Return aggregated sales analytics for one organization."""

    return sales_service.get_sales_analytics(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
    )


@router.post(
    (
        "/organizations/{organization_id}"
        "/pricing/scenarios"
    ),
    response_model=PricingAdvisorResponse,
    summary="Simulate SME Pricing Scenarios",
)
def simulate_pricing_scenarios_endpoint(
    payload: PricingScenarioInput,
    organization_id: int = Path(
        ge=1,
        description="Organization ID.",
    ),
    current_user: User = Depends(sme_or_admin),
    database_session: Session = Depends(get_db),
) -> PricingAdvisorResponse:
    """Compare -5%, unchanged and +5% advisory scenarios."""

    return pricing_advisor_service.simulate(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
        payload=payload,
    )


@router.get(
    (
        "/organizations/{organization_id}"
        "/competitor-intelligence"
    ),
    response_model=CompetitorIntelligenceResponse,
    summary="Read SME Competitor Intelligence",
)
def read_competitor_intelligence_endpoint(
    organization_id: int = Path(ge=1),
    risk_threshold_percentage: Decimal = Query(
        default=Decimal("5.00"),
        gt=0,
        le=100,
    ),
    current_user: User = Depends(sme_or_admin),
    database_session: Session = Depends(get_db),
) -> CompetitorIntelligenceResponse:
    """Return price gaps, timelines, risks and share estimates."""

    return sme_service.get_competitor_intelligence(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
        risk_threshold_percentage=risk_threshold_percentage,
    )


@router.get(
    (
        "/organizations/{organization_id}"
        "/competitor-intelligence/report"
    ),
    summary="Export SME Competitor Report",
)
def export_competitor_intelligence_report_endpoint(
    organization_id: int = Path(ge=1),
    report_format: str = Query(
        default="pdf",
        pattern="^(pdf|xlsx)$",
        alias="format",
    ),
    risk_threshold_percentage: Decimal = Query(
        default=Decimal("5.00"),
        gt=0,
        le=100,
    ),
    current_user: User = Depends(sme_or_admin),
    database_session: Session = Depends(get_db),
) -> Response:
    """Export the authorized organization's analysis as PDF or Excel."""

    organization = sme_service.read_organization(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
    )
    intelligence = sme_service.get_competitor_intelligence(
        database_session,
        organization_id=organization_id,
        user_id=current_user.id,
        risk_threshold_percentage=risk_threshold_percentage,
    )
    filename = (
        f"vextro-{organization.slug}-competitor-report."
        f"{report_format}"
    )

    if report_format == "xlsx":
        content = build_competitor_xlsx(
            organization_name=organization.name,
            intelligence=intelligence,
        )
        media_type = (
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        )
    else:
        content = build_competitor_pdf(
            organization_name=organization.name,
            intelligence=intelligence,
        )
        media_type = "application/pdf"

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
