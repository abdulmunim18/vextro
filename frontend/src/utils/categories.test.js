import { describe, expect, it } from "vitest";

import { nestCategories } from "./categories";

const categories = [
  { id: 1, parent_id: null, slug: "electronics", name: "Electronics" },
  { id: 2, parent_id: 1, slug: "mobile-phones", name: "Mobile Phones" },
  { id: 3, parent_id: 1, slug: "laptops", name: "Laptops" },
  { id: 4, parent_id: null, slug: "home-appliances", name: "Home Appliances" },
  { id: 5, parent_id: 4, slug: "air-conditioners", name: "Air Conditioners" },
  { id: 6, parent_id: 4, slug: "televisions", name: "Televisions" },
  { id: 7, parent_id: null, slug: "smartphones", name: "Smartphones" },
];

const listed = (entries) =>
  entries.map(({ category, nested }) => `${nested ? "  " : ""}${category.slug}`);

describe("nestCategories", () => {
  it("puts each appliance under Home Appliances", () => {
    expect(listed(nestCategories(categories))).toEqual([
      "mobile-phones",
      "laptops",
      "home-appliances",
      "  air-conditioners",
      "  televisions",
    ]);
  });

  it("never offers the Electronics parent or the old smartphones slug", () => {
    const slugs = nestCategories(categories).map(({ category }) => category.slug);

    expect(slugs).not.toContain("electronics");
    expect(slugs).not.toContain("smartphones");
  });
});
