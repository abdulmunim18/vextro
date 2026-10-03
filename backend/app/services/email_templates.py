"""Responsive HTML email templates with plain-text fallbacks.

Every template renders from a plain ``payload`` dictionary stored on a
``notification_events`` row, so a retried delivery renders exactly the
same message without re-reading business tables.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

from app.core.config import Settings, settings as default_settings
from app.services.email_service import EmailContent


BRAND_PRIMARY = "#1D4ED8"
BRAND_INK = "#0F172A"
BRAND_MUTED = "#64748B"
BRAND_BORDER = "#E2E8F0"
BRAND_CANVAS = "#F8FAFC"


def _safe_action_url(
    action_path: str | None,
    *,
    settings: Settings,
) -> str:
    """Build an absolute frontend URL from a relative in-app path.

    Only same-origin relative paths are accepted, which prevents an open
    redirect through a crafted ``action_path``.
    """

    base_url = settings.frontend_base_url_normalized

    if not action_path:
        return base_url or ""

    if not action_path.startswith("/") or action_path.startswith("//"):
        return base_url or ""

    return f"{base_url}{action_path}"


def _format_money(
    amount: Any,
    currency: str,
) -> str:
    """Render a currency amount with thousands separators."""

    try:
        return f"{currency} {float(amount):,.2f}"
    except (TypeError, ValueError):
        return f"{currency} {amount}"


def _format_timestamp(value: Any) -> str:
    """Render an ISO timestamp for human reading."""

    if not value:
        return ""

    if isinstance(value, datetime):
        moment = value
    else:
        try:
            moment = datetime.fromisoformat(str(value))
        except ValueError:
            return str(value)

    return moment.strftime("%d %b %Y, %H:%M %Z").strip()


def _document(
    *,
    heading: str,
    intro: str,
    rows_html: str,
    cta_label: str | None,
    cta_url: str,
    footer_note: str,
) -> str:
    """Wrap rendered content in the shared responsive email shell."""

    cta_html = ""

    if cta_label and cta_url:
        cta_html = f"""
              <tr>
                <td style="padding:8px 28px 28px 28px;">
                  <a href="{escape(cta_url, quote=True)}"
                     style="display:inline-block;background:{BRAND_PRIMARY};
                            color:#FFFFFF;font-weight:700;font-size:14px;
                            text-decoration:none;padding:13px 22px;
                            border-radius:10px;">
                    {escape(cta_label)}
                  </a>
                </td>
              </tr>"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{escape(heading)}</title>
</head>
<body style="margin:0;padding:0;background:{BRAND_CANVAS};
             font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',
             Roboto,Helvetica,Arial,sans-serif;color:{BRAND_INK};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="background:{BRAND_CANVAS};padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellpadding="0"
               cellspacing="0"
               style="max-width:600px;background:#FFFFFF;
                      border:1px solid {BRAND_BORDER};border-radius:16px;
                      overflow:hidden;">
          <tr>
            <td style="background:{BRAND_PRIMARY};padding:20px 28px;">
              <span style="color:#FFFFFF;font-size:18px;font-weight:800;
                           letter-spacing:0.5px;">VEXTRO</span>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 28px 8px 28px;">
              <h1 style="margin:0;font-size:20px;line-height:28px;
                         font-weight:800;color:{BRAND_INK};">
                {escape(heading)}
              </h1>
              <p style="margin:10px 0 0 0;font-size:14px;line-height:22px;
                        color:{BRAND_MUTED};">
                {escape(intro)}
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:18px 28px 4px 28px;">
              <table role="presentation" width="100%" cellpadding="0"
                     cellspacing="0" style="font-size:14px;">
                {rows_html}
              </table>
            </td>
          </tr>{cta_html}
          <tr>
            <td style="background:{BRAND_CANVAS};padding:18px 28px;
                       border-top:1px solid {BRAND_BORDER};">
              <p style="margin:0;font-size:12px;line-height:18px;
                        color:{BRAND_MUTED};">
                {escape(footer_note)}
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _detail_rows(
    pairs: list[tuple[str, str]],
) -> str:
    """Render label/value detail rows."""

    cells = []

    for label, value in pairs:
        if not value:
            continue

        cells.append(
            f"""
                <tr>
                  <td style="padding:7px 0;color:{BRAND_MUTED};
                             font-size:13px;width:45%;">
                    {escape(label)}
                  </td>
                  <td style="padding:7px 0;color:{BRAND_INK};
                             font-size:14px;font-weight:700;"
                      align="right">
                    {escape(value)}
                  </td>
                </tr>"""
        )

    return "".join(cells)


def _text_block(
    *,
    heading: str,
    intro: str,
    pairs: list[tuple[str, str]],
    cta_url: str,
    footer_note: str,
) -> str:
    """Render the plain-text fallback body."""

    lines = [heading, "", intro, ""]

    for label, value in pairs:
        if value:
            lines.append(f"{label}: {value}")

    if cta_url:
        lines.extend(["", f"Open in VEXTRO: {cta_url}"])

    lines.extend(["", footer_note])

    return "\n".join(lines)


PREFERENCES_NOTE = (
    "You are receiving this because email notifications are enabled "
    "for your VEXTRO account. Manage channels under "
    "Dashboard - Notification settings."
)


def render_price_drop_email(
    payload: dict[str, Any],
    *,
    action_path: str | None = None,
    settings: Settings | None = None,
) -> EmailContent:
    """Render the consumer price-alert email."""

    active_settings = settings or default_settings

    product_name = str(payload.get("product_name") or "Your tracked product")
    currency = str(payload.get("currency") or "PKR")

    current_price = _format_money(
        payload.get("current_price"),
        currency,
    )
    target_price = _format_money(
        payload.get("target_price"),
        currency,
    )

    savings_text = ""
    savings = payload.get("savings")

    if savings is not None:
        try:
            if float(savings) > 0:
                savings_text = _format_money(savings, currency)
        except (TypeError, ValueError):
            savings_text = ""

    pairs = [
        ("Product", product_name),
        ("Current price", current_price),
        ("Your target price", target_price),
        ("Below target by", savings_text),
        ("Marketplace", str(payload.get("marketplace") or "")),
        ("Observed at", _format_timestamp(payload.get("observed_at"))),
    ]

    cta_url = _safe_action_url(
        action_path,
        settings=active_settings,
    )

    heading = f"{product_name} reached your target price"
    intro = (
        "A marketplace price we monitor for you has dropped to or "
        "below the target you set."
    )

    return EmailContent(
        subject=(
            f"Price Alert: {product_name} reached your target"
        ),
        html_body=_document(
            heading=heading,
            intro=intro,
            rows_html=_detail_rows(pairs),
            cta_label="View product on VEXTRO",
            cta_url=cta_url,
            footer_note=PREFERENCES_NOTE,
        ),
        text_body=_text_block(
            heading=heading,
            intro=intro,
            pairs=pairs,
            cta_url=cta_url,
            footer_note=PREFERENCES_NOTE,
        ),
    )


def render_competitor_risk_email(
    payload: dict[str, Any],
    *,
    action_path: str | None = None,
    settings: Settings | None = None,
) -> EmailContent:
    """Render the SME competitor-risk email."""

    active_settings = settings or default_settings

    product_name = str(payload.get("product_name") or "Your product")
    currency = str(payload.get("currency") or "PKR")

    pairs = [
        ("Your product", product_name),
        (
            "Your selling price",
            _format_money(payload.get("own_price"), currency),
        ),
        (
            "Competitor price",
            _format_money(payload.get("competitor_price"), currency),
        ),
        (
            "Price gap",
            (
                f"{payload.get('price_gap_percentage')}%"
                if payload.get("price_gap_percentage") is not None
                else ""
            ),
        ),
        ("Risk level", str(payload.get("risk_level") or "").upper()),
        ("Competitor marketplace", str(payload.get("marketplace") or "")),
        ("Detected at", _format_timestamp(payload.get("observed_at"))),
    ]

    cta_url = _safe_action_url(
        action_path,
        settings=active_settings,
    )

    heading = f"Competitor price risk on {product_name}"
    intro = (
        "A monitored competitor listing moved far enough below your "
        "price to put your position at risk."
    )

    return EmailContent(
        subject=(
            f"Competitor Alert: {product_name} pricing position at risk"
        ),
        html_body=_document(
            heading=heading,
            intro=intro,
            rows_html=_detail_rows(pairs),
            cta_label="Open competitor intelligence",
            cta_url=cta_url,
            footer_note=PREFERENCES_NOTE,
        ),
        text_body=_text_block(
            heading=heading,
            intro=intro,
            pairs=pairs,
            cta_url=cta_url,
            footer_note=PREFERENCES_NOTE,
        ),
    )


def _digest_section_html(
    title: str,
    lines: list[str],
) -> str:
    """Render one digest section as a table row group."""

    if not lines:
        return ""

    items = "".join(
        f"""
                      <li style="margin:0 0 6px 0;line-height:21px;">
                        {escape(line)}
                      </li>"""
        for line in lines
    )

    return f"""
                <tr>
                  <td style="padding:14px 0 4px 0;">
                    <h2 style="margin:0 0 8px 0;font-size:14px;
                               font-weight:800;color:{BRAND_INK};
                               text-transform:uppercase;
                               letter-spacing:0.6px;">
                      {escape(title)}
                    </h2>
                    <ul style="margin:0;padding-left:18px;font-size:13px;
                               color:{BRAND_MUTED};">{items}
                    </ul>
                  </td>
                </tr>"""


def render_digest_email(
    payload: dict[str, Any],
    *,
    settings: Settings | None = None,
) -> EmailContent:
    """Render a daily or weekly digest email."""

    active_settings = settings or default_settings

    frequency = str(payload.get("frequency") or "daily")
    period_label = str(payload.get("period_label") or "")
    audience = str(payload.get("audience") or "consumer")

    sections: list[tuple[str, list[str]]] = [
        (
            str(section.get("title") or ""),
            [str(line) for line in section.get("lines") or []],
        )
        for section in payload.get("sections") or []
    ]

    heading = (
        "Your VEXTRO "
        f"{'weekly' if frequency == 'weekly' else 'daily'} digest"
    )
    intro = (
        f"Activity for {period_label}."
        if period_label
        else "Recent activity on your VEXTRO account."
    )

    cta_path = "/sme" if audience == "sme" else "/alerts"

    cta_url = _safe_action_url(
        cta_path,
        settings=active_settings,
    )

    rows_html = "".join(
        _digest_section_html(title, lines)
        for title, lines in sections
        if title and lines
    )

    text_pairs: list[tuple[str, str]] = []

    for title, lines in sections:
        for line in lines:
            text_pairs.append((title, line))

    return EmailContent(
        subject=(
            "VEXTRO "
            f"{'Weekly' if frequency == 'weekly' else 'Daily'} Digest"
            f"{f' - {period_label}' if period_label else ''}"
        ),
        html_body=_document(
            heading=heading,
            intro=intro,
            rows_html=rows_html,
            cta_label="Open VEXTRO",
            cta_url=cta_url,
            footer_note=(
                "You are receiving this because digest reports are "
                "enabled for your VEXTRO account. Change the frequency "
                "or turn digests off under Dashboard - Notification "
                "settings."
            ),
        ),
        text_body=_text_block(
            heading=heading,
            intro=intro,
            pairs=text_pairs,
            cta_url=cta_url,
            footer_note=(
                "Change the frequency or turn digests off under "
                "Dashboard - Notification settings."
            ),
        ),
    )
