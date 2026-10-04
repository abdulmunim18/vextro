"""Persistence for marketplace product galleries.

Both the legacy ``/ingest`` route and the internal acquisition pipeline
store the same galleries, so the rules live here once: a listing keeps
exactly the images the marketplace published for it, and the canonical
product is seeded from them so the catalog has something to show.
"""

from __future__ import annotations

from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models.canonical_product import CanonicalProduct
from app.models.product_image import ProductImage
from app.models.product_listing import ProductListing


def sync_product_images(
    db: Session,
    *,
    listing: ProductListing,
    canonical_product: CanonicalProduct,
    image_urls: list[str],
    alt_text: str,
) -> None:
    """Persist one listing gallery and seed canonical product images."""

    if not image_urls:
        return

    listing_images = db.query(ProductImage).filter(
        ProductImage.listing_id == listing.id
    ).all()
    listing_images_by_url = {
        image.image_url: image for image in listing_images
    }

    for existing_image in listing_images:
        if existing_image.image_url not in image_urls:
            db.delete(existing_image)

    for sort_order, image_url in enumerate(image_urls):
        listing_image = listing_images_by_url.get(image_url)

        if listing_image is None:
            listing_image = ProductImage(
                listing_id=listing.id,
                image_url=image_url,
            )
            db.add(listing_image)

        listing_image.alt_text = alt_text[:255]
        listing_image.is_primary = sort_order == 0
        listing_image.sort_order = sort_order

    canonical_images = db.query(ProductImage).filter(
        ProductImage.canonical_product_id == canonical_product.id
    ).all()

    placeholder_hosts = {
        "placehold.co",
        "via.placeholder.com",
        "placeholder.com",
    }
    incoming_has_real_image = any(
        urlparse(image_url).netloc.lower() not in placeholder_hosts
        for image_url in image_urls
    )

    if incoming_has_real_image:
        retained_canonical_images: list[ProductImage] = []

        for canonical_image in canonical_images:
            image_host = urlparse(
                canonical_image.image_url
            ).netloc.lower()

            if image_host in placeholder_hosts:
                db.delete(canonical_image)
            else:
                retained_canonical_images.append(canonical_image)

        canonical_images = retained_canonical_images

    canonical_urls = {
        image.image_url for image in canonical_images
    }
    canonical_has_primary = any(
        image.is_primary for image in canonical_images
    )

    if canonical_images and not canonical_has_primary:
        min(
            canonical_images,
            key=lambda image: (image.sort_order, image.id),
        ).is_primary = True
        canonical_has_primary = True

    for sort_order, image_url in enumerate(image_urls):
        if image_url in canonical_urls:
            continue

        db.add(
            ProductImage(
                canonical_product_id=canonical_product.id,
                image_url=image_url,
                alt_text=alt_text[:255],
                is_primary=(
                    not canonical_has_primary and sort_order == 0
                ),
                sort_order=len(canonical_images) + sort_order,
            )
        )


__all__ = ["sync_product_images"]
