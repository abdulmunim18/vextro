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
        # A letter inside, as in every real code: a dash and digits closing a
        # title read as a Daraz stock code.
        title=f"SAMSUNG 1 TON INVERTER AC Model AR-12X{token}",
        **ac(),
    )
    eighteen = discover(
        client,
        discovered_products,
        external_id=f"FH-{token}-18",
        title=f"SAMSUNG 1 TON INVERTER AC Model AR-18X{token}",
        **ac(),
    )

    assert twelve["product_created"] and eighteen["product_created"]
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


# --------------------------------------------------------------------------
# Televisions
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "series", "screen"),
    [
        # The size is written into each maker's code; the series is the rest.
        ("TCL 55 INCH SMART & 4K QD MINILED TV Model 55C6K", "C6K", 55),
        ("TCL LED 75P6L 4K SMART LED TV", "P6L", 75),
        ("HAIER LED 43\" H43S80EUX 4K SMART QLED GOOGLE TV", "S80EUX", 43),
        ("ECOSTAR 40 INCH SMART QLED TV Model CX-40Q874", "Q874", 40),
        ("DAWLANCE LED 65\" PRISMAX-65 4K UHD QLED GOOGLE TV", "PRISMAX", 65),
        # Samsung's market and trailing letters are not part of the model.
        ("SAMSUNG LED 55\" UA55U8000FUSMM 4K UHD SMART TV C/O", "U8000F", 55),
        ("SAMSUNG LED 55\" QA55Q7FAAUSMM QLED 4K UHD SMART TV", "Q7F", 55),
        ("SAMSUNG 55 INCH SMART & 4K QLED TV Model 55Q7F", "Q7F", 55),
        # A store naming the series alone states the size apart.
        ("Samsung 43\" Crystal UHD U8000F 4K Smart TV (2025)", "U8000F", 43),
        ("TCL S59K QLED Google TV With Official Warranty 32 Inch", "S59K", 32),
        # A number in the series is not a size: Samsung's Neo QLED QN70F.
        ("Samsung Neo QLED QN70F 4K Vision AI Smart TV 65Inches", "QN70F", 65),
        ("Samsung 65\" Neo QLED QA65QN70FAUXZN", "QN70F", 65),
        # A number closing the series without a hyphen is the series's own.
        ("LG 55 inch QNED AI QNED86 4K Smart TV 2025 55QNED86AS", "QNED86", 55),
        # A TV named in words.
        ("Dawlance Kore 40\" 2K FHD Smart LED Google TV", "KORE", 40),
    ],
)
def test_a_tv_keys_on_its_series_and_varies_by_screen(title, series, screen):
    profile = profile_for("televisions")

    assert profile.model_key_from(title) == series
    assert profile.identity_from(title=title) == {"screen_in": screen}


def test_a_tv_is_named_by_its_series_not_one_sized_code():
    profile = profile_for("televisions")

    assert appliance_name(
        profile.product_title("TCL 55 INCH SMART & 4K QD MINILED TV Model 55C6K"), "TCL"
    ) == "TCL Smart 4K QD MiniLED TV Model C6K"


def test_each_size_of_a_tv_series_is_a_variant_of_one_product(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    # Digits, as a Samsung series is: a model number and a year letter.
    token = str(uuid4().int)[:4]

    def tv(external_id, title, **overrides):
        payload = {
            "platform_code": "friendshome",
            "brand": "Samsung",
            "category_slug": "televisions",
            "exact_model_title": True,
        }
        payload.update(overrides)
        return discover(client, discovered_products, external_id=external_id, title=title, **payload)

    fifty_five = tv(f"FH-{token}-55", f"SAMSUNG 55 INCH SMART & 4K QLED TV Model 55Q{token}F")
    sixty_five = tv(f"FH-{token}-65", f"SAMSUNG 65 INCH SMART & 4K QLED TV Model 65Q{token}F")
    jalal = tv(
        f"JL-{token}-55",
        f"SAMSUNG LED 55\" QA55Q{token}FAAUSMM QLED 4K UHD SMART TV",
        platform_code="jalal",
        brand=None,
    )

    assert sixty_five["canonical_product_id"] == fifty_five["canonical_product_id"]
    assert sixty_five["product_variant_id"] != fifty_five["product_variant_id"]
    assert jalal["product_variant_id"] == fifty_five["product_variant_id"]


# --------------------------------------------------------------------------
# Refrigerators and freezers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "code"),
    [
        ("HAIER TWIN INVERTER + REFRIGERATOR Model HRF-538TIFRA", "HRF538TIFRA"),
        ("LG REFRIGERATORGR GN-B472PQMB", "GNB472PQMB"),
        # A model named by its number, with or without its series letters.
        ("Dawlance 9173 WB Avante GD Refrigerator 12 CFT With Official Warranty", "9173WB"),
        ("DAWLANCE REFRIGERATOR 9101 SD BLACK & SILVER", "9101SD"),
        ("PEL DIGITRON ULTRA INVERTER REFRIGERATOR Model 6370 SILVER STR", "6370"),
        # Friends Home's "REF-" is the store's, not Dawlance's.
        ("DAWLANCE SINGLE DOOR REFRIGERATOR Model REF-9101SD METALLIC GREY", "9101SD"),
        # Letters and number written apart.
        ("HAIER DEEP FREEZER HDF 405 SD", "HDF405SD"),
        ("Dawlance DFD 900 Glass Door Inverter Multi Door Refrigerator", "DFD900"),
    ],
)
def test_a_fridge_is_read_by_its_code_or_its_number(title, code):
    assert profile_for("refrigerators").model_key_from(title) == code


@pytest.mark.parametrize(
    "title",
    [
        # A capacity and a year are not a model number.
        "Haier Inverter Refrigerator 2025 Model 345 LTR",
        "Kenwood Smart Inverter Refrigerator 16 Cubic feet",
    ],
)
def test_a_fridge_title_naming_no_model_has_no_key(title):
    assert profile_for("refrigerators").model_key_from(title) is None


def test_a_fridge_title_states_its_capacity_and_compressor():
    from app.services.category_profiles import fridge_specifications

    assert fridge_specifications("Dawlance 9173 WB Avante Inverter Refrigerator 12 CFT") == {
        "capacity": "12 cu ft",
        "compressor": "Inverter",
    }
    assert fridge_specifications("SAMSUNG REFRIGERATOR RT35CG5404S9AE NON INVERTER 345 LTR") == {
        "capacity": "345 litres",
        "compressor": "Non-inverter",
    }


def fridge(**overrides):
    payload = {
        "platform_code": "friendshome",
        "brand": "Samsung",
        "category_slug": "refrigerators",
        "exact_model_title": True,
    }
    payload.update(overrides)
    return payload


def test_a_code_left_short_joins_the_one_fridge_it_begins(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    number = str(uuid4().int)[:4]
    catalogued = discover(
        client,
        discovered_products,
        external_id=f"FH-{number}",
        title=f"SAMSUNG REFRIGERATOR Model RT-{number}IDBA",
        **fridge(),
    )
    short = resolve(
        client,
        external_id=f"TM-{number}",
        title=f"Samsung RT-{number} Inverter Refrigerator",
        **fridge(platform_code="telemart", allow_new_product=False, exact_model_title=False),
    )

    assert short["matched"] is True
    assert short["canonical_product_id"] == catalogued["canonical_product_id"]


def test_a_code_left_short_joins_nothing_when_two_fridges_begin_so(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    number = str(uuid4().int)[:4]
    for finish in ("IFRA", "IFGA"):
        discover(
            client,
            discovered_products,
            external_id=f"FH-{number}-{finish}",
            title=f"SAMSUNG REFRIGERATOR Model RT-{number}{finish}",
            **fridge(),
        )
    short = resolve(
        client,
        external_id=f"TM-{number}",
        title=f"Samsung RT-{number} Inverter Refrigerator",
        **fridge(platform_code="telemart", allow_new_product=False, exact_model_title=False),
    )

    assert short["matched"] is False


def test_a_longer_code_from_a_store_that_catalogues_is_a_fridge_of_its_own(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    """One store's "RT-1234" first, then its "RT-1234TIF": two fridges."""

    number = str(uuid4().int)[:4]
    base = discover(
        client,
        discovered_products,
        external_id=f"FH-{number}",
        title=f"SAMSUNG REFRIGERATOR Model RT-{number}",
        **fridge(),
    )
    longer = discover(
        client,
        discovered_products,
        external_id=f"FH-{number}-TIF",
        title=f"SAMSUNG REFRIGERATOR Model RT-{number}TIF",
        **fridge(),
    )

    assert longer["product_created"] is True
    assert longer["canonical_product_id"] != base["canonical_product_id"]


# --------------------------------------------------------------------------
# Washing machines and dryers
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "code"),
    [
        ("HAIER 10KG TWIN TUB WASHING MACHINE Model HTW100-196G", "HTW100196G"),
        # Telemart writes the letters and the number apart.
        ("Haier HWM 150-1708 15Kg Top Load Fully Automatic Washing Machine", "HWM1501708"),
        ("Haier HTW 100-196 10Kg Top Load Twin Tub Semi Automatic Washing Machine", "HTW100196"),
        ("Dawlance DWT 14470 ES 14KG Fully Automatic Top Load Washing Machine", "DWT14470ES"),
        ("DAWLANCE WASHING MACHINE DWF95-1415 MG INVERTER F/L", "DWF951415"),
        # A word after a model number is not its series letters.
        ("MIDAS 4117 TOP LOAD WASHING MACHINE 17KG", "4117"),
    ],
)
def test_a_washer_is_read_by_its_code_however_it_is_spaced(title, code):
    assert profile_for("washing-machines").model_key_from(title) == code


def test_a_washer_title_states_its_load_type_and_motor():
    from app.services.category_profiles import washer_specifications

    assert washer_specifications("LG 20KG/12KG WASHER DRYER AUTOMATIC FRONT LOAD") == {
        "capacity": "20 kg wash / 12 kg dry",
        "type": "Front load",
    }
    assert washer_specifications("DAWLANCE WASHING MACHINE DWF95-1415 MG INVERTER F/L") == {
        "type": "Front load",
        "motor": "Inverter",
    }
    assert washer_specifications("HAIER 10KG TWIN TUB WASHING MACHINE") == {
        "capacity": "10 kg",
        "type": "Twin tub",
    }


def test_a_washer_written_apart_joins_the_one_catalogued_with_its_finish(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    number = str(uuid4().int)[:4]
    catalogued = discover(
        client,
        discovered_products,
        external_id=f"FH-{number}",
        title=f"SAMSUNG 10KG TWIN TUB WASHING MACHINE Model HTW100-{number}G",
        platform_code="friendshome",
        brand="Samsung",
        category_slug="washing-machines",
        exact_model_title=True,
    )
    telemart = resolve(
        client,
        external_id=f"TM-{number}",
        title=f"Samsung HTW 100-{number} 10Kg Twin Tub Washing Machine",
        platform_code="telemart",
        brand="Samsung",
        category_slug="washing-machines",
        allow_new_product=False,
    )

    assert telemart["matched"] is True
    assert telemart["canonical_product_id"] == catalogued["canonical_product_id"]


def test_a_store_naming_its_own_washer_keeps_the_number_ending_its_code(
    client: TestClient,
    discovered_products: list[int],  # noqa: F811
) -> None:
    """A Daraz stock code ends a title with a dash and digits; so does a model."""

    number = str(uuid4().int)[:4]
    result = discover(
        client,
        discovered_products,
        external_id=f"FH-{number}",
        title=f"SAMSUNG 22KG AUTOMATIC TOP LOAD WASHING MACHINE Model MI-WMTL-{number}",
        platform_code="friendshome",
        brand="Samsung",
        category_slug="washing-machines",
        exact_model_title=True,
    )

    assert result["product_created"] is True
    assert result["model"] == f"MIWMTL{number}"
