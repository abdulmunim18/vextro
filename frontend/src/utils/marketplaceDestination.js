export function getMarketplaceDestination(
  listing,
  platformName,
) {
  const productUrl = listing.product_url?.trim();

  if (productUrl) {
    try {
      const parsedUrl = new URL(productUrl);
      const isHomepageOnly =
        parsedUrl.pathname.replaceAll("/", "") === "" &&
        !parsedUrl.search;

      if (!isHomepageOnly) {
        return {
          url: productUrl,
          isSearchFallback: false,
        };
      }
    } catch {
      // Fall through to a marketplace search URL.
    }
  }

  const normalizedPlatform = platformName.toLowerCase();
  const searchQuery = encodeURIComponent(listing.title);

  if (normalizedPlatform.includes("daraz")) {
    return {
      url: `https://www.daraz.pk/catalog/?q=${searchQuery}`,
      isSearchFallback: true,
    };
  }

  if (normalizedPlatform.includes("priceoye")) {
    return {
      url: `https://priceoye.pk/search?q=${searchQuery}`,
      isSearchFallback: true,
    };
  }

  return {
    url: productUrl || "#",
    isSearchFallback: !productUrl,
  };
}
