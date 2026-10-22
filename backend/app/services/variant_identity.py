"""A variant's identity as data, kept free of imports so models can use it.

Every category describes its variants with its own attributes (RAM and
storage, case size, connectivity). They are stored together under
``variant_attributes["identity"]`` and summarised in one string, the
``configuration_key``, which the database keeps unique per product, colour
and condition.
"""

from __future__ import annotations

IDENTITY = "identity"

# The two attributes that also have typed columns, from before categories.
MEMORY_COLUMNS = ("ram_gb", "storage_gb")


def configuration_key(attributes: dict[str, object]) -> str:
    """One stable string for a variant's identity attributes.

    Sorted by key so the order a source states them in never matters;
    ``{"storage_gb": 256, "ram_gb": 8}`` is ``ram_gb=8|storage_gb=256``. A
    product with no identity attributes (one model, colours only) has the
    empty key.
    """

    parts = []
    for key in sorted(attributes):
        value = attributes[key]
        if value is None or value == "":
            continue
        parts.append(f"{key}={str(value).strip().lower()}")

    return "|".join(parts)


def variant_identity(
    variant_attributes: dict[str, object] | None,
    *,
    ram_gb: int | None = None,
    storage_gb: int | None = None,
) -> dict[str, object]:
    """Return a variant's identity attributes, typed columns included.

    The RAM and storage columns are authoritative while they exist, so a
    variant created by older code that only filled the columns still gets
    the right identity.
    """

    stored = (variant_attributes or {}).get(IDENTITY)
    identity = {
        key: value
        for key, value in (stored.items() if isinstance(stored, dict) else ())
        if value is not None and value != ""
    }

    for key, value in (("ram_gb", ram_gb), ("storage_gb", storage_gb)):
        if value is not None:
            identity[key] = value
        else:
            identity.pop(key, None)

    return identity


__all__ = ["IDENTITY", "MEMORY_COLUMNS", "configuration_key", "variant_identity"]
