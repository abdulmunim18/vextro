// What tells two variants of one product apart. A phone differs in RAM and
// storage; a tablet also in Wi-Fi or cellular and screen size; a watch in
// case size. The backend records the full set in
// variant_attributes.identity; RAM and storage also have columns of their
// own, which win.

// Bookkeeping the backend keeps beside a variant. None of it describes the
// product, so none of it belongs in a specification table.
const INTERNAL_ATTRIBUTES = new Set([
  "identity",
  "named_by",
  "source_platform",
  "source_external_id",
]);

const CONNECTIVITY_LABELS = {
  wifi: "Wi-Fi",
  cellular: "Wi-Fi + Cellular",
};

export function isInternalVariantAttribute(key) {
  return INTERNAL_ATTRIBUTES.has(key);
}

export function formatCapacity(gigabytes) {
  return gigabytes >= 1024 && gigabytes % 1024 === 0
    ? `${gigabytes / 1024}TB`
    : `${gigabytes}GB`;
}

// [{ key, label, value }] for each attribute the variant states, in the
// order a shopper reads them: size and connectivity, then memory.
export function variantIdentityDetails(variant) {
  if (!variant) {
    return [];
  }

  const identity = variant.variant_attributes?.identity || {};
  const ramGb = variant.ram_gb ?? identity.ram_gb;
  const storageGb = variant.storage_gb ?? identity.storage_gb;
  const details = [];

  if (identity.screen_in) {
    details.push({
      key: "screen_in",
      label: "Screen",
      value: `${identity.screen_in}″`,
    });
  }

  if (identity.case_size_mm) {
    details.push({
      key: "case_size_mm",
      label: "Case size",
      value: `${identity.case_size_mm} mm`,
    });
  }

  if (identity.connectivity) {
    details.push({
      key: "connectivity",
      label: "Connectivity",
      value:
        CONNECTIVITY_LABELS[identity.connectivity] ||
        identity.connectivity,
    });
  }

  if (storageGb) {
    details.push({
      key: "storage_gb",
      label: "Storage",
      value: formatCapacity(storageGb),
    });
  }

  if (ramGb) {
    details.push({
      key: "ram_gb",
      label: "RAM",
      value: `${ramGb}GB`,
    });
  }

  return details;
}

// Short chip text: "11″ screen", "Wi-Fi", "256GB storage", "8GB RAM".
export function variantIdentityChips(variant) {
  return variantIdentityDetails(variant).map(({ key, value }) => {
    if (key === "screen_in") {
      return `${value} screen`;
    }
    if (key === "storage_gb") {
      return `${value} storage`;
    }
    if (key === "ram_gb") {
      return `${value} RAM`;
    }
    return value;
  });
}
