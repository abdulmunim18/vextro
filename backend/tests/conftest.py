from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import Session, sessionmaker

import app.models  # noqa: F401
from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.brand import Brand
from app.models.category import Category
from app.models.platform import Platform
from app.models.role import Role


TEST_DATABASE_NAME = settings.test_db_name

TEST_DATABASE_URL = URL.create(
    drivername="postgresql+psycopg",
    username=settings.db_user,
    password=settings.db_password,
    host=settings.db_host,
    port=settings.db_port,
    database=TEST_DATABASE_NAME,
)


test_engine = create_engine(
    TEST_DATABASE_URL,
    pool_pre_ping=True,
)


TestingSessionLocal = sessionmaker(
    bind=test_engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def override_get_db() -> Generator[Session, None, None]:
    """Provide a dedicated test database session."""

    database_session = TestingSessionLocal()

    try:
        yield database_session
    finally:
        database_session.close()


app.dependency_overrides[get_db] = override_get_db

# A developer's .env may start the crawl scheduler with the API. Tests start
# the API many times and must never launch a real crawl of the marketplaces.
settings.scraper_autostart_with_api = False


@pytest.fixture(autouse=True)
def stub_auth_email_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests deterministic without contacting external services."""

    monkeypatch.setattr(settings, "assistant_ai_enabled", False)

    monkeypatch.setattr(
        "app.services.auth_service.generate_email_otp",
        lambda: "123456",
    )
    monkeypatch.setattr(
        "app.services.auth_service.send_verification_otp_email",
        lambda **_kwargs: None,
    )
    monkeypatch.setattr(
        "app.services.auth_service.send_password_reset_email",
        lambda **_kwargs: None,
    )


@pytest.fixture(scope="session", autouse=True)
def prepare_test_database() -> Generator[None, None, None]:
    """Create, seed, and later remove the test database schema."""

    if TEST_DATABASE_NAME != "vextro_test_db":
        raise RuntimeError(
            "Tests must run only against vextro_test_db."
        )

    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)

    with TestingSessionLocal() as database_session:
        # Default application roles
        roles = [
            Role(
                name="consumer",
                description="Consumer test role.",
            ),
            Role(
                name="sme",
                description="SME test role.",
            ),
            Role(
                name="admin",
                description="Administrator test role.",
            ),
        ]

        # Parent category
        electronics = Category(
            name="Electronics",
            slug="electronics",
            is_active=True,
        )

        database_session.add_all(
            [
                *roles,
                electronics,
            ]
        )

        # Generate electronics.id before creating child categories
        database_session.flush()

        child_categories = [
            Category(
                parent_id=electronics.id,
                name="Mobile Phones",
                slug="mobile-phones",
                is_active=True,
            ),
            Category(
                parent_id=electronics.id,
                name="Laptops",
                slug="laptops",
                is_active=True,
            ),
            Category(
                parent_id=electronics.id,
                name="Tablets",
                slug="tablets",
                is_active=True,
            ),
            Category(
                parent_id=electronics.id,
                name="Smart Watches",
                slug="smart-watches",
                is_active=True,
            ),
            Category(
                parent_id=electronics.id,
                name="Audio and Earbuds",
                slug="audio-and-earbuds",
                is_active=True,
            ),
            Category(
                parent_id=electronics.id,
                name="Power Banks",
                slug="power-banks",
                is_active=True,
            ),
            Category(
                parent_id=electronics.id,
                name="Mobile Accessories",
                slug="mobile-accessories",
                is_active=True,
            ),
        ]

        # As migration a4e8b1c3d927 seeds them.
        home_appliances = Category(
            name="Home Appliances",
            slug="home-appliances",
            is_active=True,
        )
        database_session.add(home_appliances)
        database_session.flush()
        child_categories += [
            Category(
                parent_id=home_appliances.id,
                name="Air Conditioners",
                slug="air-conditioners",
                is_active=True,
            ),
            Category(
                parent_id=home_appliances.id,
                name="Televisions",
                slug="televisions",
                is_active=True,
            ),
            # As migration c6f2d8a41b93 seeds it.
            Category(
                parent_id=home_appliances.id,
                name="Refrigerators & Freezers",
                slug="refrigerators",
                is_active=True,
            ),
            # As migration d1a7e3f5c284 seeds it.
            Category(
                parent_id=home_appliances.id,
                name="Washing Machines & Dryers",
                slug="washing-machines",
                is_active=True,
            ),
            # As migration e8b4c2a6d913 seeds it.
            Category(
                parent_id=home_appliances.id,
                name="Microwave Ovens",
                slug="microwave-ovens",
                is_active=True,
            ),
        ]

        brand_names = [
            "Apple",
            "Samsung",
            "Xiaomi",
            "Oppo",
            "Vivo",
            "Infinix",
            "Tecno",
            "Realme",
            "OnePlus",
            "Huawei",
            "Honor",
            "Nokia",
            "Dell",
            "HP",
            "Lenovo",
            "Asus",
            "Acer",
        ]

        brands = [
            Brand(
                name=brand_name,
                slug=brand_name.lower().replace(" ", "-"),
                is_active=True,
            )
            for brand_name in brand_names
        ]

        platforms = [
            Platform(
                name="Daraz",
                code="daraz",
                base_url="https://www.daraz.pk",
                is_active=True,
            ),
            Platform(
                name="PriceOye",
                code="priceoye",
                base_url="https://priceoye.pk",
                is_active=True,
            ),
            Platform(
                name="Shophive",
                code="shophive",
                base_url="https://www.shophive.com",
                is_active=True,
            ),
            *(
                Platform(name=name, code=code, base_url=base_url, is_active=True)
                for name, code, base_url in (
                    ("Friends Home", "friendshome", "https://friendshome.pk"),
                    ("Jalal Electronics", "jalal", "https://jalalelectronics.com"),
                    ("Telemart", "telemart", "https://telemart.pk"),
                )
            ),
        ]

        database_session.add_all(
            [
                *child_categories,
                *brands,
                *platforms,
            ]
        )

        database_session.commit()

    yield

    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="session")
def client(
    prepare_test_database: None,
) -> Generator[TestClient, None, None]:
    """Provide the FastAPI test client."""

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()


@pytest.fixture
def database_session(
    prepare_test_database: None,
) -> Generator[Session, None, None]:
    """Provide a session for database assertions."""

    with TestingSessionLocal() as session:
        yield session
