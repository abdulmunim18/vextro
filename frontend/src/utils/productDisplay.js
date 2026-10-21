export function toFiniteNumber(value) {
  const numericValue = Number(value);

  return Number.isFinite(numericValue)
    ? numericValue
    : null;
}

export function formatPrice(
  value,
  currency = "PKR",
) {
  const numericValue = toFiniteNumber(value);

  if (numericValue === null) {
    return "Price unavailable";
  }

  try {
    return new Intl.NumberFormat("en-PK", {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(numericValue);
  } catch {
    return `${currency} ${numericValue.toLocaleString(
      "en-PK",
    )}`;
  }
}

export function formatCompactPrice(value) {
  const numericValue = toFiniteNumber(value);

  if (numericValue === null) {
    return "";
  }

  return new Intl.NumberFormat("en-PK", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(numericValue);
}

export function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-PK", {
    dateStyle: "medium",
  }).format(date);
}

export function formatDateTime(value) {
  if (!value) {
    return "Not available";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-PK", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function formatAttributeLabel(value) {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    );
}
// The warranty exactly as the marketplace states it for this offer
// ("1 Year Warranty", "No Warranty", "Check at Delivery"), read from the
// listing's stored `warranty`. Daraz states one for few of its offers.
export const WARRANTY_NOT_STATED = "Not stated";

export function formatWarranty(listing) {
  const warranty = String(listing?.warranty ?? "").trim();

  return warranty || WARRANTY_NOT_STATED;
}
