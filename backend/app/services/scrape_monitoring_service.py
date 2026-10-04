"""Transactional lifecycle operations for scraper monitoring."""

from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.scrape_run import ScrapeRun
from app.core.config import settings
from app.repositories.scrape_monitoring_repository import (
    ScrapeMonitoringRepository,
)
from app.schemas.scrape_monitoring import (
    ScrapeErrorInput,
    ScrapeErrorResponse,
    ScrapeRunDetailResponse,
    ScrapeRunFinishInput,
    ScrapeRunResponse,
    ScrapeRunStartInput,
)


class ScrapeMonitoringService:
    def __init__(
        self,
        repository: ScrapeMonitoringRepository | None = None,
    ) -> None:
        self.repository = repository or ScrapeMonitoringRepository()

    @staticmethod
    def _sanitize_text(value: str | None) -> str | None:
        if value is None:
            return None
        sanitized = value
        if settings.ingestion_api_key:
            sanitized = sanitized.replace(
                settings.ingestion_api_key,
                "[REDACTED]",
            )
        return sanitized

    @classmethod
    def _sanitize_metadata(cls, value: dict) -> dict:
        sensitive_fragments = (
            "authorization",
            "password",
            "secret",
            "token",
            "api_key",
            "ingestion_key",
            "headers",
        )
        return {
            str(key)[:100]: (
                "[REDACTED]"
                if any(
                    fragment in str(key).lower()
                    for fragment in sensitive_fragments
                )
                else cls._sanitize_text(str(item))[:500]
            )
            for key, item in value.items()
        }

    @staticmethod
    def _require_running(run: ScrapeRun | None) -> ScrapeRun:
        if run is None:
            raise HTTPException(status_code=404, detail="Scrape run not found.")
        if run.status != "running":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The scrape run is already finalized.",
            )
        return run

    # A crawl that has not reported anything for this long is not running
    # any more: the process was killed, crashed or lost the backend.
    STALE_RUN_HOURS = 6

    def reconcile_stale_runs(
        self,
        database_session: Session,
        *,
        platform: str | None = None,
        max_age_hours: int | None = None,
    ) -> int:
        """Close runs left marked running by a crawl that never finished."""

        # ``0`` is a deliberate caller choice ("close every running row"),
        # so it must not fall through to the default.
        if max_age_hours is None:
            max_age_hours = self.STALE_RUN_HOURS

        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        stale_runs = self.repository.list_stale_running_runs(
            database_session,
            started_before=cutoff,
            platform=platform,
        )

        for run in stale_runs:
            self.repository.finalize_run(
                run,
                status="failed",
                items_discovered=run.items_discovered,
                items_ingested=run.items_ingested,
                items_rejected=run.items_rejected,
                items_failed=run.items_failed,
                error_count=run.error_count,
                products_created=run.products_created,
                listings_created=run.listings_created,
                listings_updated=run.listings_updated,
                price_changes=run.price_changes,
                reviews_added=run.reviews_added,
                error_summary=(
                    "The crawl stopped without reporting completion and was "
                    "closed by VEXTRO."
                ),
            )

        return len(stale_runs)

    def start_run(
        self,
        database_session: Session,
        payload: ScrapeRunStartInput,
    ) -> ScrapeRunResponse:
        try:
            # A new crawl for this platform proves any older "running" row
            # belongs to a process that is gone.
            self.reconcile_stale_runs(
                database_session,
                platform=payload.platform,
            )
            run = self.repository.create_run(
                database_session,
                platform=payload.platform,
                spider_name=payload.spider_name,
                trigger_type=payload.trigger_type,
                parser_version=payload.parser_version,
            )
            database_session.commit()
            database_session.refresh(run)
            return ScrapeRunResponse.model_validate(run)
        except Exception:
            database_session.rollback()
            raise

    def record_ingested_item(
        self,
        database_session: Session,
        run_id: int,
    ) -> ScrapeRunResponse:
        try:
            run = self._require_running(
                self.repository.get_run(
                    database_session,
                    run_id,
                    for_update=True,
                )
            )
            self.repository.record_ingested_item(run)
            database_session.commit()
            database_session.refresh(run)
            return ScrapeRunResponse.model_validate(run)
        except Exception:
            database_session.rollback()
            raise

    def record_error(
        self,
        database_session: Session,
        run_id: int,
        payload: ScrapeErrorInput,
    ) -> ScrapeErrorResponse:
        try:
            run = self._require_running(
                self.repository.get_run(
                    database_session,
                    run_id,
                    for_update=True,
                )
            )
            error = self.repository.create_error(
                database_session,
                run,
                outcome=payload.outcome,
                item_discovered=payload.item_discovered,
                external_listing_id=payload.external_listing_id,
                product_url=payload.product_url,
                error_type=payload.error_type,
                error_stage=payload.error_stage,
                message=self._sanitize_text(payload.message) or "Scrape error",
                raw_value=self._sanitize_text(payload.raw_value),
                error_metadata=self._sanitize_metadata(payload.metadata),
            )
            database_session.commit()
            database_session.refresh(error)
            return ScrapeErrorResponse.model_validate(error)
        except Exception:
            database_session.rollback()
            raise

    def finish_run(
        self,
        database_session: Session,
        run_id: int,
        payload: ScrapeRunFinishInput,
    ) -> ScrapeRunResponse:
        try:
            run = self._require_running(
                self.repository.get_run(
                    database_session,
                    run_id,
                    for_update=True,
                )
            )
            error_summary = payload.error_summary

            if not payload.crawl_succeeded:
                run_status = "failed"
            elif not payload.items_discovered:
                # A marketplace crawl that discovered nothing has not
                # succeeded: the catalog page changed shape or the request
                # was blocked. Reporting it as completed hid both.
                run_status = "failed"
                error_summary = error_summary or (
                    "The crawl finished without discovering any marketplace "
                    "items."
                )
            elif payload.items_rejected or payload.items_failed:
                run_status = "partial"
            else:
                run_status = "completed"
            self.repository.finalize_run(
                run,
                status=run_status,
                items_discovered=payload.items_discovered,
                items_ingested=payload.items_ingested,
                items_rejected=payload.items_rejected,
                items_failed=payload.items_failed,
                error_count=payload.error_count,
                products_created=payload.products_created,
                listings_created=payload.listings_created,
                listings_updated=payload.listings_updated,
                price_changes=payload.price_changes,
                reviews_added=payload.reviews_added,
                error_summary=self._sanitize_text(error_summary),
            )
            database_session.commit()
            database_session.refresh(run)
            return ScrapeRunResponse.model_validate(run)
        except Exception:
            database_session.rollback()
            raise

    def list_runs(
        self,
        database_session: Session,
        *,
        limit: int,
    ) -> list[ScrapeRunResponse]:
        return [
            ScrapeRunResponse.model_validate(run)
            for run in self.repository.list_runs(database_session, limit=limit)
        ]

    def get_run(
        self,
        database_session: Session,
        run_id: int,
    ) -> ScrapeRunDetailResponse:
        run = self.repository.get_run(
            database_session,
            run_id,
            with_errors=True,
        )
        if run is None:
            raise HTTPException(status_code=404, detail="Scrape run not found.")
        return ScrapeRunDetailResponse.model_validate(run)
