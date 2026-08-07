from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal

from app.core.database import get_db
from app.models.product_listing import ProductListing
from app.models.canonical_product import CanonicalProduct
from app.models.price_history import PriceHistory

# Create the router for the ingestion URL
router = APIRouter(prefix="/ingest", tags=["Data Ingestion"])

# Define the exact data structure we expect from Scrapy
class ScrapedItemPayload(BaseModel):
    platform: str
    external_id: str
    model: str
    product_url: str
    price: float
    currency: str = "PKR"
    color: Optional[str] = "N/A"
    variant: Optional[str] = "Standard"
    availability: str
    is_available: bool
    warranty: Optional[str] = "Official Brand Warranty"

@router.post("/priceoye", status_code=status.HTTP_201_CREATED)
def ingest_priceoye_listing(payload: ScrapedItemPayload, db: Session = Depends(get_db)):
    try:
        # 1. Search for an existing listing using the unique slug (external_id)
        listing = db.query(ProductListing).filter(
            ProductListing.external_id == payload.external_id
        ).first()

        if listing:
            # 2. Update price and stock if the product already exists
            old_price = float(listing.current_price)
            listing.current_price = Decimal(str(payload.price))
            listing.is_available = payload.is_available
            listing.last_seen_at = datetime.utcnow()

            # Record a price history snapshot if the price went up or down
            if old_price != payload.price:
                history_entry = PriceHistory(
                    listing_id=listing.id,
                    price=Decimal(str(payload.price)),
                    captured_at=datetime.utcnow()
                )
                db.add(history_entry)

            db.commit()
            return {"status": "success", "action": "updated", "listing_id": listing.id}

        else:
            # 3. Create a brand new Canonical Product if we have never seen it before
            canonical = CanonicalProduct(
                category_id=1,  # Temporary default category ID
                name=payload.model,
                slug=payload.external_id,
                model=payload.model,
                specifications={"color": payload.color, "variant": payload.variant}
            )
            db.add(canonical)
            db.flush() 

            # 4. Create the attached Product Listing for PriceOye
            new_listing = ProductListing(
                platform_id=1,  # Temporary default ID for PriceOye
                product_variant_id=canonical.id,
                external_id=payload.external_id,
                title=payload.model,
                product_url=payload.product_url,
                current_price=Decimal(str(payload.price)),
                currency=payload.currency,
                warranty=payload.warranty,
                is_available=payload.is_available,
                raw_payload=payload.dict()
            )
            db.add(new_listing)
            db.commit()
            
            return {"status": "success", "action": "created", "listing_id": new_listing.id}

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database insertion failed: {str(e)}"
        )