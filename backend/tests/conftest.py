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