import re


def derive_full_name_from_email(email: str) -> str:
    """Build a safe display name from the local part of an email address."""

    local_part = email.strip().split("@", 1)[0].split("+", 1)[0]
    readable_name = re.sub(r"[._-]+", " ", local_part)
    readable_name = re.sub(r"(?<=\D)(?=\d)", " ", readable_name)
    readable_name = " ".join(readable_name.split()).strip().title()

    if len(readable_name) < 2:
        return "VEXTRO User"

    return readable_name[:120]
