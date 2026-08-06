"""Business logic for SME sales CSV imports."""

import csv
from collections import Counter
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from io import StringIO
from math import ceil
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.business_product import BusinessProduct
from app.models.sales_import import SalesImport
from app.repositories.sales_repository import SalesRepository
from app.repositories.sme_repository import SMERepository
from app.schemas.sales import (
    SalesCSVRowError,
    SalesImportListResponse,
    SalesImportResponse,
    SalesImportResultResponse,
    SalesRecordListResponse,
    SalesRecordResponse,
)


class SalesService:
    """Process and retrieve SME sales CSV imports."""

    REQUIRED_COLUMNS = {
        "sku",
        "sale_date",
        "quantity",
        "unit_price",
    }

    OPTIONAL_COLUMNS = {
        "currency",
    }

    ALLOWED_COLUMNS = (
        REQUIRED_COLUMNS
        | OPTIONAL_COLUMNS
    )

    MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024

    MAX_DATA_ROWS = 5000

    MAX_UNIT_PRICE = Decimal(
        "999999999999.99",
    )

    MAX_TOTAL_REVENUE = Decimal(
        "99999999999999.99",
    )

    MONEY_QUANTIZER = Decimal("0.01")

    def __init__(
        self,
        repository: SalesRepository | None = None,
        sme_repository: SMERepository | None = None,
    ) -> None:
        self.repository = (
            repository
            or SalesRepository()
        )

        self.sme_repository = (
            sme_repository
            or SMERepository()
        )

    def _get_accessible_organization(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
    ) -> None:
        """Require access to one active organization."""

        organization = (
            self.sme_repository
            .get_organization_for_user(
                database_session,
                organization_id=organization_id,
                user_id=user_id,
            )
        )

        if organization is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The requested organization "
                    "was not found."
                ),
            )

    @staticmethod
    def _sanitize_filename(
        filename: str | None,
    ) -> str:
        """Return a safe uploaded filename."""

        if not filename:
            return "sales-import.csv"

        safe_filename = Path(filename).name.strip()

        if not safe_filename:
            return "sales-import.csv"

        return safe_filename[:255]

    @staticmethod
    def _normalize_header(
        header: str | None,
    ) -> str:
        """Normalize one CSV header name."""

        if header is None:
            return ""

        return header.strip().lower()

    @staticmethod
    def _clean_cell(
        value: object,
    ) -> str:
        """Convert one CSV cell into trimmed text."""

        if value is None:
            return ""

        return str(value).strip()

    @staticmethod
    def _row_is_empty(
        row: dict[str | None, object],
    ) -> bool:
        """Return whether every value in a CSV row is blank."""

        for value in row.values():
            if isinstance(value, list):
                if any(
                    str(item).strip()
                    for item in value
                ):
                    return False

                continue

            if value is not None and str(value).strip():
                return False

        return True

    def _decode_csv(
        self,
        file_content: bytes,
    ) -> str:
        """Decode an uploaded CSV as UTF-8."""

        if not file_content:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail="The uploaded CSV file is empty.",
            )

        if len(file_content) > self.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=(
                    status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
                ),
                detail=(
                    "The CSV file must not exceed "
                    "2 MB."
                ),
            )

        try:
            return file_content.decode(
                "utf-8-sig",
            )

        except UnicodeDecodeError as error:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=(
                    "The CSV file must use UTF-8 "
                    "encoding."
                ),
            ) from error

    def _read_csv_rows(
        self,
        decoded_content: str,
    ) -> list[
        tuple[
            int,
            dict[str | None, object],
        ]
    ]:
        """Validate headers and return non-empty CSV rows."""

        try:
            csv_stream = StringIO(
                decoded_content,
                newline="",
            )

            reader = csv.DictReader(
                csv_stream,
                strict=True,
            )

            raw_headers = reader.fieldnames

            if raw_headers is None:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_CONTENT
                    ),
                    detail=(
                        "The CSV file must contain "
                        "a header row."
                    ),
                )

            normalized_headers = [
                self._normalize_header(header)
                for header in raw_headers
            ]

            if any(
                not header
                for header in normalized_headers
            ):
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_CONTENT
                    ),
                    detail=(
                        "CSV header names cannot "
                        "be blank."
                    ),
                )

            duplicate_headers = sorted(
                header
                for header, count
                in Counter(
                    normalized_headers,
                ).items()
                if count > 1
            )

            if duplicate_headers:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_CONTENT
                    ),
                    detail={
                        "message": (
                            "The CSV contains duplicate "
                            "header columns."
                        ),
                        "duplicate_columns": (
                            duplicate_headers
                        ),
                    },
                )

            header_set = set(
                normalized_headers,
            )

            missing_columns = sorted(
                self.REQUIRED_COLUMNS
                - header_set
            )

            if missing_columns:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_CONTENT
                    ),
                    detail={
                        "message": (
                            "The CSV is missing required "
                            "columns."
                        ),
                        "missing_columns": (
                            missing_columns
                        ),
                    },
                )

            unsupported_columns = sorted(
                header_set
                - self.ALLOWED_COLUMNS
            )

            if unsupported_columns:
                raise HTTPException(
                    status_code=(
                        status.HTTP_422_UNPROCESSABLE_CONTENT
                    ),
                    detail={
                        "message": (
                            "The CSV contains unsupported "
                            "columns."
                        ),
                        "unsupported_columns": (
                            unsupported_columns
                        ),
                    },
                )

            reader.fieldnames = normalized_headers

            rows: list[
                tuple[
                    int,
                    dict[str | None, object],
                ]
            ] = []

            for row_number, row in enumerate(
                reader,
                start=2,
            ):
                if self._row_is_empty(row):
                    continue

                rows.append(
                    (
                        row_number,
                        row,
                    ),
                )

                if len(rows) > self.MAX_DATA_ROWS:
                    raise HTTPException(
                        status_code=(
                            status.HTTP_422_UNPROCESSABLE_CONTENT
                        ),
                        detail=(
                            "The CSV file cannot contain "
                            "more than 5000 data rows."
                        ),
                    )

        except csv.Error as error:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=(
                    "The uploaded file is not a "
                    "valid CSV document."
                ),
            ) from error

        if not rows:
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=(
                    "The CSV file does not contain "
                    "any sales rows."
                ),
            )

        return rows

    @staticmethod
    def _validate_sku(
        value: str,
    ) -> tuple[str | None, SalesCSVRowError | None]:
        """Validate and normalize an SME product SKU."""

        normalized_value = value.strip().upper()

        if not normalized_value:
            return None, SalesCSVRowError(
                row_number=2,
                field="sku",
                message="SKU is required.",
                value=value or None,
            )

        if len(normalized_value) > 120:
            return None, SalesCSVRowError(
                row_number=2,
                field="sku",
                message=(
                    "SKU cannot exceed "
                    "120 characters."
                ),
                value=value[:500] or None,
            )

        return normalized_value, None

    @staticmethod
    def _validate_sale_date(
        value: str,
    ) -> tuple[date | None, SalesCSVRowError | None]:
        """Validate an ISO-format sale date."""

        if not value:
            return None, SalesCSVRowError(
                row_number=2,
                field="sale_date",
                message="Sale date is required.",
                value=None,
            )

        try:
            parsed_date = date.fromisoformat(
                value,
            )

        except ValueError:
            return None, SalesCSVRowError(
                row_number=2,
                field="sale_date",
                message=(
                    "Sale date must use "
                    "YYYY-MM-DD format."
                ),
                value=value[:500],
            )

        return parsed_date, None

    @staticmethod
    def _validate_quantity(
        value: str,
    ) -> tuple[int | None, SalesCSVRowError | None]:
        """Validate a positive whole-number quantity."""

        if not value:
            return None, SalesCSVRowError(
                row_number=2,
                field="quantity",
                message="Quantity is required.",
                value=None,
            )

        try:
            quantity = int(value)

        except ValueError:
            return None, SalesCSVRowError(
                row_number=2,
                field="quantity",
                message=(
                    "Quantity must be a positive "
                    "whole number."
                ),
                value=value[:500],
            )

        if quantity <= 0:
            return None, SalesCSVRowError(
                row_number=2,
                field="quantity",
                message=(
                    "Quantity must be greater "
                    "than zero."
                ),
                value=value[:500],
            )

        return quantity, None

    def _validate_unit_price(
        self,
        value: str,
    ) -> tuple[
        Decimal | None,
        SalesCSVRowError | None,
    ]:
        """Validate a non-negative price with two decimals."""

        if not value:
            return None, SalesCSVRowError(
                row_number=2,
                field="unit_price",
                message="Unit price is required.",
                value=None,
            )

        try:
            unit_price = Decimal(value)

        except InvalidOperation:
            return None, SalesCSVRowError(
                row_number=2,
                field="unit_price",
                message=(
                    "Unit price must be a valid "
                    "number."
                ),
                value=value[:500],
            )

        if not unit_price.is_finite():
            return None, SalesCSVRowError(
                row_number=2,
                field="unit_price",
                message=(
                    "Unit price must be a finite "
                    "number."
                ),
                value=value[:500],
            )

        if unit_price < 0:
            return None, SalesCSVRowError(
                row_number=2,
                field="unit_price",
                message=(
                    "Unit price cannot be negative."
                ),
                value=value[:500],
            )

        try:
            normalized_price = unit_price.quantize(
                self.MONEY_QUANTIZER,
            )

        except InvalidOperation:
            return None, SalesCSVRowError(
                row_number=2,
                field="unit_price",
                message=(
                    "Unit price is outside the "
                    "supported numeric range."
                ),
                value=value[:500],
            )

        if normalized_price != unit_price:
            return None, SalesCSVRowError(
                row_number=2,
                field="unit_price",
                message=(
                    "Unit price can contain at most "
                    "two decimal places."
                ),
                value=value[:500],
            )

        if normalized_price > self.MAX_UNIT_PRICE:
            return None, SalesCSVRowError(
                row_number=2,
                field="unit_price",
                message=(
                    "Unit price exceeds the maximum "
                    "supported value."
                ),
                value=value[:500],
            )

        return normalized_price, None

    @staticmethod
    def _validate_currency(
        value: str,
    ) -> tuple[str | None, SalesCSVRowError | None]:
        """Validate the currently supported currency."""

        normalized_currency = (
            value.strip().upper()
            if value
            else "PKR"
        )

        if (
            len(normalized_currency) != 3
            or not normalized_currency.isalpha()
        ):
            return None, SalesCSVRowError(
                row_number=2,
                field="currency",
                message=(
                    "Currency must contain exactly "
                    "three letters."
                ),
                value=value[:500] or None,
            )

        if normalized_currency != "PKR":
            return None, SalesCSVRowError(
                row_number=2,
                field="currency",
                message=(
                    "Only PKR currency is currently "
                    "supported."
                ),
                value=value[:500],
            )

        return normalized_currency, None

    @staticmethod
    def _set_error_row_number(
        error: SalesCSVRowError,
        row_number: int,
    ) -> SalesCSVRowError:
        """Replace a temporary validation row number."""

        return error.model_copy(
            update={
                "row_number": row_number,
            },
        )

    def _mark_import_failed(
        self,
        database_session: Session,
        *,
        organization_id: int,
        sales_import_id: int,
        total_rows: int,
    ) -> None:
        """Persist a safe failed state after a processing error."""

        database_session.rollback()

        persisted_import = (
            self.repository.get_sales_import(
                database_session,
                organization_id=organization_id,
                sales_import_id=sales_import_id,
            )
        )

        if persisted_import is None:
            return

        self.repository.update_sales_import(
            database_session,
            persisted_import,
            status="failed",
            total_rows=total_rows,
            accepted_rows=0,
            rejected_rows=0,
            error_message=(
                "The CSV import could not be "
                "completed because of an internal "
                "processing error."
            ),
            completed_at=datetime.now(
                timezone.utc,
            ),
        )

        database_session.commit()

    def process_csv_import(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
        filename: str | None,
        file_content: bytes,
    ) -> SalesImportResultResponse:
        """Validate, process and store one sales CSV file."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        safe_filename = self._sanitize_filename(
            filename,
        )

        if not safe_filename.lower().endswith(
            ".csv",
        ):
            raise HTTPException(
                status_code=(
                    status.HTTP_422_UNPROCESSABLE_CONTENT
                ),
                detail=(
                    "Only files with a .csv extension "
                    "are supported."
                ),
            )

        decoded_content = self._decode_csv(
            file_content,
        )

        csv_rows = self._read_csv_rows(
            decoded_content,
        )

        sales_import = (
            self.repository.create_sales_import(
                database_session,
                organization_id=organization_id,
                uploaded_by_user_id=user_id,
                original_filename=safe_filename,
            )
        )

        self.repository.update_sales_import(
            database_session,
            sales_import,
            status="processing",
            total_rows=len(csv_rows),
            accepted_rows=0,
            rejected_rows=0,
            error_message=None,
            completed_at=None,
        )

        database_session.commit()
        database_session.refresh(sales_import)

        row_errors: list[SalesCSVRowError] = []
        accepted_rows = 0
        rejected_rows = 0

        product_cache: dict[
            str,
            BusinessProduct | None,
        ] = {}

        try:
            for row_number, raw_row in csv_rows:
                extra_values = raw_row.get(None)

                if (
                    isinstance(extra_values, list)
                    and any(
                        str(value).strip()
                        for value in extra_values
                    )
                ):
                    row_errors.append(
                        SalesCSVRowError(
                            row_number=row_number,
                            field=None,
                            message=(
                                "The row contains more "
                                "values than the CSV "
                                "header defines."
                            ),
                            value=", ".join(
                                str(value)
                                for value in extra_values
                            )[:500],
                        ),
                    )

                    rejected_rows += 1
                    continue

                sku_text = self._clean_cell(
                    raw_row.get("sku"),
                )

                sale_date_text = self._clean_cell(
                    raw_row.get("sale_date"),
                )

                quantity_text = self._clean_cell(
                    raw_row.get("quantity"),
                )

                unit_price_text = self._clean_cell(
                    raw_row.get("unit_price"),
                )

                currency_text = self._clean_cell(
                    raw_row.get("currency"),
                )

                row_validation_errors: list[
                    SalesCSVRowError
                ] = []

                sku, sku_error = self._validate_sku(
                    sku_text,
                )

                if sku_error is not None:
                    row_validation_errors.append(
                        self._set_error_row_number(
                            sku_error,
                            row_number,
                        ),
                    )

                parsed_sale_date, date_error = (
                    self._validate_sale_date(
                        sale_date_text,
                    )
                )

                if date_error is not None:
                    row_validation_errors.append(
                        self._set_error_row_number(
                            date_error,
                            row_number,
                        ),
                    )

                quantity, quantity_error = (
                    self._validate_quantity(
                        quantity_text,
                    )
                )

                if quantity_error is not None:
                    row_validation_errors.append(
                        self._set_error_row_number(
                            quantity_error,
                            row_number,
                        ),
                    )

                unit_price, price_error = (
                    self._validate_unit_price(
                        unit_price_text,
                    )
                )

                if price_error is not None:
                    row_validation_errors.append(
                        self._set_error_row_number(
                            price_error,
                            row_number,
                        ),
                    )

                currency, currency_error = (
                    self._validate_currency(
                        currency_text,
                    )
                )

                if currency_error is not None:
                    row_validation_errors.append(
                        self._set_error_row_number(
                            currency_error,
                            row_number,
                        ),
                    )

                business_product = None

                if sku is not None:
                    if sku not in product_cache:
                        product_cache[sku] = (
                            self.repository
                            .get_business_product_by_sku(
                                database_session,
                                organization_id=(
                                    organization_id
                                ),
                                sku=sku,
                            )
                        )

                    business_product = product_cache[
                        sku
                    ]

                    if business_product is None:
                        row_validation_errors.append(
                            SalesCSVRowError(
                                row_number=row_number,
                                field="sku",
                                message=(
                                    "No active business "
                                    "product was found for "
                                    "this SKU."
                                ),
                                value=sku[:500],
                            ),
                        )

                if row_validation_errors:
                    row_errors.extend(
                        row_validation_errors,
                    )

                    rejected_rows += 1
                    continue

                assert business_product is not None
                assert parsed_sale_date is not None
                assert quantity is not None
                assert unit_price is not None
                assert currency is not None

                total_revenue = (
                    Decimal(quantity)
                    * unit_price
                ).quantize(
                    self.MONEY_QUANTIZER,
                )

                if (
                    total_revenue
                    > self.MAX_TOTAL_REVENUE
                ):
                    row_errors.append(
                        SalesCSVRowError(
                            row_number=row_number,
                            field="total_revenue",
                            message=(
                                "Calculated total revenue "
                                "exceeds the maximum "
                                "supported value."
                            ),
                            value=str(
                                total_revenue,
                            )[:500],
                        ),
                    )

                    rejected_rows += 1
                    continue

                self.repository.create_sales_record(
                    database_session,
                    sales_import_id=sales_import.id,
                    business_product_id=(
                        business_product.id
                    ),
                    source_row_number=row_number,
                    sale_date=parsed_sale_date,
                    quantity=quantity,
                    unit_price=unit_price,
                    total_revenue=total_revenue,
                    currency=currency,
                )

                accepted_rows += 1

            final_status = (
                "completed"
                if rejected_rows == 0
                else "completed_with_errors"
            )

            error_message = (
                None
                if rejected_rows == 0
                else (
                    f"{rejected_rows} sales row(s) "
                    "were rejected during validation."
                )
            )

            self.repository.update_sales_import(
                database_session,
                sales_import,
                status=final_status,
                total_rows=len(csv_rows),
                accepted_rows=accepted_rows,
                rejected_rows=rejected_rows,
                error_message=error_message,
                completed_at=datetime.now(
                    timezone.utc,
                ),
            )

            database_session.commit()
            database_session.refresh(sales_import)

        except IntegrityError as error:
            self._mark_import_failed(
                database_session,
                organization_id=organization_id,
                sales_import_id=sales_import.id,
                total_rows=len(csv_rows),
            )

            raise HTTPException(
                status_code=(
                    status.HTTP_409_CONFLICT
                ),
                detail=(
                    "The sales import conflicted with "
                    "existing database records."
                ),
            ) from error

        except HTTPException:
            database_session.rollback()
            raise

        except Exception as error:
            self._mark_import_failed(
                database_session,
                organization_id=organization_id,
                sales_import_id=sales_import.id,
                total_rows=len(csv_rows),
            )

            raise HTTPException(
                status_code=(
                    status.HTTP_500_INTERNAL_SERVER_ERROR
                ),
                detail=(
                    "The sales CSV import could not "
                    "be completed."
                ),
            ) from error

        return SalesImportResultResponse(
            sales_import=(
                SalesImportResponse.model_validate(
                    sales_import,
                )
            ),
            row_errors=row_errors,
        )

    def list_sales_imports(
        self,
        database_session: Session,
        *,
        organization_id: int,
        user_id: int,
        page: int,
        page_size: int,
    ) -> SalesImportListResponse:
        """Return paginated imports for one organization."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        total, imports = (
            self.repository.list_sales_imports(
                database_session,
                organization_id=organization_id,
                page=page,
                page_size=page_size,
            )
        )

        total_pages = (
            ceil(total / page_size)
            if total > 0
            else 0
        )

        return SalesImportListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=[
                SalesImportResponse.model_validate(
                    sales_import,
                )
                for sales_import in imports
            ],
        )

    def read_sales_import(
        self,
        database_session: Session,
        *,
        organization_id: int,
        sales_import_id: int,
        user_id: int,
    ) -> SalesImportResponse:
        """Return one accessible sales import."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        sales_import = (
            self.repository.get_sales_import(
                database_session,
                organization_id=organization_id,
                sales_import_id=sales_import_id,
            )
        )

        if sales_import is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The requested sales import "
                    "was not found."
                ),
            )

        return SalesImportResponse.model_validate(
            sales_import,
        )

    def list_sales_records(
        self,
        database_session: Session,
        *,
        organization_id: int,
        sales_import_id: int,
        user_id: int,
        page: int,
        page_size: int,
    ) -> SalesRecordListResponse:
        """Return accepted records from one sales import."""

        self._get_accessible_organization(
            database_session,
            organization_id=organization_id,
            user_id=user_id,
        )

        sales_import = (
            self.repository.get_sales_import(
                database_session,
                organization_id=organization_id,
                sales_import_id=sales_import_id,
            )
        )

        if sales_import is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "The requested sales import "
                    "was not found."
                ),
            )

        total, records = (
            self.repository.list_sales_records(
                database_session,
                organization_id=organization_id,
                sales_import_id=sales_import_id,
                page=page,
                page_size=page_size,
            )
        )

        total_pages = (
            ceil(total / page_size)
            if total > 0
            else 0
        )

        return SalesRecordListResponse(
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
            items=[
                SalesRecordResponse.model_validate(
                    record,
                )
                for record in records
            ],
        )
