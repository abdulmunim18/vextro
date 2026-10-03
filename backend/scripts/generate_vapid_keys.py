"""Print a fresh VAPID key pair for Web Push configuration.

    python -m scripts.generate_vapid_keys

The output is printed to the terminal only. Nothing is written to disk and
nothing is committed: copy the values into your own ``.env`` file, keep
``VAPID_PRIVATE_KEY`` secret, and expose only ``VAPID_PUBLIC_KEY`` to the
frontend.
"""

from __future__ import annotations

import base64
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _urlsafe_b64(raw: bytes) -> str:
    """Encode bytes the way the Web Push specification expects."""

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def main() -> int:
    """Generate and print one P-256 application server key pair."""

    private_key = ec.generate_private_key(ec.SECP256R1())

    private_value = private_key.private_numbers().private_value

    private_bytes = private_value.to_bytes(32, byteorder="big")

    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )

    print("# Add these to backend/.env - never commit the private key.")
    print(f"VAPID_PUBLIC_KEY={_urlsafe_b64(public_bytes)}")
    print(f"VAPID_PRIVATE_KEY={_urlsafe_b64(private_bytes)}")
    print("VAPID_SUBJECT=mailto:you@example.com")
    print()
    print(
        "# Expose only the public key to the frontend, for example as\n"
        "# VITE_VAPID_PUBLIC_KEY in frontend/.env. The backend also "
        "serves it\n"
        "# through GET /api/v1/notifications/preferences."
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
