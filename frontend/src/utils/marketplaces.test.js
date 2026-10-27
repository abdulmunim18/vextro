import { describe, expect, it } from "vitest";

import { getMarketplaceDestination } from "./marketplaceDestination";
import { isMarketplace, sellsCategory } from "./marketplaces";

const store = (code) => ({ code });

describe("marketplaces", () => {
  it("compares the appliance stores alongside the electronics stores", () => {
    for (const code of ["daraz", "priceoye", "shophive", "friendshome", "jalal", "telemart"]) {
      expect(isMarketplace(store(code))).toBe(true);
    }
    expect(isMarketplace(store("whatmobile"))).toBe(false);
  });

  it("shows a phone page only the stores that sell phones", () => {
    expect(sellsCategory(store("priceoye"), "mobile-phones")).toBe(true);
    expect(sellsCategory(store("friendshome"), "mobile-phones")).toBe(false);
    expect(sellsCategory(store("telemart"), "laptops")).toBe(false);
  });

  it("shows an AC page the stores that sell ACs, and not Shophive", () => {
    expect(sellsCategory(store("friendshome"), "air-conditioners")).toBe(true);
    expect(sellsCategory(store("jalal"), "air-conditioners")).toBe(true);
    expect(sellsCategory(store("priceoye"), "air-conditioners")).toBe(true);
    expect(sellsCategory(store("shophive"), "air-conditioners")).toBe(false);
  });

  it("shows a TV page every store", () => {
    for (const code of ["daraz", "priceoye", "shophive", "friendshome", "jalal", "telemart"]) {
      expect(sellsCategory(store(code), "televisions")).toBe(true);
    }
  });
});

describe("marketplace destinations", () => {
  it("searches a Shopify store when a listing has no page of its own", () => {
    const listing = { product_url: "", title: "Haier HSU-19HFAB" };

    expect(getMarketplaceDestination(listing, "Friends Home")).toEqual({
      url: "https://friendshome.pk/search?q=Haier%20HSU-19HFAB",
      isSearchFallback: true,
    });
    expect(getMarketplaceDestination(listing, "Jalal Electronics").url).toBe(
      "https://jalalelectronics.com/search?q=Haier%20HSU-19HFAB",
    );
  });

  it("opens the product page when there is one", () => {
    const listing = {
      product_url: "https://telemart.pk/products/haier-ac",
      title: "Haier AC",
    };

    expect(getMarketplaceDestination(listing, "Telemart")).toEqual({
      url: "https://telemart.pk/products/haier-ac",
      isSearchFallback: false,
    });
  });
});
