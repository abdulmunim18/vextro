"""Two marketplaces that both publish exact model names, and one phone."""

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.canonical_product import CanonicalProduct
from tests.test_smartphone_sync import (  # noqa: F401 - shared fixtures
    configure_ingestion_key,
    discover,
    discovered_products,
)


def product_name(database_session: Session, product_id: object) -> str:
    product = database_session.get(CanonicalProduct, int(product_id))
    database_session.refresh(product)

    return product.name


# --------------------------------------------------------------------------
# One phone, two spellings
# --------------------------------------------------------------------------


def exact(platform_code: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "platform_code": platform_code,
        "brand": "Samsung",
        "color": "Black",
        "specifications": {"ram": "8GB", "storage_capacity": "256GB"},
        "exact_model_title": True,
    }
    payload.update(overrides)

    return payload


def test_one_shop_writing_5g_and_another_not_is_still_one_phone(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],  # noqa: F811
) -> None:
    """Shophive sells the "Reno 15F 5G"; PriceOye calls it the "Reno 15F"."""

    token = uuid4().hex[:8]

    priceoye = discover(
        client,
        discovered_products,
        external_id=f"SPELL-{token}-PO",
        title=f"Samsung Galaxy Sp{token}",
        **exact("priceoye"),
    )
    shophive = discover(
        client,
        discovered_products,
        external_id=f"SPELL-{token}-SH",
        title=f"Samsung Galaxy Sp{token} 5G",
        **exact("shophive"),
    )

    assert shophive["canonical_product_id"] == priceoye["canonical_product_id"]
    assert shophive["product_variant_id"] == priceoye["product_variant_id"]
    assert len(discovered_products) == 1


def test_the_spelling_runs_the_other_way_too(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    token = uuid4().hex[:8]

    priceoye = discover(
        client,
        discovered_products,
        external_id=f"REV-{token}-PO",
        title=f"Samsung Galaxy Rv{token} 5G",
        **exact("priceoye"),
    )
    shophive = discover(
        client,
        discovered_products,
        external_id=f"REV-{token}-SH",
        title=f"Samsung Galaxy Rv{token}",
        **exact("shophive"),
    )

    assert shophive["canonical_product_id"] == priceoye["canonical_product_id"]


def test_one_shop_selling_both_keeps_them_apart(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    """A shop that lists the 4G and the 5G phone means two phones."""

    token = uuid4().hex[:8]

    plain = discover(
        client,
        discovered_products,
        external_id=f"BOTH-{token}-4G",
        title=f"Samsung Galaxy Bo{token}",
        **exact("shophive"),
    )
    fifth = discover(
        client,
        discovered_products,
        external_id=f"BOTH-{token}-5G",
        title=f"Samsung Galaxy Bo{token} 5G",
        **exact("shophive"),
    )

    assert plain["canonical_product_id"] != fifth["canonical_product_id"]


def test_a_shops_two_phones_stay_apart_inside_one_crawl_batch(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    """Listings are delivered in batches, after the batch was resolved.

    The phone below already exists because a seller listed it. PriceOye's
    crawl then resolves its 4G page and, before any PriceOye listing has
    been stored, its 5G page. The 5G page must not join the 4G phone.
    """

    token = uuid4().hex[:8]

    seller = discover(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"BATCH-{token}-SELLER",
        title=f"Samsung Galaxy Bt{token} 8GB 256GB Black",
        brand="Samsung",
        specifications={"ram": "8GB", "storage_capacity": "256GB"},
    )
    plain = discover(
        client,
        discovered_products,
        external_id=f"BATCH-{token}-4G",
        title=f"Samsung Galaxy Bt{token}",
        **exact("priceoye"),
    )
    fifth = discover(
        client,
        discovered_products,
        external_id=f"BATCH-{token}-5G",
        title=f"Samsung Galaxy Bt{token} 5G",
        **exact("priceoye"),
    )

    assert plain["canonical_product_id"] == seller["canonical_product_id"]
    assert fifth["canonical_product_id"] != plain["canonical_product_id"]


def test_a_look_alike_model_is_not_joined_just_because_shops_differ(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    """Only "5G" is forgiven between shops; "Pro" still means another phone."""

    token = uuid4().hex[:8]

    base = discover(
        client,
        discovered_products,
        external_id=f"PRO-{token}-PO",
        title=f"Samsung Galaxy Pr{token}",
        **exact("priceoye"),
    )
    pro = discover(
        client,
        discovered_products,
        external_id=f"PRO-{token}-SH",
        title=f"Samsung Galaxy Pr{token} Pro 5G",
        **exact("shophive"),
    )

    assert pro["canonical_product_id"] != base["canonical_product_id"]


# --------------------------------------------------------------------------
# Which marketplace names the phone
# --------------------------------------------------------------------------


def test_a_phone_keeps_one_name_however_often_the_shops_are_crawled(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],  # noqa: F811
) -> None:
    """Without an order of preference the name would flip at every crawl."""

    token = uuid4().hex[:8]

    seller = discover(
        client,
        discovered_products,
        platform_code="daraz",
        external_id=f"NAME-{token}-SELLER",
        title=f"Samsung Mobile Nx{token} 8GB 256GB",
        brand="Samsung",
        specifications={"ram": "8GB", "storage_capacity": "256GB"},
    )
    product_id = seller["canonical_product_id"]
    assert product_name(database_session, product_id) == f"Samsung Nx{token}"

    def shophive() -> None:
        result = discover(
            client,
            discovered_products,
            external_id=f"NAME-{token}-SH",
            title=f"Samsung Galaxy Nx{token} 5G",
            **exact("shophive"),
        )
        assert result["canonical_product_id"] == product_id

    def priceoye() -> None:
        result = discover(
            client,
            discovered_products,
            external_id=f"NAME-{token}-PO",
            title=f"Samsung Galaxy Nx{token}",
            **exact("priceoye"),
        )
        assert result["canonical_product_id"] == product_id

    # Only a seller and Shophive list it: Shophive's name is the exact one.
    shophive()
    assert product_name(database_session, product_id) == (
        f"Samsung Galaxy Nx{token} 5G"
    )

    # PriceOye lists it too, and its spelling is the catalogue's default.
    priceoye()
    assert product_name(database_session, product_id) == (
        f"Samsung Galaxy Nx{token}"
    )

    # Later crawls, in either order, change nothing.
    shophive()
    priceoye()
    shophive()
    assert product_name(database_session, product_id) == (
        f"Samsung Galaxy Nx{token}"
    )
