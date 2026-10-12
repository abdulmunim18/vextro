"""Remove phone numbers from text the public wrote.

The crawler removes them before sending anything, and this is the second
check on arrival: a number a visitor typed into a comment box must never be
stored, whatever the crawler let through.
"""

from __future__ import annotations

import re


CONTACT_PLACEHOLDER = "[number removed]"

CONTACT_NUMBER = re.compile(
    # A mobile number however its digits are spaced or punctuated
    # ("0301.9294806", "0322_6604704", "0344/444/9964", "0332 - 2229442").
    r"(?:\+?92|(?<!\d)0)[\s._/-]{0,3}3(?:[\s._/-]{0,3}\d){9}"
    # Any other number written with a leading zero and one break.
    r"|(?<!\d)0\d{2,4}[\s._/-]{1,3}\d{6,9}(?!\d)"
    # A mobile number typed without its leading zero ("345 7281327").
    r"|(?<!\d)3\d{2}[\s.-]?\d{7}(?!\d)"
    # Any run of ten digits or more. Spaced-out figures such as
    # "8 128 5000 50" are specifications and are left alone.
    r"|\d{10,}"
)


def redact_contact_numbers(text: str) -> tuple[str, bool]:
    """Return ``(text, removed)`` with every phone number replaced."""

    cleaned, count = CONTACT_NUMBER.subn(CONTACT_PLACEHOLDER, text or "")

    return " ".join(cleaned.split()), count > 0


__all__ = ["CONTACT_PLACEHOLDER", "redact_contact_numbers"]
