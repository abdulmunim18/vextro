"""Integration tests for SME sales CSV import APIs."""

from collections.abc import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.sales_import import SalesImport
from app.models.sales_record import SalesRecord


TEST_PASSWORD = "StrongPassword123!"

ORGANIZATIONS_ENDPOINT = (
    "/api/v1/sme/organizations"
)


def unique_email(
    prefix: str,
) -> str:
    """Generate a unique test email address."""

    return (
        f"{prefix}-{uuid4().hex}@example.com"
    )


def register_and_login(
    client: TestClient,
    *,
    account_type: str,
    prefix: str,
) -> dict[str, str]:
    """Register one user and return authorization headers."""

    email = unique_email(prefix)

    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": (
                f"{account_type.title()} Sales Test User"
            ),
            "email": email,
            "password": TEST_PASSWORD,
            "account_type": account_type,
        },
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()[
        "access_token"
    ]

    return {
        "Authorization": (
            f"Bearer {access_token}"
        ),
    }


@pytest.fixture
def sales_context(
    client: TestClient,
    database_session: Session,
) -> Generator[
    dict[str, object],
    None,
    None,
]:
    """Create an SME organization and business product."""

    token = uuid4().hex[:10]

    headers = register_and_login(
        client,
        account_type="sme",
        prefix=f"sales-sme-{token}",
    )

    organization_response = client.post(
        ORGANIZATIONS_ENDPOINT,
        headers=headers,
        json={
            "name": (
                f"Sales Test Organization {token}"
            ),
            "industry": "Mobile Retail",
        },
    )

    assert organization_response.status_code == 201

    organization = organization_response.json()

    organization_id = int(
        organization["id"],
    )

    sku = f"PHONE-{token}".upper()

    products_endpoint = (
        f"{ORGANIZATIONS_ENDPOINT}/"
        f"{organization_id}/products"
    )

    product_response = client.post(
        products_endpoint,
        headers=headers,
        json={
            "name": (
                f"Sales Test Phone {token}"
            ),
            "sku": sku,
            "cost_price": 100000,
            "selling_price": 125000,
            "currency": "PKR",
            "stock_level": 25,
            "reorder_level": 5,
        },
    )

    assert product_response.status_code == 201

    product = product_response.json()

    context = {
        "headers": headers,
        "organization_id": organization_id,
        "organization": organization,
        "business_product_id": int(
            product["id"],
        ),
        "sku": sku,
        "imports_endpoint": (
            f"{ORGANIZATIONS_ENDPOINT}/"
            f"{organization_id}/sales/imports"
        ),
    }

    yield context

    database_session.rollback()

    import_ids = select(
        SalesImport.id,
    ).where(
        SalesImport.organization_id
        == organization_id,
    )

    database_session.execute(
        delete(SalesRecord).where(
            SalesRecord.sales_import_id.in_(
                import_ids,
            ),
        ),
    )

    database_session.execute(
        delete(SalesImport).where(
            SalesImport.organization_id
            == organization_id,
        ),
    )

    database_session.execute(
        delete(Organization).where(
            Organization.id == organization_id,
        ),
    )

    database_session.commit()


def test_sales_import_routes_require_authentication_and_role(
    client: TestClient,
) -> None:
    """Block unauthenticated and Consumer import requests."""

    endpoint = (
        f"{ORGANIZATIONS_ENDPOINT}/"
        "1/sales/imports"
    )

    csv_content = (
        "sku,sale_date,quantity,unit_price,currency\n"
        "PHONE-001,2026-08-01,1,1000,PKR\n"
    )

    no_token_response = client.post(
        endpoint,
        files={
            "file": (
                "sales.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            ),
        },
    )

    assert no_token_response.status_code == 401

    consumer_headers = register_and_login(
        client,
        account_type="consumer",
        prefix="sales-consumer-block",
    )

    consumer_response = client.post(
        endpoint,
        headers=consumer_headers,
        files={
            "file": (
                "sales.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            ),
        },
    )

    assert consumer_response.status_code == 403

    assert (
        consumer_response.json()["detail"]["code"]
        == "ROLE_NOT_ALLOWED"
    )


def test_sme_can_import_and_read_valid_sales_csv(
    client: TestClient,
    database_session: Session,
    sales_context: dict[str, object],
) -> None:
    """Import valid rows and retrieve persisted records."""

    headers = sales_context["headers"]
    imports_endpoint = sales_context[
        "imports_endpoint"
    ]
    sku = str(
        sales_context["sku"],
    )

    assert isinstance(headers, dict)
    assert isinstance(imports_endpoint, str)

    csv_content = "\n".join(
        [
            (
                "sku,sale_date,quantity,"
                "unit_price,currency"
            ),
            (
                f"{sku},2026-08-01,"
                "2,125000,PKR"
            ),
            (
                f"{sku},2026-08-02,"
                "1,125000.00,PKR"
            ),
        ],
    )

    import_response = client.post(
        imports_endpoint,
        headers=headers,
        files={
            "file": (
                "valid-sales.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            ),
        },
    )

    assert import_response.status_code == 201

    import_result = import_response.json()

    assert import_result["row_errors"] == []

    sales_import = import_result[
        "sales_import"
    ]

    assert sales_import["status"] == "completed"
    assert sales_import["total_rows"] == 2
    assert sales_import["accepted_rows"] == 2
    assert sales_import["rejected_rows"] == 0
    assert sales_import["error_message"] is None
    assert sales_import["completed_at"] is not None

    sales_import_id = int(
        sales_import["id"],
    )

    list_response = client.get(
        imports_endpoint,
        headers=headers,
        params={
            "page": 1,
            "page_size": 10,
        },
    )

    assert list_response.status_code == 200

    list_data = list_response.json()

    assert list_data["total"] == 1
    assert list_data["total_pages"] == 1

    assert list_data["items"][0]["id"] == (
        sales_import_id
    )

    detail_response = client.get(
        f"{imports_endpoint}/{sales_import_id}",
        headers=headers,
    )

    assert detail_response.status_code == 200

    assert detail_response.json()["status"] == (
        "completed"
    )

    records_response = client.get(
        (
            f"{imports_endpoint}/"
            f"{sales_import_id}/records"
        ),
        headers=headers,
        params={
            "page": 1,
            "page_size": 20,
        },
    )

    assert records_response.status_code == 200

    records_data = records_response.json()

    assert records_data["total"] == 2
    assert records_data["total_pages"] == 1
    assert len(records_data["items"]) == 2

    records_by_row = {
        item["source_row_number"]: item
        for item in records_data["items"]
    }

    assert set(records_by_row) == {
        2,
        3,
    }

    assert records_by_row[2][
        "total_revenue"
    ] == "250000.00"

    assert records_by_row[3][
        "total_revenue"
    ] == "125000.00"

    database_session.expire_all()

    stored_import = database_session.scalar(
        select(SalesImport).where(
            SalesImport.id == sales_import_id,
        ),
    )

    assert stored_import is not None
    assert stored_import.status == "completed"
    assert stored_import.accepted_rows == 2

    stored_record_count = database_session.scalar(
        select(
            func.count(SalesRecord.id),
        ).where(
            SalesRecord.sales_import_id
            == sales_import_id,
        ),
    )

    assert int(stored_record_count or 0) == 2


def test_sales_import_returns_row_validation_errors(
    client: TestClient,
    sales_context: dict[str, object],
) -> None:
    """Accept valid rows and report rejected CSV rows."""

    headers = sales_context["headers"]
    imports_endpoint = sales_context[
        "imports_endpoint"
    ]
    sku = str(
        sales_context["sku"],
    )

    assert isinstance(headers, dict)
    assert isinstance(imports_endpoint, str)

    csv_content = "\n".join(
        [
            (
                "sku,sale_date,quantity,"
                "unit_price,currency"
            ),
            (
                f"{sku},2026-08-01,"
                "1,125000,PKR"
            ),
            (
                "UNKNOWN-SKU,2026-08-02,"
                "1,1000,PKR"
            ),
            (
                f"{sku},not-a-date,"
                "0,-5,USD"
            ),
        ],
    )

    response = client.post(
        imports_endpoint,
        headers=headers,
        files={
            "file": (
                "mixed-sales.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            ),
        },
    )

    assert response.status_code == 201

    result = response.json()

    sales_import = result[
        "sales_import"
    ]

    assert sales_import["status"] == (
        "completed_with_errors"
    )

    assert sales_import["total_rows"] == 3
    assert sales_import["accepted_rows"] == 1
    assert sales_import["rejected_rows"] == 2

    row_errors = result["row_errors"]

    assert any(
        error["row_number"] == 3
        and error["field"] == "sku"
        and "No active business product" in (
            error["message"]
        )
        for error in row_errors
    )

    fourth_row_fields = {
        error["field"]
        for error in row_errors
        if error["row_number"] == 4
    }

    assert fourth_row_fields == {
        "sale_date",
        "quantity",
        "unit_price",
        "currency",
    }

    sales_import_id = int(
        sales_import["id"],
    )

    records_response = client.get(
        (
            f"{imports_endpoint}/"
            f"{sales_import_id}/records"
        ),
        headers=headers,
    )

    assert records_response.status_code == 200
    assert records_response.json()["total"] == 1


def test_sales_import_rejects_missing_headers(
    client: TestClient,
    sales_context: dict[str, object],
) -> None:
    """Reject malformed headers before creating an import."""

    headers = sales_context["headers"]
    imports_endpoint = sales_context[
        "imports_endpoint"
    ]
    sku = str(
        sales_context["sku"],
    )

    assert isinstance(headers, dict)
    assert isinstance(imports_endpoint, str)

    csv_content = "\n".join(
        [
            "sku,sale_date,quantity",
            f"{sku},2026-08-01,2",
        ],
    )

    response = client.post(
        imports_endpoint,
        headers=headers,
        files={
            "file": (
                "missing-column.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            ),
        },
    )

    assert response.status_code == 422

    detail = response.json()["detail"]

    assert detail["message"] == (
        "The CSV is missing required columns."
    )

    assert detail["missing_columns"] == [
        "unit_price",
    ]

    list_response = client.get(
        imports_endpoint,
        headers=headers,
    )

    assert list_response.status_code == 200
    assert list_response.json()["total"] == 0


def test_another_sme_cannot_access_sales_import(
    client: TestClient,
    sales_context: dict[str, object],
) -> None:
    """Hide one SME sales import from another SME."""

    owner_headers = sales_context["headers"]
    imports_endpoint = sales_context[
        "imports_endpoint"
    ]
    sku = str(
        sales_context["sku"],
    )

    assert isinstance(owner_headers, dict)
    assert isinstance(imports_endpoint, str)

    csv_content = "\n".join(
        [
            (
                "sku,sale_date,quantity,"
                "unit_price,currency"
            ),
            (
                f"{sku},2026-08-01,"
                "1,125000,PKR"
            ),
        ],
    )

    import_response = client.post(
        imports_endpoint,
        headers=owner_headers,
        files={
            "file": (
                "private-sales.csv",
                csv_content.encode("utf-8"),
                "text/csv",
            ),
        },
    )

    assert import_response.status_code == 201

    sales_import_id = int(
        import_response.json()[
            "sales_import"
        ]["id"],
    )

    other_headers = register_and_login(
        client,
        account_type="sme",
        prefix="other-sales-sme",
    )

    detail_response = client.get(
        f"{imports_endpoint}/{sales_import_id}",
        headers=other_headers,
    )

    assert detail_response.status_code == 404

    assert detail_response.json()["detail"] == (
        "The requested organization was not found."
    )

    records_response = client.get(
        (
            f"{imports_endpoint}/"
            f"{sales_import_id}/records"
        ),
        headers=other_headers,
    )

    assert records_response.status_code == 404
