"""Scheduled daily and weekly digest reporting.

Digest content is built only from data VEXTRO already records: the
notification events raised during the period, the user's current price
alerts and, for SME owners, the existing competitor-intelligence
analysis. Nothing is invented.

Period boundaries are computed in the configured digest timezone
(``DIGEST_TIMEZONE``, default ``Asia/Karachi``) and then converted to UTC
for querying, so a "daily" digest covers the user-facing calendar day
rather than a UTC day. There is no per-user timezone in the schema, so one
system timezone applies to everybody.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, settings as default_settings
from app.models.digest_run import (
    DIGEST_STATUS_DELIVERED,
    DIGEST_STATUS_FAILED,
    DIGEST_STATUS_SKIPPED_EMPTY,
    DigestRun,
    FREQUENCY_DAILY,
    FREQUENCY_WEEKLY,
)
from app.models.notification_event import (
    EVENT_TYPE_COMPETITOR_RISK,
    EVENT_TYPE_PRICE_DROP,
)
from app.models.organization import Organization
from app.models.price_alert import PriceAlert
from app.repositories.notification_event_repository import (
    list_user_events_in_period,
)
from app.repositories.notification_preference_repository import (
    list_digest_recipients,
)
from app.repositories.user_repository import get_user_by_id
from app.services.email_service import (
    EmailAttachment,
    EmailDeliveryError,
    EmailNotConfiguredError,
    send_email,
)
from app.services.email_templates import render_digest_email


logger = logging.getLogger(__name__)


MAX_SECTION_LINES = 15


@dataclass(frozen=True)
class DigestPeriod:
    """One digest reporting window with its idempotency key."""

    frequency: str
    period_key: str
    period_label: str
    start_utc: datetime
    end_utc: datetime


def resolve_digest_period(
    *,
    frequency: str,
    reference: datetime | None = None,
    settings: Settings | None = None,
) -> DigestPeriod:
    """Return the most recent complete period for one frequency.

    A digest always reports a period that has already finished, so a job
    running on Tuesday morning sends Monday's daily digest and never a
    partial day.
    """

    active_settings = settings or default_settings
    zone = active_settings.digest_zoneinfo

    local_now = (
        reference.astimezone(zone)
        if reference is not None
        else datetime.now(zone)
    )

    if frequency == FREQUENCY_WEEKLY:
        # The last complete week, ending on the configured weekday.
        week_start_weekday = active_settings.digest_weekly_day % 7

        days_since_start = (
            local_now.weekday() - week_start_weekday
        ) % 7

        current_week_start = (
            local_now.date() - timedelta(days=days_since_start)
        )

        period_start_date = current_week_start - timedelta(days=7)
        period_end_date = current_week_start

        iso_year, iso_week, _ = period_start_date.isocalendar()

        return DigestPeriod(
            frequency=FREQUENCY_WEEKLY,
            period_key=f"{iso_year}-W{iso_week:02d}",
            period_label=(
                f"{period_start_date.strftime('%d %b %Y')} to "
                f"{(period_end_date - timedelta(days=1)).strftime('%d %b %Y')}"
            ),
            start_utc=_to_utc(period_start_date, zone),
            end_utc=_to_utc(period_end_date, zone),
        )

    period_start_date = local_now.date() - timedelta(days=1)
    period_end_date = local_now.date()

    return DigestPeriod(
        frequency=FREQUENCY_DAILY,
        period_key=period_start_date.isoformat(),
        period_label=period_start_date.strftime("%d %b %Y"),
        start_utc=_to_utc(period_start_date, zone),
        end_utc=_to_utc(period_end_date, zone),
    )


def _to_utc(
    local_date: date,
    zone: Any,
) -> datetime:
    """Convert a local calendar date's midnight into UTC."""

    return datetime.combine(
        local_date,
        time.min,
        tzinfo=zone,
    ).astimezone(UTC)


def _format_money(
    amount: Any,
    currency: str,
) -> str:
    """Render a currency amount for digest text."""

    try:
        return f"{currency} {Decimal(str(amount)):,.2f}"
    except (ValueError, ArithmeticError):
        return f"{currency} {amount}"


def _owned_organization(
    database_session: Session,
    *,
    user_id: int,
) -> Organization | None:
    """Return the active organization owned by one user, if any."""

    query = (
        select(Organization)
        .where(
            Organization.owner_user_id == user_id,
            Organization.is_active.is_(True),
        )
        .order_by(Organization.created_at.asc())
        .limit(1)
    )

    return database_session.scalar(query)


def _consumer_sections(
    database_session: Session,
    *,
    user_id: int,
    period: DigestPeriod,
) -> list[dict[str, Any]]:
    """Build the consumer digest sections for one period."""

    sections: list[dict[str, Any]] = []

    triggered_events = list_user_events_in_period(
        database_session,
        user_id=user_id,
        event_types=(EVENT_TYPE_PRICE_DROP,),
        period_start=period.start_utc,
        period_end=period.end_utc,
        limit=MAX_SECTION_LINES,
    )

    if triggered_events:
        sections.append(
            {
                "title": "Price alerts triggered",
                "lines": [
                    (
                        f"{event.payload.get('product_name', 'A product')}"
                        " reached "
                        + _format_money(
                            event.payload.get("current_price"),
                            str(event.payload.get("currency") or "PKR"),
                        )
                        + " against your target of "
                        + _format_money(
                            event.payload.get("target_price"),
                            str(event.payload.get("currency") or "PKR"),
                        )
                    )
                    for event in triggered_events
                ],
            }
        )

    waiting_alerts = list(
        database_session.scalars(
            select(PriceAlert)
            .where(
                PriceAlert.user_id == user_id,
                PriceAlert.is_active.is_(True),
                PriceAlert.is_triggered.is_(False),
            )
            .order_by(PriceAlert.created_at.desc())
            .limit(MAX_SECTION_LINES)
        ).all()
    )

    if triggered_events and waiting_alerts:
        sections.append(
            {
                "title": "Alerts still watching",
                "lines": [
                    (
                        "Target "
                        + _format_money(
                            alert.target_price,
                            alert.currency,
                        )
                        + (
                            f" on {alert.canonical_product.name}"
                            if alert.canonical_product is not None
                            else " on a tracked listing"
                        )
                    )
                    for alert in waiting_alerts
                ],
            }
        )

    return sections


def _sme_sections(
    database_session: Session,
    *,
    user_id: int,
    period: DigestPeriod,
) -> list[dict[str, Any]]:
    """Build the SME digest sections for one period."""

    sections: list[dict[str, Any]] = []

    risk_events = list_user_events_in_period(
        database_session,
        user_id=user_id,
        event_types=(EVENT_TYPE_COMPETITOR_RISK,),
        period_start=period.start_utc,
        period_end=period.end_utc,
        limit=MAX_SECTION_LINES,
    )

    if risk_events:
        sections.append(
            {
                "title": "Competitor risk events",
                "lines": [
                    (
                        f"{event.payload.get('product_name', 'A product')}"
                        f" is {event.payload.get('price_gap_percentage')}%"
                        " above a competitor priced at "
                        + _format_money(
                            event.payload.get("competitor_price"),
                            str(event.payload.get("currency") or "PKR"),
                        )
                    )
                    for event in risk_events
                ],
            }
        )

    return sections


def _sme_report_attachments(
    database_session: Session,
    *,
    user_id: int,
    settings: Settings,
) -> tuple[EmailAttachment, ...]:
    """Attach the existing competitor PDF report when one is available.

    This reuses the module 6.13 report generators rather than duplicating
    any reporting logic. A failure here must never stop the digest.
    """

    if not settings.digest_attach_sme_report:
        return ()

    organization = _owned_organization(
        database_session,
        user_id=user_id,
    )

    if organization is None:
        return ()

    try:
        from app.services.competitor_report_service import (
            build_competitor_pdf,
        )
        from app.services.sme_service import SMEService

        intelligence = SMEService().get_competitor_intelligence(
            database_session,
            organization_id=organization.id,
            user_id=user_id,
            risk_threshold_percentage=Decimal("5.00"),
        )

        if not intelligence.items:
            return ()

        content = build_competitor_pdf(
            organization_name=organization.name,
            intelligence=intelligence,
        )

    except Exception:  # noqa: BLE001 - attachment is best effort only
        logger.exception(
            "digest.attachment.failed user_id=%s",
            user_id,
        )

        return ()

    return (
        EmailAttachment(
            filename=(
                f"vextro-{organization.slug}-competitor-report.pdf"
            ),
            content=content,
            media_type="application/pdf",
        ),
    )


def build_digest_payload(
    database_session: Session,
    *,
    user_id: int,
    period: DigestPeriod,
) -> dict[str, Any] | None:
    """Return the digest payload, or ``None`` when nothing happened.

    Returning ``None`` is what keeps VEXTRO from emailing a user to say
    that nothing changed.
    """

    organization = _owned_organization(
        database_session,
        user_id=user_id,
    )

    audience = (
        "sme"
        if organization is not None
        else "consumer"
    )

    if audience == "sme":
        sections = _sme_sections(
            database_session,
            user_id=user_id,
            period=period,
        )
    else:
        sections = _consumer_sections(
            database_session,
            user_id=user_id,
            period=period,
        )

    event_count = sum(
        len(section["lines"])
        for section in sections
    )

    if event_count == 0:
        return None

    return {
        "frequency": period.frequency,
        "period_key": period.period_key,
        "period_label": period.period_label,
        "audience": audience,
        "sections": sections,
        "event_count": event_count,
    }


def _claim_digest_run(
    database_session: Session,
    *,
    user_id: int,
    period: DigestPeriod,
) -> DigestRun | None:
    """Insert the run row that reserves this period for this user.

    The unique ``(user_id, frequency, period_key)`` index means a second
    scheduler firing for the same period loses the race and gets ``None``,
    so no digest is ever sent twice.
    """

    run = DigestRun(
        user_id=user_id,
        frequency=period.frequency,
        period_key=period.period_key,
        period_start=period.start_utc,
        period_end=period.end_utc,
        status=DIGEST_STATUS_SKIPPED_EMPTY,
        event_count=0,
    )

    database_session.add(run)

    try:
        database_session.commit()

    except IntegrityError:
        database_session.rollback()

        return None

    return run


def send_user_digest(
    database_session: Session,
    *,
    user_id: int,
    period: DigestPeriod,
    settings: Settings | None = None,
) -> str:
    """Build and deliver one user's digest for one period.

    Returns the recorded run status: ``delivered``, ``skipped_empty`` or
    ``failed``.
    """

    active_settings = settings or default_settings

    run = _claim_digest_run(
        database_session,
        user_id=user_id,
        period=period,
    )

    if run is None:
        logger.info(
            "digest.skipped_duplicate user_id=%s frequency=%s period=%s",
            user_id,
            period.frequency,
            period.period_key,
        )

        return "duplicate"

    payload = build_digest_payload(
        database_session,
        user_id=user_id,
        period=period,
    )

    if payload is None:
        logger.info(
            "digest.skipped_empty user_id=%s frequency=%s period=%s",
            user_id,
            period.frequency,
            period.period_key,
        )

        return DIGEST_STATUS_SKIPPED_EMPTY

    run.event_count = int(payload["event_count"])

    user = get_user_by_id(
        database_session,
        user_id,
    )

    if user is None or not (user.email or "").strip():
        run.status = DIGEST_STATUS_FAILED
        run.failure_reason = "No email address is available."

        database_session.commit()

        return DIGEST_STATUS_FAILED

    if not active_settings.is_email_configured:
        run.status = DIGEST_STATUS_FAILED
        run.failure_reason = "SMTP delivery is not configured."

        database_session.commit()

        return DIGEST_STATUS_FAILED

    content = render_digest_email(
        payload,
        settings=active_settings,
    )

    if payload["audience"] == "sme":
        attachments = _sme_report_attachments(
            database_session,
            user_id=user_id,
            settings=active_settings,
        )

        if attachments:
            content = replace(
                content,
                attachments=attachments,
            )

    try:
        send_email(
            recipient=user.email,
            content=content,
            settings=active_settings,
        )

    except (EmailNotConfiguredError, EmailDeliveryError) as error:
        run.status = DIGEST_STATUS_FAILED
        run.failure_reason = str(error)[:500]

        database_session.commit()

        logger.warning(
            "digest.delivery.failed user_id=%s reason=%s",
            user_id,
            error,
        )

        return DIGEST_STATUS_FAILED

    except Exception as error:  # noqa: BLE001 - never break the job
        run.status = DIGEST_STATUS_FAILED
        run.failure_reason = (
            f"Unexpected digest error: {type(error).__name__}"
        )

        database_session.commit()

        logger.exception(
            "digest.delivery.failed user_id=%s",
            user_id,
        )

        return DIGEST_STATUS_FAILED

    run.status = DIGEST_STATUS_DELIVERED

    database_session.commit()

    logger.info(
        "digest.delivered user_id=%s frequency=%s period=%s events=%s",
        user_id,
        period.frequency,
        period.period_key,
        run.event_count,
    )

    return DIGEST_STATUS_DELIVERED


def run_digest_cycle(
    database_session: Session,
    *,
    frequency: str,
    reference: datetime | None = None,
    settings: Settings | None = None,
) -> dict[str, int]:
    """Process every subscriber of one digest frequency."""

    active_settings = settings or default_settings

    if frequency not in {FREQUENCY_DAILY, FREQUENCY_WEEKLY}:
        raise ValueError(
            "frequency must be 'daily' or 'weekly'"
        )

    period = resolve_digest_period(
        frequency=frequency,
        reference=reference,
        settings=active_settings,
    )

    logger.info(
        "digest.cycle.started frequency=%s period=%s",
        frequency,
        period.period_key,
    )

    recipients = list_digest_recipients(
        database_session,
        frequency=frequency,
    )

    summary = {
        "candidates": len(recipients),
        "delivered": 0,
        "skipped_empty": 0,
        "duplicate": 0,
        "failed": 0,
    }

    for preference in recipients:
        try:
            status = send_user_digest(
                database_session,
                user_id=preference.user_id,
                period=period,
                settings=active_settings,
            )

        except Exception:  # noqa: BLE001 - one user must not stop the run
            database_session.rollback()

            logger.exception(
                "digest.user.failed user_id=%s",
                preference.user_id,
            )

            summary["failed"] += 1

            continue

        if status in summary:
            summary[status] += 1

    logger.info(
        (
            "digest.cycle.finished frequency=%s period=%s "
            "delivered=%s skipped_empty=%s duplicate=%s failed=%s"
        ),
        frequency,
        period.period_key,
        summary["delivered"],
        summary["skipped_empty"],
        summary["duplicate"],
        summary["failed"],
    )

    return summary
