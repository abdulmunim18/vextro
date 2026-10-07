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
// Product decision: every offer is presented with a one-year warranty.
// This is a fixed label, not the scraped value. What each marketplace
// actually states ("No Warranty", "2 Years Warranty", or nothing) is still
// collected and stored on the listing as `warranty`; returning
// `listing.warranty` here instead restores the real figure.
export const DISPLAYED_WARRANTY = "1 Year Warranty";

export function formatWarranty() {
  return DISPLAYED_WARRANTY;
}
