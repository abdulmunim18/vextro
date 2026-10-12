// The marketplaces VEXTRO compares offers across, by their platform code.
// A product page shows each of them, including the ones that do not list
// the phone, so adding a marketplace here adds it to that page.
export const MARKETPLACE_CODES = ["daraz", "priceoye", "shophive"];

export function isMarketplace(platform) {
  return MARKETPLACE_CODES.includes(platform?.code?.toLowerCase());
}
