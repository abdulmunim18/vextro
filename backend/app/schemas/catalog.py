from pydantic import BaseModel, ConfigDict


class CategoryResponse(BaseModel):
    """Public product-category information."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    parent_id: int | None
    name: str
    slug: str
    is_active: bool


class CategoryListResponse(BaseModel):
    """List of active categories."""

    items: list[CategoryResponse]


class BrandResponse(BaseModel):
    """Public product-brand information."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    name: str
    slug: str
    is_active: bool


class BrandListResponse(BaseModel):
    """List of active brands."""

    items: list[BrandResponse]


class PlatformResponse(BaseModel):
    """Public marketplace information."""

    model_config = ConfigDict(
        from_attributes=True,
    )

    id: int
    name: str
    code: str
    base_url: str
    is_active: bool


class PlatformListResponse(BaseModel):
    """List of active marketplaces."""

    items: list[PlatformResponse]