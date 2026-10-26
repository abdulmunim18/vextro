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


# --------------------------------------------------------------------------
# Air conditioners
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "code"),
    [
        # Jalal adds the climate rating to Gree's code.
        ("GREE SPLIT AC 1 TON GS-12ZITH1W-T3 ZENO SERIES", "GS12ZITH1W"),
        # A split AC's outdoor unit has a code of its own.
        ("HAIER SPLIT AC INVERTER 1.6 TON HSU-19HFCM/013USDC HEAT & COOL", "HSU19HFCM"),
        ("HAIER SPLIT AC INVERTER 1.5 TON HSU-19HFS/023WDC(W)-T3 Pro WHITE", "HSU19HFS"),
        # An indoor unit ending "I" pairs with an outdoor one ending "O".
        ("AERIS SPLIT AC INVERTER 1.0TON AEW12QC01HCI/AEW12QC01HCO T3", "AEW12QC01HC"),
        # A colour written after the code is not part of it.
        ("HAIER 1.5 TON T3 INVERTER AC Model HSU-19HFS-W", "HSU19HFS"),
        ("HAIER 1.5 TON T3 INVERTER AC Model HSU-20HFTEX-DG", "HSU20HFTEX"),
        # TCL's own code holds a T3 of its own.
        ("TCL FLOOR STANDING AC 4.0 TON TAC-48T3-FH", "TAC48T3FH"),
    ],
)
def test_an_ac_code_is_read_without_what_stores_add_to_it(title, code):
    assert profile_for("air-conditioners").model_key_from(title) == code


@pytest.mark.parametrize(
    ("title", "colour"),
    [
        ("HAIER 1.5 TON T3 INVERTER AC Model HSU-19HFS-W", "White"),
        ("HAIER 1.5 TON T3 INVERTER AC Model HSU-20HFTEX OW", "Off White"),
        # "G" is grey on one Haier and gold on another.
        ("HAIER 1.0 TON T3 INVERTER AC Model HSU-13HFAB G", None),
        ("HAIER SPLIT AC 1.1 TON INVERTER HSU-13HFS/013WDC(S)-T3 PRO SILVER", "Silver"),
        ("GREE 1.5 TON T3 INVERTER AC Model GS-18ZITH1W", None),
    ],
)
def test_the_colour_an_ac_code_names_is_read(title, colour):
    from app.services.category_profiles import ac_code_colour

    assert ac_code_colour(title) == colour


@pytest.mark.parametrize(
    ("title", "key"),
    [
        ("ORIENT 1.5 TON ULTRON DC INVERTER AC Model 18G LUNAR FLORAL BLACK", "1.5T 18G FLORAL LUNAR ULTRON"),
        ("PEL 1.0 TON SAVER T3 INVERTER AC Model 12K SAVER T3", "1T 12K SAVER"),
        ("DAWLANCE SPLIT AC INVERTER 1.5 TON EXCEL INVERTER 30 WHITE HEAT & COOL", "1.5T 30 EXCEL"),
        # One AC as another store writes it: the same key.
        ("Dawlance Excel 30 Heat & Cool Inverter Split Air Condition 1.5 Ton With Official Warranty", "1.5T 30 EXCEL"),
    ],
)
def test_an_ac_named_in_words_keys_on_its_name_and_tonnage(title, key):
    assert profile_for("air-conditioners").model_key_from(title) == key


@pytest.mark.parametrize(
    "title",
    [
        "Dawlance Magna Inverter Split AC 1.5 Ton With Official Warranty",
        "Haier Inverter AC 1.5 Ton",
    ],
)
def test_an_ac_title_naming_no_model_has_no_key(title):
    assert profile_for("air-conditioners").model_key_from(title) is None


def test_an_ac_title_states_its_tonnage_compressor_and_heating():
    from app.services.category_profiles import ac_specifications

    assert ac_specifications("HAIER SPLIT AC INVERTER 1.5 TON HSU-19HFS HEAT/COOL") == {
        "capacity": "1.5 Ton",
        "compressor": "Inverter",
        "heating": "Heat & Cool",
    }
    assert ac_specifications("Gree T-Fresh Cool Only Floor Standing 4 Ton") == {
        "capacity": "4 Ton",
        "heating": "Cool only",
    }


def test_one_ac_from_two_stores_lands_on_one_colour_variant(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    token = uuid4().hex[:4].upper()
    friends_home = discover(
        client,
        discovered_products,
        external_id=f"FH-{token}",
        title=f"SAMSUNG 1.5 TON T3 INVERTER AC Model AR-19{token}-W",
        **ac(),
    )
    jalal = discover(
        client,
        discovered_products,
        external_id=f"JL-{token}",
        title=f"SAMSUNG SPLIT AC INVERTER 1.5 TON AR-19{token}/013USDC(W)-T3 WHITE HEAT/COOL",
        **ac(platform_code="jalal", brand=None),
    )
    grey = discover(
        client,
        discovered_products,
        external_id=f"FH-{token}-G",
        title=f"SAMSUNG 1.5 TON T3 INVERTER AC Model AR-19{token} GREY",
        **ac(),
    )
    gray = discover(
        client,
        discovered_products,
        external_id=f"JL-{token}-G",
        title=f"SAMSUNG SPLIT AC INVERTER 1.5 TON AR-19{token}/013USDC GRAY T3",
        **ac(platform_code="jalal", brand=None),
    )

    assert jalal["canonical_product_id"] == friends_home["canonical_product_id"]
    assert jalal["product_variant_id"] == friends_home["product_variant_id"]
    assert friends_home["color"] == "White"
    assert gray["product_variant_id"] == grey["product_variant_id"]
    assert grey["product_variant_id"] != friends_home["product_variant_id"]
