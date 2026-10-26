"""Appliances are matched on their maker's model code, not their name."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.canonical_product import CanonicalProduct
from app.services.category_profiles import appliance_name, profile_for
from tests.test_smartphone_sync import (  # noqa: F401 - shared fixtures
    configure_ingestion_key,
    discover,
    discovered_products,
    resolve,
)


# --------------------------------------------------------------------------
# Reading the code
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "code"),
    [
        # Friends Home points at it with "Model".
        ("MIDEA 1.5 TON DC INVERTER EXTREME AC Model MSAGC-18HRFN1", "MSAGC18HRFN1"),
        ("KENWOOD 1.5 TON E SMART ONYX T3 INVERTER AC Model KES-1866S", "KES1866S"),
        # PriceOye puts it in brackets.
        ("Sharp 1.0 Ton Inverter Split Series AC (AHX12SEV)", "AHX12SEV"),
        ("Gree 1.5 Ton Fairy Series Split Inverter  AC (GS18FITH1W)", "GS18FITH1W"),
        # Others write it among the words.
        ("TCL 55P635 55\" UHD 4K Smart LED Android TV", "55P635"),
        ("Samsung 43T5300 FHD Smart TV 2020 With Official Warranty", "43T5300"),
        ("Dawlance DWT-1775 PL 17Kg Top Load Fully Automatic Washing Machine", "DWT1775"),
        ("Philips 50PUT7406/98 4K UHD LED Android TV", "50PUT7406"),
    ],
)
def test_the_model_code_is_read_from_every_stores_title(title, code):
    assert profile_for("air-conditioners").model_code_from(title) == code


def test_one_code_written_two_ways_is_one_code():
    profile = profile_for("air-conditioners")

    assert profile.model_code_from("Gree AC Model GS-18FITH1") == profile.model_code_from(
        "Gree Inverter AC (GS18FITH1)"
    )


@pytest.mark.parametrize(
    "title",
    [
        # A measure, a resolution and a refrigerant are not codes.
        "Gree 1.5 Ton R410A 4K-UHD Inverter AC",
        "Haier 120Hz 4K Smart TV",
        "Kenwood Inverter AC T3",
    ],
)
def test_a_title_without_a_code_states_none(title):
    assert profile_for("air-conditioners").model_code_from(title) is None


def test_phones_and_laptops_are_not_matched_by_code():
    for slug in ("mobile-phones", "tablets", "smart-watches", "audio-and-earbuds", "laptops"):
        assert profile_for(slug).model_code_from("Samsung Galaxy A55 SM-A556E") is None


def test_a_title_in_capitals_becomes_a_name_in_words():
    assert appliance_name("HAIER 1.5 TON T3 INVERTER AC Model HSU-19HFAB W", "Haier") == (
        "Haier 1.5 Ton T3 Inverter AC Model HSU-19HFAB W"
    )
    # A title already written in words is kept as written.
    assert appliance_name("Gree Fairy Series Inverter AC (GS18FITH1W)", "Gree") == (
        "Gree Fairy Series Inverter AC (GS18FITH1W)"
    )
    assert appliance_name("Inverter AC KES-1866S", "Kenwood") == "Kenwood Inverter AC KES-1866S"


# --------------------------------------------------------------------------
# Matching
# --------------------------------------------------------------------------


# Samsung is a seeded brand: a brand a test creates would outlive it.
def ac(**overrides):
    payload = {
        "platform_code": "friendshome",
        "brand": "Samsung",
        "category_slug": "air-conditioners",
        "exact_model_title": True,
    }
    payload.update(overrides)
    return payload


def test_two_stores_writing_one_code_differently_share_one_product(
    client: TestClient,
    database_session: Session,
    discovered_products: list[int],  # noqa: F811
) -> None:
    token = uuid4().hex[:5].upper()
    first = discover(
        client,
        discovered_products,
        external_id=f"FH-{token}",
        title=f"SAMSUNG 1.5 TON T3 INVERTER AC Model AR-{token}9HF",
        **ac(),
    )
    second = discover(
        client,
        discovered_products,
        external_id=f"PO-{token}",
        title=f"Samsung 1.5 Ton Triple Inverter Split AC (AR{token}9HF)",
        **ac(platform_code="priceoye"),
    )

    assert first["product_created"] is True
    assert second["matched"] is True
    assert second["product_created"] is False
    assert second["canonical_product_id"] == first["canonical_product_id"]

    product = database_session.get(CanonicalProduct, int(first["canonical_product_id"]))
    assert product.model == f"AR{token}9HF"
    assert product.name.startswith("Samsung 1.5 Ton T3 Inverter AC")


def test_names_alike_but_codes_apart_are_two_products(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    token = uuid4().hex[:5].upper()
    twelve = discover(
        client,
        discovered_products,
        external_id=f"FH-{token}-12",
        title=f"SAMSUNG 1 TON INVERTER AC Model AR-12{token}",
        **ac(),
    )
    eighteen = discover(
        client,
        discovered_products,
        external_id=f"FH-{token}-18",
        title=f"SAMSUNG 1 TON INVERTER AC Model AR-18{token}",
        **ac(),
    )

    assert twelve["canonical_product_id"] != eighteen["canonical_product_id"]


def test_a_match_only_store_joins_a_catalogued_code_and_never_adds_one(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    token = uuid4().hex[:5].upper()
    catalogued = discover(
        client,
        discovered_products,
        external_id=f"FH-{token}",
        title=f"SAMSUNG 1.5 TON INVERTER AC Model AR-{token}7W",
        **ac(),
    )

    joined = resolve(
        client,
        external_id=f"DZ-{token}",
        title=f"Samsung 1.5 ton inverter ac AR{token}7W best price",
        **ac(platform_code="daraz", allow_new_product=False, exact_model_title=False),
    )
    unknown = resolve(
        client,
        external_id=f"DZ-{token}-X",
        title=f"Samsung 1.5 ton inverter ac AR{token}8W",
        **ac(platform_code="daraz", allow_new_product=False, exact_model_title=False),
    )

    assert joined["matched"] is True
    assert joined["canonical_product_id"] == catalogued["canonical_product_id"]
    assert unknown["matched"] is False
    assert unknown.get("canonical_product_id") is None


def test_a_listing_stating_no_code_is_left_alone(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    result = discover(
        client,
        discovered_products,
        external_id=f"FH-{uuid4().hex[:6]}",
        title="Samsung Inverter AC 1.5 Ton",
        **ac(),
    )

    assert result["matched"] is False
    assert result["product_created"] is False
    assert "model code" in result["reason"]
