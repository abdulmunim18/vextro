"""Category profiles: what tells two variants apart in each category."""

import pytest

from app.services.category_profiles import (
    PROFILES,
    UnknownCategoryError,
    configuration_key,
    profile_for,
)


def identity(slug, title, specifications=None):
    return profile_for(slug).identity_from(title=title, specifications=specifications)


# --------------------------------------------------------------------------
# Choosing a profile
# --------------------------------------------------------------------------


def test_a_listing_naming_no_category_is_a_smartphone():
    assert profile_for(None).slug == "mobile-phones"
    assert profile_for("").slug == "mobile-phones"


def test_the_old_smartphones_slug_is_the_same_category():
    assert profile_for("smartphones").slug == "mobile-phones"
    assert profile_for(" Tablets ").slug == "tablets"


def test_an_unknown_category_is_an_error_not_a_phone():
    with pytest.raises(UnknownCategoryError):
        profile_for("fashion")


def test_every_profile_names_a_seeded_category():
    seeded = {"mobile-phones", "laptops", "tablets", "smart-watches", "audio-and-earbuds", "power-banks", "mobile-accessories"}

    assert set(PROFILES) <= seeded


# --------------------------------------------------------------------------
# Smartphones: unchanged behaviour
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "specifications", "expected"),
    [
        ("Samsung Galaxy A17 6GB 128GB", None, {"ram_gb": 6, "storage_gb": 128}),
        ("Vivo Y05e 4GB +64GB", None, {"ram_gb": 4, "storage_gb": 64}),
        ("Oppo A6C", {"ram": "4GB", "storage_capacity": "128GB"}, {"ram_gb": 4, "storage_gb": 128}),
        ("Nokia 105 Power", None, {}),
    ],
)
def test_a_phone_is_identified_by_ram_and_storage(title, specifications, expected):
    assert identity("mobile-phones", title, specifications) == expected


# --------------------------------------------------------------------------
# Tablets
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Apple iPad Air 11 M3 128GB Wi-Fi", "wifi"),
        ("Apple iPad Pro 13 M5 256GB WiFi + Cellular", "cellular"),
        ("Samsung Galaxy Tab A9 Plus 8GB 128GB 5G", "cellular"),
        ("Samsung Galaxy Tab S10 FE 8GB 128GB LTE", "cellular"),
        ("Xiaomi Redmi Pad 2 8GB 256GB", None),
    ],
)
def test_a_tablet_states_whether_it_takes_a_sim(title, expected):
    assert identity("tablets", title).get("connectivity") == expected


def test_a_tablet_keeps_its_memory_too():
    assert identity("tablets", "Samsung Galaxy Tab A9 Plus 8GB 128GB WiFi") == {
        "ram_gb": 8,
        "storage_gb": 128,
        "connectivity": "wifi",
    }


# --------------------------------------------------------------------------
# Smart watches and earbuds
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Apple Watch Series 11 46mm GPS", {"case_size_mm": 46}),
        ("Apple Watch Ultra 3 49 mm GPS + Cellular", {"case_size_mm": 49, "connectivity": "cellular"}),
        ("Samsung Galaxy Watch 8 44MM", {"case_size_mm": 44}),
        ("Xiaomi Redmi Watch 5 Active", {}),
    ],
)
def test_a_watch_is_identified_by_case_size(title, expected):
    assert identity("smart-watches", title) == expected


def test_a_screen_measured_in_millimetres_elsewhere_is_not_a_case_size():
    assert identity("smart-watches", "Amazfit Bip 6 1.97 inch 100mm strap") == {}


def test_earbuds_have_no_identity_beyond_the_model_and_colour():
    assert identity("audio-and-earbuds", "Apple AirPods Pro 3 with USB-C") == {}


# --------------------------------------------------------------------------
# Configuration key
# --------------------------------------------------------------------------


def test_the_key_does_not_depend_on_the_order_attributes_were_stated():
    assert configuration_key({"storage_gb": 256, "ram_gb": 8}) == configuration_key(
        {"ram_gb": 8, "storage_gb": 256}
    ) == "ram_gb=8|storage_gb=256"


def test_unstated_attributes_leave_no_trace_in_the_key():
    assert configuration_key({"ram_gb": None, "storage_gb": 128, "connectivity": ""}) == "storage_gb=128"
    assert configuration_key({}) == ""


def test_text_values_are_compared_without_case():
    assert configuration_key({"connectivity": "WiFi"}) == configuration_key({"connectivity": "wifi"})


def test_values_the_source_sent_as_fields_outrank_the_title():
    """The crawler's own RAM and storage win, as they do in the matcher."""

    profile = profile_for("mobile-phones")

    assert profile.identity_from(
        title="REALME NOTE 60X = 4GB RAM = 64GB ROM",
        specifications={"storage_capacity": "128GB"},
        stated={"ram_gb": 4, "storage_gb": 64},
    ) == {"ram_gb": 4, "storage_gb": 64}

