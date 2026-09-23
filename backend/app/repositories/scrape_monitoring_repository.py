"""Database operations for durable scraper execution monitoring."""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.scrape_error import ScrapeError
from app.models.scrape_run import ScrapeRun


class ScrapeMonitoringRepository:
    @staticmethod
    def create_run(
        database_session: Session,
        *,
        platform: str,
        spider_name: str,
        trigger_type: str,
        parser_version: str,
    ) -> ScrapeRun:
        run = ScrapeRun(
            platform=platform,
            spider_name=spider_name,
            status="running",
            trigger_type=trigger_type,
            parser_version=parser_version,
        )
        database_session.add(run)
        database_session.flush()
        return run

    @staticmethod
    def get_run(
        database_session: Session,
        run_id: int,
        *,
        with_errors: bool = False,
        for_update: bool = False,
    ) -> ScrapeRun | None:
        statement = select(ScrapeRun).where(ScrapeRun.id == run_id)
        if with_errors:
            statement = statement.options(selectinload(ScrapeRun.errors))
        if for_update:
            statement = statement.with_for_update()
        return database_session.scalar(statement)

    @staticmethod
    def record_ingested_item(run: ScrapeRun) -> None:
        run.items_discovered += 1
        run.items_ingested += 1

    @staticmethod
    def create_error(
        database_session: Session,
        run: ScrapeRun,
        *,
        outcome: str,
        item_discovered: bool,
        external_listing_id: str | None,
        product_url: str | None,
        error_type: str,
        error_stage: str,
        message: str,
        raw_value: str | None,
        error_metadata: dict[str, Any],
    ) -> ScrapeError:
        if item_discovered:
            run.items_discovered += 1
        if outcome == "rejected":
            run.items_rejected += 1
        else:
            run.items_failed += 1
        run.error_count += 1

        error = ScrapeError(
            scrape_run_id=run.id,
            external_listing_id=external_listing_id,
            product_url=product_url,
            error_type=error_type,
            error_stage=error_stage,
            message=message,
            raw_value=raw_value,
            error_metadata=error_metadata,
        )
        database_session.add(error)
        database_session.flush()
        return error

    @staticmethod
    def finalize_run(
        run: ScrapeRun,
        *,
        status: str,
        items_discovered: int,
        items_ingested: int,
        items_rejected: int,
        items_failed: int,
        error_count: int,
    ) -> None:
        run.status = status
        run.finished_at = datetime.now(UTC)
        run.items_discovered = max(run.items_discovered, items_discovered)
        run.items_ingested = max(run.items_ingested, items_ingested)
        run.items_rejected = max(run.items_rejected, items_rejected)
        run.items_failed = max(run.items_failed, items_failed)
        run.error_count = max(run.error_count, error_count)

    @staticmethod
    def list_runs(
        database_session: Session,
        *,
        limit: int,
    ) -> list[ScrapeRun]:
        statement = (
            select(ScrapeRun)
            .order_by(ScrapeRun.started_at.desc(), ScrapeRun.id.desc())
            .limit(limit)
        )
        return list(database_session.scalars(statement).all())
