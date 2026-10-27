from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    BigInteger,
    event,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.services.variant_identity import (
    IDENTITY,
    configuration_key,
    variant_identity,
)

if TYPE_CHECKING:
    from app.models.canonical_product import CanonicalProduct
    from app.models.price_forecast import PriceForecast
    from app.models.product_listing import ProductListing


class ProductVariant(Base):
    """A specific configuration of a canonical product."""

    __tablename__ = "product_variants"

    __table_args__ = (
        # One variant per product, identity, colour and condition. The
        # identity includes RAM and storage, so this also covers what the
        # older RAM-and-storage rule did, and lets a Wi-Fi and a cellular
        # tablet of one memory size exist side by side.
        UniqueConstraint(
            "canonical_product_id",
            "configuration_key",
            "color",
            "condition",
            name="uq_product_variants_identity",
        ),
        CheckConstraint(
            "ram_gb IS NULL OR ram_gb > 0",
            name="ck_product_variants_ram_positive",
        ),
        CheckConstraint(
            "storage_gb IS NULL OR storage_gb > 0",
            name="ck_product_variants_storage_positive",
        ),
    )

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(),
        primary_key=True,
    )

    canonical_product_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "canonical_products.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    sku: Mapped[str | None] = mapped_column(
        String(120),
        nullable=True,
        unique=True,
        index=True,
    )

    ram_gb: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    storage_gb: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    color: Mapped[str | None] = mapped_column(
        String(80),
        nullable=True,
    )

    condition: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
        server_default=text("'new'"),
    )

    variant_attributes: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=text("'{}'::jsonb"),
    )

    # The variant's identity attributes as one string, such as
    # "ram_gb=8|storage_gb=256". Filled automatically on every save from
    # ``variant_attributes["identity"]`` and the RAM and storage columns.
    configuration_key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=text("''"),
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    canonical_product: Mapped["CanonicalProduct"] = relationship(
        back_populates="variants",
    )
    listings: Mapped[list["ProductListing"]] = relationship(
        back_populates="product_variant",
    )
    price_forecasts: Mapped[list["PriceForecast"]] = relationship(
        back_populates="product_variant",
        cascade="all, delete-orphan",
    )


@event.listens_for(ProductVariant, "before_insert")
@event.listens_for(ProductVariant, "before_update")
def _keep_identity_in_step(_mapper, _connection, variant: ProductVariant) -> None:
    """Derive the identity and its key whenever a variant is written.

    Whoever creates or edits a variant (the resolver, an administrator, a
    seed script, a test) only has to set the attributes; the stored
    identity and key cannot drift from them.
    """

    identity = variant_identity(
        variant.variant_attributes,
        ram_gb=variant.ram_gb,
        storage_gb=variant.storage_gb,
    )
    attributes = dict(variant.variant_attributes or {})

    if identity:
        attributes[IDENTITY] = identity
    else:
        attributes.pop(IDENTITY, None)

    if attributes != (variant.variant_attributes or {}):
        variant.variant_attributes = attributes

    key = configuration_key(identity)
    if variant.configuration_key != key:
        variant.configuration_key = key

