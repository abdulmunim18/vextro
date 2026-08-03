from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes.product_catalog import router as product_catalog_router

from app.api.routes.health import router as health_router
from app.core.config import settings

from app.api.routes.access import router as access_router

from app.api.routes.auth import router as auth_router
from app.api.routes.catalog import router as catalog_router
from app.api.routes.price_intelligence import (
    router as price_intelligence_router,
)
from app.api.routes.price_alerts import (
    router as price_alerts_router,
)

app = FastAPI(
    title=settings.app_name,
    description="AI-powered e-commerce market intelligence system",
    version=settings.app_version,
    debug=settings.app_debug,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
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

@app.get("/", tags=["Root"])
def root() -> dict[str, str]:
    return {
        "message": "Welcome to VEXTRO API",
    }