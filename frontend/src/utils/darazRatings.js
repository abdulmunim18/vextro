// Daraz shows the text of its reviews only on its own site, and its review
// service may not be crawled. What it does publish with every offer is the
// offer's star rating and how many buyers rated it. This turns those into
// one figure per seller and their overall, weighted by number of reviews.
export function summariseDarazRatings(listings) {
  const bySeller = new Map();

  listings.forEach((listing) => {
    const count = Number(listing.review_count) || 0;
    const rating = Number(listing.rating) || 0;
    const key = listing.seller?.id ?? `listing-${listing.id}`;
    const seller = bySeller.get(key) ?? {
      key,
      name: listing.seller?.name || "Daraz seller",
      verified: Boolean(listing.seller?.is_verified),
      count: 0,
      weighted: 0,
      inStock: false,
      url: null,
      topCount: -1,
    };

    if (count > 0 && rating > 0) {
      seller.count += count;
      seller.weighted += rating * count;
    }
    seller.inStock = seller.inStock || Boolean(listing.is_available);
    if (listing.product_url && count > seller.topCount) {
      seller.topCount = count;
      seller.url = listing.product_url;
    }
    bySeller.set(key, seller);
  });

  const sellers = [...bySeller.values()]
    .map((seller) => ({
      ...seller,
      rating: seller.count > 0 ? seller.weighted / seller.count : null,
    }))
    .sort(
      (first, second) =>
        second.count - first.count ||
        Number(second.inStock) - Number(first.inStock),
    );

  const count = sellers.reduce((sum, seller) => sum + seller.count, 0);
  const rating =
    count > 0
      ? sellers.reduce((sum, seller) => sum + seller.weighted, 0) / count
      : null;
  const mostReviewed = sellers.find((seller) => seller.url) ?? null;

  return {
    count,
    rating,
    sellers,
    ratedSellers: sellers.filter((seller) => seller.count > 0).length,
    url: mostReviewed?.url ?? null,
  };
}
