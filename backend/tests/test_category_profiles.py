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


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ('Apple IPad Pro M5 Chip 13" 256GB Wifi', 13),
        ("Apple iPad Air 11inch 2026 8th Generation M4 Chip Wifi", 11),
        ("Samsung Galaxy Tab S11 Ultra 14.6″ 512GB Wifi", 14.6),
        ("Apple iPad Mini 7 8.3'' 128GB Wifi (2024)", 8.3),
        ("Apple iPad Pro M5 Chip 13 Inches WiFi 2025 256GB", 13),
        # "11" here is the generation, not a size.
        ("Apple iPad 11 (A16)", None),
        # A desktop monitor's size is not a tablet's.
        ('Samsung 27" Monitor Tab', None),
    ],
)
def test_a_tablet_states_its_screen_size(title, expected):
    assert identity("tablets", title).get("screen_in") == expected


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Apple iPad Air 11inch 2026 8th Generation M4 Chip Wifi", "Apple iPad Air 8th Gen M4"),
        ("Xiaomi Redmi Pad 2 Wifi 1 Year Warranty", "Xiaomi Redmi Pad 2"),
        ("Xiaomi Pad 7 (1 Year Brand Warranty)", "Xiaomi Pad 7"),
        ("E18 D08 8 Inches Tab Wifi Only", "E18 D08 Tab"),
        ('Apple iPad Pro 12.9" M2 Wi-Fi + Cellular', "Apple iPad Pro M2"),
        # The year goes too; a bracket before the chip once cut the name
        # down to "Apple iPad Pro".
        ("Apple iPad Pro 11inch (2025) M5 Chip WiFi", "Apple iPad Pro M5"),
        ("Apple iPad Pro M5 Chip 13 inches WiFi 2025 256GB", "Apple iPad Pro M5 256GB"),
        # One model as two stores spell it.
        ("Apple iPad Air 8th Generation M4 Chip", "Apple iPad Air 8th Gen M4"),
        ("Samsung Galaxy Tab S10 Lite WiFi SM-x400", "Samsung Galaxy Tab S10 Lite x400"),
        ("Xiaomi Redmi Pad 2 SSD - Wifi", "Xiaomi Redmi Pad 2"),
    ],
)
def test_a_tablets_name_leaves_out_its_variant_and_warranty(title, expected):
    assert profile_for("tablets").product_title(title) == expected


@pytest.mark.parametrize(
    ("first", "second"),
    [
        # PriceOye drops "Galaxy Tab"; Shophive writes it.
        ("Samsung S11 Ultra Wifi", 'Samsung Galaxy Tab S11 Ultra 14.6" Wifi'),
        ("Samsung Galaxy A11 Wifi Tab", 'Samsung Galaxy Tab A11 8.7" WiFi'),
        # Shophive writes one iPad Air both ways.
        ('Apple iPad Air 7 11" M3 Wi-Fi', 'Apple iPad Air M3 7th Gen 13" Wi-Fi'),
        ("Apple iPad 11 (A16)", 'Apple iPad 11 A16 11" Wifi (2025)'),
        # A brand written in two words.
        ("VGO TEL V Tab 2", "Vgotel V Tab 2 3G"),
    ],
)
def test_two_stores_spellings_of_one_tablet_read_the_same(first, second):
    def words(title):
        return sorted(profile_for("tablets").product_title(title).lower().split())

    assert words(first) == words(second)


def test_a_tablets_name_keeps_its_generation_and_drops_the_category_noun():
    profile = profile_for("tablets")

    assert profile.product_title("Lenovo Tab M10 HD (2nd Gen)") == "Lenovo Tab M10 HD 2nd Gen"
    assert profile.product_title("Amazon Fire HD 8 12Th Gen Tablet") == "Amazon Fire HD 8 12th Gen"
    # A figure with a unit is a screen size, not a generation.
    assert profile.product_title('Apple iPad Mini 6 8.3" WIFI') == "Apple iPad Mini 6th Gen"
    assert profile.product_title("Apple iPad 10.2 2021") == "Apple iPad 10.2"


def test_unit_less_memory_is_not_read_as_a_model_number():
    """ "Redmi Pad 2 8/256" once matched the "Pad 8" on its "8"."""

    profile = profile_for("tablets")

    assert profile.product_title("Xiaomi Redmi Pad 2 8/256 4G") == "Xiaomi Redmi Pad 2"
    assert profile.product_title("Xiaomi Pad 7 8GB + 256GB") == "Xiaomi Pad 7"
    # Not memory: the second figure is no storage size.
    assert profile.product_title("Lenovo Tab 6 4/46") == "Lenovo Tab 6 4/46"


def test_phone_titles_are_not_rewritten():
    assert profile_for("mobile-phones").product_title("Samsung Galaxy A17 (2025) 5G") == (
        "Samsung Galaxy A17 (2025) 5G"
    )


# --------------------------------------------------------------------------
# Smart watches and earbuds
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        # GPS and GPS + Cellular are two models at two prices.
        ("Apple Watch Series 11 46mm GPS", {"case_size_mm": 46, "connectivity": "gps"}),
        ("Apple Watch Ultra 3 49 mm GPS + Cellular", {"case_size_mm": 49, "connectivity": "cellular"}),
        ("Samsung Galaxy Watch 8 44MM", {"case_size_mm": 44}),
        ("Samsung Galaxy Watch 8 Classic 46mm Bluetooth", {"case_size_mm": 46, "connectivity": "gps"}),
        ("Xiaomi Redmi Watch 5 Active", {}),
        # The case's material, not the band's.
        (
            "Apple Watch Series 12 GPS + Cellular 46mm Natural Titanium Case with Natural Milanese Loop",
            {"case_size_mm": 46, "connectivity": "cellular", "case_material": "titanium"},
        ),
        (
            "Apple Watch Series 11 42mm Space Gray Aluminium Case With Black Sports Band",
            {"case_size_mm": 42, "case_material": "aluminium"},
        ),
    ],
)
def test_a_watch_is_identified_by_case_size(title, expected):
    assert identity("smart-watches", title) == expected


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Apple Watch SE 3 40mm GPS (2025)", "Apple Watch SE Gen 3 40mm Midnight Case With Midnight Sports Band"),
        (
            "Apple Watch Ultra 3 49mm (2025)",
            "Apple Watch Ultra 3 GPS + Cellular 49mm Black Titanium Case with Black Ocean Band (MF254)",
        ),
        ("Samsung Watch 8 Classic 46mm", "Samsung Galaxy Watch 8 Classic 46mm Bluetooth"),
        ("Huawei GT7 Pro Smart Watch 46mm", "Huawei Watch GT7 Pro 46mm"),
        ("Xiaomi Mi Band 10", "Xiaomi Smart Band 10"),
        ("Faster Nerv Smart Watch 2", "Faster Nerv Watch 2"),
    ],
)
def test_two_stores_spellings_of_one_watch_read_the_same(first, second):
    profile = profile_for("smart-watches")

    assert profile.product_title(first).lower() == profile.product_title(second).lower()


@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("Amazfit Pop 3S Smart Watch With 1.96″ Amoled", "Amazfit Pop 3S Watch"),
        ("Xinji N3 Smart Watch Ultra-Thin 1.43&#039;&#039; Amoled", "Xinji N3 Watch Ultra-Thin"),
        ("Samsung Galaxy Watch 9 WiFi With Sports Band 44mm", "Samsung Galaxy Watch 9"),
        ("Huawei Band 11 Pro Premium Fitness Tracker", "Huawei Band 11 Pro"),
        ("Xiaomi Smart Band 9 Active Smart Watch (Global)", "Xiaomi Smart Band 9 Active"),
        ("Haylou RS4 Max Calling Watch", "Haylou RS4 Max Watch"),
        ("Nothing CMF Watch 3 Pro With One Year Brand", "Nothing CMF Watch 3 Pro"),
        # "Inch" after the quote once survived, and its "2" was read away.
        ('CMF Nothing Watch Pro 2 With 1.32" Inch Amoled Display', "CMF Nothing Watch Pro 2"),
        ('Kospet Tank S2 1.32" Inch Amoled', "Kospet Tank S2"),
    ],
)
def test_a_watchs_name_leaves_out_its_screen_band_and_selling_points(title, expected):
    assert profile_for("smart-watches").product_title(title) == expected


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("Apple AirPods 4 Active Noise Cancellation", "Apple AirPods 4 ANC"),
        ("Samsung Buds 3 Pro Wireless Earbuds", "Samsung Galaxy Buds 3 Pro"),
        ("QCY T13 ANC 2 TWS Bluetooth 5.3 Earbuds 30H Playtime", "QCY T13 ANC 2"),
        ("Apple AirPods Pro 3 with MagSafe Charging Case (USB-C)", "Apple AirPods Pro 3"),
        ("Sony WH-1000XM5 Wireless Noise Cancelling Headphones", "Sony WH-1000XM5"),
        # One store writes Anker's SKU, Apple's part number or the fit.
        ("Anker Soundcore D1200H11 Liberty Buds", "Anker Soundcore Liberty Buds"),
        ("Anker A3959H11 Soundcore R50i NC", "Anker Soundcore R50i NC"),
        ("Apple AirPods 5 MKFW4LL/A", "Apple AirPods 5"),
        ("Anker Soundcore AeroClip Open-Ear Clip-On", "Anker Soundcore AeroClip Open Ear"),
        ("Audionic Hammer 110 Ultra On-Ear Headphone", "Audionic Hammer 110 Ultra"),
        ("Sony WF-C510 Truly Wireless", "Sony WF-C510"),
    ],
)
def test_two_stores_spellings_of_one_earbud_read_the_same(first, second):
    profile = profile_for("audio-and-earbuds")

    assert profile.product_title(first).lower() == profile.product_title(second).lower()


def test_earbuds_are_told_apart_by_colour_alone():
    profile = profile_for("audio-and-earbuds")

    assert profile.keys == ()
    assert not profile.uses_memory


def test_memory_does_not_tell_watches_apart():
    assert profile_for("mobile-phones").uses_memory
    assert profile_for("tablets").uses_memory
    assert not profile_for("smart-watches").uses_memory


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

