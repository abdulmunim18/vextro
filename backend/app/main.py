from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api.routes import ingest
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.product_catalog import router as product_catalog_router

from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.scraper_supervisor import (
    scraper_scheduler_supervisor,
)

from app.api.routes.access import router as access_router

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.acquisition import router as acquisition_router
from app.api.routes.forecast_integration import router as forecast_integration_router
from app.api.routes.notifications import (
    router as notifications_router,
)
from app.api.routes.assistant import router as assistant_router
from app.api.routes.sme import router as sme_router
from app.api.routes.admin_catalog import (
    router as admin_catalog_router,
)
from app.api.routes.price_intelligence import (
    router as price_intelligence_router,
)
from app.api.routes.price_alerts import (
    router as price_alerts_router,
)
from app.api.routes.warehouse import router as warehouse_router
from app.api.routes.seller_trust import router as seller_trust_router

@asynccontextmanager
async def lifespan(_: FastAPI):
    """Optionally run the scraper scheduler for the life of the API.

    The scheduler runs as its own process and guards itself with an
    operating-system lock, so ``uvicorn --reload`` and multi-worker runs
    cannot produce two of them.
    """

    scraper_scheduler_supervisor.start()

    try:
        yield
    finally:
        scraper_scheduler_supervisor.stop()


app = FastAPI(
    title=settings.app_name,
    description="AI-powered e-commerce market intelligence system",
    version=settings.app_version,
    debug=settings.app_debug,
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health_router)
app.include_router(auth_router)
app.include_router(access_router)
app.include_router(catalog_router)
app.include_router(product_catalog_router)
app.include_router(price_alerts_router)
app.include_router(price_intelligence_router)
app.include_router(ingest.router, prefix="/api/v1")
app.include_router(warehouse_router, prefix="/api/v1")
app.include_router(admin_router)
app.include_router(admin_catalog_router)
app.include_router(acquisition_router)
app.include_router(forecast_integration_router)
app.include_router(sme_router)
app.include_router(notifications_router)
app.include_router(assistant_router)
app.include_router(seller_trust_router)

@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    return {
        "message": "Welcome to VEXTRO API",
    }
