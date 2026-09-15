"""Transactional lifecycle operations for scraper monitoring."""

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

    def start_run(
        self,
        database_session: Session,
        payload: ScrapeRunStartInput,
    ) -> ScrapeRunResponse:
        try:
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
            if not payload.crawl_succeeded:
                run_status = "failed"
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
