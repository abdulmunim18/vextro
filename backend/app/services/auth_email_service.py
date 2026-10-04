from html import escape

from app.services.email_service import EmailContent, send_email


def send_verification_otp_email(
    *,
    recipient: str,
    full_name: str,
    otp: str,
    expires_minutes: int,
) -> None:
    """Send the one-time code that completes account creation."""

    safe_name = escape(full_name)
    safe_otp = escape(otp)
    send_email(
        recipient=recipient,
        content=EmailContent(
            subject="Verify your VEXTRO email",
            text_body=(
                f"Hi {full_name},\n\nYour VEXTRO verification code is "
                f"{otp}. It expires in {expires_minutes} minutes.\n\n"
                "If you did not request this account, ignore this email."
            ),
            html_body=(
                f"<p>Hi {safe_name},</p>"
                "<p>Use this code to finish creating your VEXTRO account:</p>"
                f"<p style=\"font-size:32px;font-weight:800;letter-spacing:8px\">{safe_otp}</p>"
                f"<p>This code expires in {expires_minutes} minutes.</p>"
                "<p>If you did not request this account, ignore this email.</p>"
            ),
        ),
    )


def send_password_reset_email(
    *,
    recipient: str,
    full_name: str,
    reset_url: str,
    expires_minutes: int,
) -> None:
    """Send a single-use password reset link."""

    safe_name = escape(full_name)
    safe_url = escape(reset_url, quote=True)
    send_email(
        recipient=recipient,
        content=EmailContent(
            subject="Reset your VEXTRO password",
            text_body=(
                f"Hi {full_name},\n\nReset your VEXTRO password using this link:\n"
                f"{reset_url}\n\nThe link expires in {expires_minutes} minutes. "
                "If you did not request it, ignore this email."
            ),
            html_body=(
                f"<p>Hi {safe_name},</p>"
                "<p>You requested a VEXTRO password reset.</p>"
                f"<p><a href=\"{safe_url}\" style=\"display:inline-block;padding:12px 20px;"
                "background:#2563eb;color:#fff;text-decoration:none;border-radius:8px\">"
                "Reset password</a></p>"
                f"<p>This single-use link expires in {expires_minutes} minutes.</p>"
                "<p>If you did not request it, ignore this email.</p>"
            ),
        ),
    )
