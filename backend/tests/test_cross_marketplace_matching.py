from app.services.cross_marketplace_matching import (
    clean_product_display_name,
    cross_marketplace_product_key,
    normalized_product_identity,
)


def test_clean_product_display_name_removes_marketplace_features() -> None:
    assert clean_product_display_name(
        '(Official PTA Approve) Vivo Y85a - 6.26" Full HD Display '
        '- Dual Sim - 4GB RAM - 64GB ROM'
    ) == "Vivo Y85a"
    assert clean_product_display_name(
        "Samsung Galaxy A56 5G || 8GB RAM + 256GB ROM"
    ) == "Samsung Galaxy A56 5G"
    assert clean_product_display_name(
        "Infinix Note 60 Pro (8GB-256GB)"
    ) == "Infinix Note 60 Pro"


def test_clean_product_display_name_preserves_model_year() -> None:
    assert clean_product_display_name("Nokia 130 (2023)") == "Nokia 130 (2023)"
    assert clean_product_display_name(
        "Google Pixel 9 | 12GB RAM | 128GB storage"
    ) == "Google Pixel 9"


def test_normalized_product_identity_removes_offer_details() -> None:
    assert normalized_product_identity(
        "Samsung Galaxy A56 5G || 8GB RAM + 256GB ROM || 5000mAh Battery"
    ) == "samsung galaxy a56"
    assert normalized_product_identity(
        "Samsung Galaxy A56 12/256GB - PTA APPROVED"
    ) == "samsung galaxy a56"
    assert normalized_product_identity(
        "Realme Note 60x Up to 3GB+5GB Dynamic RAM + 64GB ROM"
    ) == "realme note 60x"


def test_normalized_product_identity_keeps_model_identity() -> None:
    assert normalized_product_identity(
        "Samsung Galaxy A37 5G"
    ) != normalized_product_identity(
        "Samsung Galaxy A36 5G"
    )
    assert normalized_product_identity(
        "Apple iPhone 17 Pro Max"
    ) != normalized_product_identity(
        "Apple iPhone 15"
    )


def test_cross_marketplace_key_ignores_optional_brand_prefixes() -> None:
    assert cross_marketplace_product_key(
        "Apple iPhone 15 Pro 256GB PTA Approved",
        "Apple",
    ) == cross_marketplace_product_key(
        "iPhone 15 Pro (256GB)",
        "Apple",
    )
    assert cross_marketplace_product_key(
        "Redmi Note 14 Pro 8GB + 256GB",
        "Xiaomi",
    ) == cross_marketplace_product_key(
        "Xiaomi Redmi Note 14 Pro",
        "Xiaomi",
    )
    assert cross_marketplace_product_key(
        "Samsung A57 8GB/256GB",
        "Samsung",
    ) == cross_marketplace_product_key(
        "Samsung Galaxy A57 5G",
        "Samsung",
    )


def test_cross_marketplace_key_keeps_decisive_model_words() -> None:
    assert cross_marketplace_product_key(
        "iPhone 15 Pro",
        "Apple",
    ) != cross_marketplace_product_key(
        "Apple iPhone 15 Pro Max",
        "Apple",
    )
    assert cross_marketplace_product_key(
        "Samsung Galaxy A56",
        "Samsung",
    ) != cross_marketplace_product_key(
        "Samsung Galaxy A55",
        "Samsung",
    )
