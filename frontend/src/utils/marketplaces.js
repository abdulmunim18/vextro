// The marketplaces VEXTRO compares offers across, by their platform code.
// A product page shows each one that sells the product's kind of goods,
// including the ones that do not list this product.
const ELECTRONICS_STORES = ["daraz", "priceoye", "shophive"];
const APPLIANCE_STORES = ["friendshome", "jalal", "telemart"];

export const MARKETPLACE_CODES = [...ELECTRONICS_STORES, ...APPLIANCE_STORES];

// The marketplaces that sell each category; a category not named here is
// sold by the electronics stores.
const CATEGORY_MARKETPLACES = {
  "air-conditioners": ["daraz", "priceoye", ...APPLIANCE_STORES],
  televisions: [...ELECTRONICS_STORES, ...APPLIANCE_STORES],
  refrigerators: ["daraz", "priceoye", ...APPLIANCE_STORES],
  "washing-machines": ["daraz", ...APPLIANCE_STORES],
  "microwave-ovens": ["daraz", ...APPLIANCE_STORES],
};

export function isMarketplace(platform) {
  return MARKETPLACE_CODES.includes(platform?.code?.toLowerCase());
}

export function sellsCategory(platform, categorySlug) {
  const code = platform?.code?.toLowerCase();
  const sellers = CATEGORY_MARKETPLACES[categorySlug] ?? ELECTRONICS_STORES;

  return sellers.includes(code);
}
