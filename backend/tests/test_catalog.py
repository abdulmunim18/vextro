from fastapi.testclient import TestClient


def test_list_platforms(
    client: TestClient,
) -> None:
    """Return the active VEXTRO marketplaces."""

    response = client.get(
        "/api/v1/platforms"
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert len(items) == 2

    assert [
        platform["code"]
        for platform in items
    ] == [
        "daraz",
        "priceoye",
    ]

    assert all(
        platform["is_active"] is True
        for platform in items
    )


def test_list_categories_with_hierarchy(
    client: TestClient,
) -> None:
    """Return active categories with parent relationships."""

    response = client.get(
        "/api/v1/categories"
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert len(items) == 8

    categories_by_slug = {
        category["slug"]: category
        for category in items
    }

    electronics = categories_by_slug[
        "electronics"
    ]

    mobile_phones = categories_by_slug[
        "mobile-phones"
    ]

    assert electronics["parent_id"] is None

    assert (
        mobile_phones["parent_id"]
        == electronics["id"]
    )

    assert all(
        category["is_active"] is True
        for category in items
    )


def test_list_brands_in_alphabetical_order(
    client: TestClient,
) -> None:
    """Return active brands in alphabetical order."""

    response = client.get(
        "/api/v1/brands"
    )

    assert response.status_code == 200

    items = response.json()["items"]

    assert len(items) == 17

    brand_names = [
        brand["name"]
        for brand in items
    ]

    assert brand_names == sorted(
    brand_names,
    key=str.casefold,
)

    assert "Apple" in brand_names
    assert "Samsung" in brand_names
    assert "Xiaomi" in brand_names

    assert all(
        brand["is_active"] is True
        for brand in items
    )