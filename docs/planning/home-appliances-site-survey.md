# Home appliances: site survey

Checked on 26 October 2026, before any appliance code was written. For each
store: whether robots.txt lets us read the catalogue, how the catalogue can be
read, how many products it has per appliance, and whether titles carry the
manufacturer's model code (the thing appliance matching will key on).

## Stores

| Store | How we read it | ACs | TVs | Fridges | Washing machines | Microwaves | Verdict |
|---|---|---|---|---|---|---|---|
| Friends Home (friendshome.pk) | Shopify `products.json` | ~495 | ~412 | ~468 | ~302 | ~113 | Use, creates products |
| Jalal Electronics (jalalelectronics.com) | Shopify `products.json` | 202 | 124 | 180 | 161 | 50 | Use, creates products |
| PriceOye | existing spider | 102 | 126 | 25 | none | none | Use, creates products |
| Shophive | existing spider | none | 180 | none | none | none | Use for TVs |
| Telemart (telemart.pk) | Shopify `products.json` | 75 | spread over several collections | 85 | 95 | 82 | Use, match-only |
| Daraz | existing spider | yes | yes | yes | yes | yes | Use, match-only |
| Al-Fatah (alfatah.pk) | Shopify `products.json` | none found | none found | ~48 | not checked | 46 | Later, fridges and microwaves only |
| Mega.pk | refuses non-browser requests (HTTP 500) | | | | | | Skip: anti-bot |
| iShopping | HTTP 403 | | | | | | Skip: anti-bot |
| HomeShopping | category URLs redirect to `/*` | | | | | | Skip for now |
| Orient (brand site) | robots.txt disallows everything | | | | | | Skip |
| Dawlance (brand site) | robots.txt returns 403 | | | | | | Skip |

Counts are the store's own collection sizes and include some accessories and
out-of-stock items. Shopify's collection size also counts products the store
has hidden, which the feed leaves out: the first live read gave Friends Home
126 ACs (not ~495) and Jalal 202. Friends Home's narrower AC collections
(by tonnage, by brand) held nothing its main AC collection did not.

## What the data looks like

Model codes are in every store's titles:

- Friends Home: `HAIER 1.5 TON T3 INVERTER AC Model HSU-19HFAB W`, `TCL 55 INCH SMART & 4K QD MINILED TV Model 55C6K`
- PriceOye: `Gree 1.5 Ton Fairy Series Split Inverter AC (GS18FITH1W)`, `TCL 49 Inch FHD Smart LED TV (L49S6500)`
- Jalal: `DAWLANCE REFRIGERATOR DMD-9060 INV INOX NO FROST,4 DOOR`
- Telemart: `Dawlance DWT-1775 PL 17Kg Top Load Fully Automatic Washing Machine with Official Warranty`
- Shophive: `TCL 55P635 55" UHD 4K Smart LED Android TV`

The same code is written differently from store to store (`GS-18FITH1 W`,
`GS18FITH1W`), so codes must be compared with spaces, hyphens and a trailing
colour letter removed.

Shopify feeds give price, availability, SKU and vendor in one JSON request of up
to 250 products. A whole collection takes one or two requests, far fewer than
walking HTML pages.

## Things to handle

- Telemart is a marketplace. Third-party sellers list unrelated goods in appliance
  collections (a Rs 1,070 "mini washing machine"), and sold-out items show Rs 0.
  It should only join products other stores already list.
- Jalal's vendor field is the store's name, not the brand, so the brand comes from the title.
- Jalal titles have typos such as `REFRIGERATORGR`.
- Accessories to turn away: AC stands, copper pipe kits, covers, TV wall mounts, remotes, TV boxes.
- Prices may or may not include installation, and warranty may be the brand's or the shop's.
- `ROBOTSTXT_OBEY` stays on. None of the Shopify stores disallow `products.json`
  or the collection pages; their `filter` and `sort_by` URLs are disallowed, and we don't use them.

## Recommended order

1. ACs: Friends Home, Jalal, PriceOye, plus Telemart and Daraz (match-only).
2. TVs: Friends Home, Jalal, PriceOye, Shophive, plus Telemart and Daraz (match-only).
3. Fridges and freezers: Friends Home, Jalal, PriceOye, plus Telemart and Daraz.
4. Washing machines: Friends Home, Jalal, plus Telemart and Daraz.
5. Microwaves: Friends Home, Jalal, plus Telemart, Al-Fatah and Daraz.
