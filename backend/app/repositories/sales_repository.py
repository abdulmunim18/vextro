"""Database operations for SME sales CSV imports."""

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.business_product import BusinessProduct
from app.models.sales_import import SalesImport
from app.models.sales_record import SalesRecord


class SalesRepository:
    """Store and retrieve SME sales imports and records."""

    @staticmethod
    def create_sales_import(
        database_session: Session,
        *,
        organization_id: int,
        uploaded_by_user_id: int,
        original_filename: str,
    ) -> SalesImport:
        """Create a pending sales-import operation."""

        sales_import = SalesImport(
            organization_id=organization_id,
            uploaded_by_user_id=uploaded_by_user_id,
            original_filename=original_filename,
            status="pending",
            total_rows=0,
            accepted_rows=0,
            rejected_rows=0,
            error_message=None,
            completed_at=None,
        )

        database_session.add(sales_import)
        database_session.flush()

        return sales_import

    @staticmethod
    def update_sales_import(
        database_session: Session,
        sales_import: SalesImport,
        *,
        status: str,
        total_rows: int,
        accepted_rows: int,
        rejected_rows: int,
        error_message: str | None,
        completed_at: datetime | None,
    ) -> SalesImport:
        """Update the result of a sales-import operation."""

        sales_import.status = status
        sales_import.total_rows = total_rows
        sales_import.accepted_rows = accepted_rows
        sales_import.rejected_rows = rejected_rows
        sales_import.error_message = error_message
        sales_import.completed_at = completed_at

        database_session.flush()

        return sales_import

    @staticmethod
    def get_business_product_by_sku(
        database_session: Session,
        *,
        organization_id: int,
        sku: str,
    ) -> BusinessProduct | None:
        """Return one active product matching an organization SKU."""

        normalized_sku = sku.strip().lower()

        statement = select(
            BusinessProduct,
        ).where(
            BusinessProduct.organization_id
            == organization_id,
            BusinessProduct.sku.is_not(None),
            func.lower(BusinessProduct.sku)
            == normalized_sku,
            BusinessProduct.is_active.is_(True),
        )

        return database_session.scalar(statement)

    @staticmethod
    def create_sales_record(
        database_session: Session,
        *,
        sales_import_id: int,
        business_product_id: int,
        source_row_number: int,
        sale_date: date,
        quantity: int,
        unit_price: Decimal,
        total_revenue: Decimal,
        currency: str,
    ) -> SalesRecord:
        """Create one validated sales record."""

        sales_record = SalesRecord(
            sales_import_id=sales_import_id,
            business_product_id=business_product_id,
            source_row_number=source_row_number,
            sale_date=sale_date,
            quantity=quantity,
            unit_price=unit_price,
            total_revenue=total_revenue,
            currency=currency,
        )

        database_session.add(sales_record)
        database_session.flush()

        return sales_record

    @staticmethod
    def get_sales_import(
        database_session: Session,
        *,
        organization_id: int,
        sales_import_id: int,
    ) -> SalesImport | None:
        """Return one import belonging to an organization."""

        statement = select(
            SalesImport,
        ).where(
            SalesImport.id == sales_import_id,
            SalesImport.organization_id
            == organization_id,
        )

        return database_session.scalar(statement)

    @staticmethod
    def list_sales_imports(
        database_session: Session,
        *,
        organization_id: int,
        page: int,
        page_size: int,
    ) -> tuple[int, list[SalesImport]]:
        """Return paginated sales imports for an organization."""

        conditions = [
            SalesImport.organization_id
            == organization_id,
        ]

        total_statement = select(
            func.count(SalesImport.id),
        ).where(
            *conditions,
        )

        total = int(
            database_session.scalar(
                total_statement,
            )
            or 0
        )

        statement = (
            select(SalesImport)
            .where(*conditions)
            .order_by(
                SalesImport.created_at.desc(),
                SalesImport.id.desc(),
            )
            .offset(
                (page - 1) * page_size,
            )
            .limit(page_size)
        )

        items = list(
            database_session.scalars(statement),
        )

        return total, items

    @staticmethod
    def list_sales_records(
        database_session: Session,
        *,
        organization_id: int,
        sales_import_id: int,
        page: int,
        page_size: int,
    ) -> tuple[int, list[SalesRecord]]:
        """Return paginated records from one organization import."""

        conditions = [
            SalesRecord.sales_import_id
            == sales_import_id,
            SalesImport.organization_id
            == organization_id,
        ]

        total_statement = (
            select(
                func.count(SalesRecord.id),
            )
            .join(
                SalesImport,
                SalesImport.id
                == SalesRecord.sales_import_id,
            )
            .where(*conditions)
        )

        total = int(
            database_session.scalar(
                total_statement,
            )
            or 0
        )

        statement = (
            select(SalesRecord)
            .join(
                SalesImport,
                SalesImport.id
                == SalesRecord.sales_import_id,
            )
            .where(*conditions)
            .order_by(
                SalesRecord.sale_date.desc(),
                SalesRecord.source_row_number.asc(),
            )
            .offset(
                (page - 1) * page_size,
            )
            .limit(page_size)
        )

        items = list(
            database_session.scalars(statement),
        )

        return total, items
