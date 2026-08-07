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
    @staticmethod
    def get_sales_analytics(
        database_session: Session,
        *,
        organization_id: int,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> dict:
        """Aggregate sales analytics for one organization."""

        conditions = [
            SalesImport.organization_id
            == organization_id,
        ]

        if start_date is not None:
            conditions.append(
                SalesRecord.sale_date
                >= start_date,
            )

        if end_date is not None:
            conditions.append(
                SalesRecord.sale_date
                <= end_date,
            )

        summary_statement = (
            select(
                func.coalesce(
                    func.sum(
                        SalesRecord.total_revenue,
                    ),
                    0,
                ).label("total_revenue"),
                func.coalesce(
                    func.sum(
                        SalesRecord.quantity,
                    ),
                    0,
                ).label("total_units_sold"),
                func.count(
                    SalesRecord.id,
                ).label("total_sales_records"),
                func.count(
                    func.distinct(
                        SalesRecord.business_product_id,
                    ),
                ).label("products_sold"),
            )
            .select_from(SalesRecord)
            .join(
                SalesImport,
                SalesImport.id
                == SalesRecord.sales_import_id,
            )
            .where(
                *conditions,
            )
        )

        summary_row = database_session.execute(
            summary_statement,
        ).one()

        total_revenue = Decimal(
            summary_row.total_revenue or 0,
        )

        total_units_sold = int(
            summary_row.total_units_sold or 0,
        )

        total_sales_records = int(
            summary_row.total_sales_records or 0,
        )

        products_sold = int(
            summary_row.products_sold or 0,
        )

        if total_units_sold > 0:
            average_selling_price = (
                total_revenue
                / Decimal(total_units_sold)
            ).quantize(
                Decimal("0.01"),
            )
        else:
            average_selling_price = Decimal(
                "0.00",
            )

        trend_statement = (
            select(
                SalesRecord.sale_date.label(
                    "sale_date",
                ),
                func.coalesce(
                    func.sum(
                        SalesRecord.total_revenue,
                    ),
                    0,
                ).label("revenue"),
                func.coalesce(
                    func.sum(
                        SalesRecord.quantity,
                    ),
                    0,
                ).label("units_sold"),
                func.count(
                    SalesRecord.id,
                ).label("sales_records"),
            )
            .select_from(SalesRecord)
            .join(
                SalesImport,
                SalesImport.id
                == SalesRecord.sales_import_id,
            )
            .where(
                *conditions,
            )
            .group_by(
                SalesRecord.sale_date,
            )
            .order_by(
                SalesRecord.sale_date.asc(),
            )
        )

        trend_rows = database_session.execute(
            trend_statement,
        ).all()

        revenue_trend = [
            {
                "sale_date": row.sale_date,
                "revenue": Decimal(
                    row.revenue or 0,
                ),
                "units_sold": int(
                    row.units_sold or 0,
                ),
                "sales_records": int(
                    row.sales_records or 0,
                ),
            }
            for row in trend_rows
        ]

        product_statement = (
            select(
                BusinessProduct.id.label(
                    "business_product_id",
                ),
                BusinessProduct.name.label(
                    "product_name",
                ),
                BusinessProduct.sku.label(
                    "sku",
                ),
                func.coalesce(
                    func.sum(
                        SalesRecord.total_revenue,
                    ),
                    0,
                ).label("revenue"),
                func.coalesce(
                    func.sum(
                        SalesRecord.quantity,
                    ),
                    0,
                ).label("units_sold"),
                func.count(
                    SalesRecord.id,
                ).label("sales_records"),
            )
            .select_from(SalesRecord)
            .join(
                SalesImport,
                SalesImport.id
                == SalesRecord.sales_import_id,
            )
            .join(
                BusinessProduct,
                BusinessProduct.id
                == SalesRecord.business_product_id,
            )
            .where(
                *conditions,
            )
            .group_by(
                BusinessProduct.id,
                BusinessProduct.name,
                BusinessProduct.sku,
            )
            .order_by(
                func.sum(
                    SalesRecord.total_revenue,
                ).desc(),
                func.sum(
                    SalesRecord.quantity,
                ).desc(),
                BusinessProduct.id.asc(),
            )
        )

        product_rows = database_session.execute(
            product_statement,
        ).all()

        product_performance = []

        for row in product_rows:
            revenue = Decimal(
                row.revenue or 0,
            )

            units_sold = int(
                row.units_sold or 0,
            )

            if units_sold > 0:
                average_price = (
                    revenue
                    / Decimal(units_sold)
                ).quantize(
                    Decimal("0.01"),
                )
            else:
                average_price = Decimal(
                    "0.00",
                )

            product_performance.append(
                {
                    "business_product_id":
                        row.business_product_id,
                    "product_name":
                        row.product_name,
                    "sku":
                        row.sku,
                    "revenue":
                        revenue,
                    "units_sold":
                        units_sold,
                    "sales_records":
                        int(
                            row.sales_records or 0,
                        ),
                    "average_selling_price":
                        average_price,
                },
            )

        return {
            "total_revenue":
                total_revenue,
            "total_units_sold":
                total_units_sold,
            "total_sales_records":
                total_sales_records,
            "average_selling_price":
                average_selling_price,
            "products_sold":
                products_sold,
            "revenue_trend":
                revenue_trend,
            "product_performance":
                product_performance,
        }