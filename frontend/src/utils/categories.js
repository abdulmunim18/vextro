// Categories the filter never offers: the Electronics parent and the old
// "smartphones" slug, whose products live under mobile-phones.
export const HIDDEN_CATEGORY_SLUGS = new Set(["electronics", "smartphones"]);

// Shown categories in filter order: each one whose parent is shown sits
// under it (Air Conditioners under Home Appliances); the rest stand alone.
export function nestCategories(categories) {
  const shown = categories.filter(
    (category) => !HIDDEN_CATEGORY_SLUGS.has(category.slug),
  );
  const shownIds = new Set(shown.map((category) => category.id));

  return shown
    .filter((category) => !shownIds.has(category.parent_id))
    .flatMap((top) => [
      { category: top, nested: false },
      ...shown
        .filter((category) => category.parent_id === top.id)
        .map((category) => ({ category, nested: true })),
    ]);
}
