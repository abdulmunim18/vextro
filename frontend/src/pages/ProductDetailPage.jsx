import {
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Link,
  useParams,
} from "react-router-dom";

import MarketplaceListingCard from "../components/MarketplaceListingCard";
import PriceHistoryPanel from "../components/PriceHistoryPanel";
import RouteLoadingState from "../components/RouteLoadingState";
import {
  getBrands,
  getCategories,
  getPlatforms,
  getProductById,
  getProductListings,
  getProductPriceHistory,
} from "../services/catalogService";
import { getApiErrorMessage } from "../utils/apiError";

function extractItems(responseData) {
  if (Array.isArray(responseData)) {
    return responseData;
  }

  if (Array.isArray(responseData?.items)) {
    return responseData.items;
  }

  return [];
}

function formatSpecificationValue(value) {
  if (value === null || value === undefined) {
    return "Not specified";
  }

  if (typeof value === "boolean") {
    return value ? "Yes" : "No";
  }

  if (Array.isArray(value)) {
    return value.join(", ");
  }

  if (typeof value === "object") {
    return Object.entries(value)
      .map(([key, itemValue]) => `${key}: ${itemValue}`)
      .join(", ");
  }

  return String(value);
}

function formatSpecificationLabel(key) {
  return key
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) =>
      character.toUpperCase(),
    );
}

function getPrimaryImage(product) {
  const images = Array.isArray(product?.images)
    ? product.images
    : [];

  return (
    images.find((image) => image.is_primary) ||
    images[0] ||
    null
  );
}

function ProductDetailPage() {
  const { productId } = useParams();

  const [product, setProduct] = useState(null);
  const [listings, setListings] = useState([]);
  const [priceHistory, setPriceHistory] =
    useState(null);

  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);
  const [platforms, setPlatforms] = useState([]);

  const [selectedImage, setSelectedImage] =
    useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] =
    useState("");

  const [sectionWarnings, setSectionWarnings] =
    useState([]);

  useEffect(() => {
    let isMounted = true;

    async function loadProductPage() {
      setIsLoading(true);
      setErrorMessage("");
      setSectionWarnings([]);

      const numericProductId = Number(productId);

      if (
        !Number.isInteger(numericProductId) ||
        numericProductId < 1
      ) {
        setErrorMessage("Invalid product identifier.");
        setIsLoading(false);
        return;
      }

      const results = await Promise.allSettled([
        getProductById(numericProductId),
        getProductListings(numericProductId),
        getProductPriceHistory(numericProductId),
        getCategories(),
        getBrands(),
        getPlatforms(),
      ]);

      if (!isMounted) {
        return;
      }

      const [
        productResult,
        listingsResult,
        historyResult,
        categoriesResult,
        brandsResult,
        platformsResult,
      ] = results;

      if (productResult.status === "rejected") {
        setErrorMessage(
          getApiErrorMessage(
            productResult.reason,
            "Unable to load this product.",
          ),
        );

        setIsLoading(false);
        return;
      }

      const loadedProduct = productResult.value;

      setProduct(loadedProduct);

      const primaryImage =
        getPrimaryImage(loadedProduct);

      setSelectedImage(primaryImage?.image_url || "");

      const warnings = [];

      if (listingsResult.status === "fulfilled") {
        setListings(
          extractItems(listingsResult.value),
        );
      } else {
        setListings([]);
        warnings.push(
          "Marketplace listings are temporarily unavailable.",
        );
      }

      if (historyResult.status === "fulfilled") {
        setPriceHistory(historyResult.value);
      } else {
        setPriceHistory({
          product_id: numericProductId,
          product_name: loadedProduct.name,
          total_listings: 0,
          total_points: 0,
          listings: [],
        });

        warnings.push(
          "Historical price data is temporarily unavailable.",
        );
      }

      if (categoriesResult.status === "fulfilled") {
        setCategories(
          extractItems(categoriesResult.value),
        );
      }

      if (brandsResult.status === "fulfilled") {
        setBrands(extractItems(brandsResult.value));
      }

      if (platformsResult.status === "fulfilled") {
        setPlatforms(
          extractItems(platformsResult.value),
        );
      }

      setSectionWarnings(warnings);
      setIsLoading(false);
    }

    loadProductPage();

    return () => {
      isMounted = false;
    };
  }, [productId]);

  const category = categories.find(
    (item) => item.id === product?.category_id,
  );

  const brand = brands.find(
    (item) => item.id === product?.brand_id,
  );

  const platformById = useMemo(
    () =>
      Object.fromEntries(
        platforms.map((platform) => [
          platform.id,
          platform,
        ]),
      ),
    [platforms],
  );

  const sortedListings = useMemo(
    () =>
      [...listings].sort(
        (firstListing, secondListing) =>
          Number(firstListing.current_price) -
          Number(secondListing.current_price),
      ),
    [listings],
  );

  const lowestListingId =
    sortedListings.find(
      (listing) =>
        listing.is_available &&
        Number.isFinite(
          Number(listing.current_price),
        ),
    )?.id ?? null;

  const specifications = Object.entries(
    product?.specifications || {},
  );

  const images = Array.isArray(product?.images)
    ? [...product.images].sort(
        (firstImage, secondImage) =>
          firstImage.sort_order -
          secondImage.sort_order,
      )
    : [];

  const variants = Array.isArray(product?.variants)
    ? product.variants
    : [];

  if (isLoading) {
    return (
      <RouteLoadingState message="Loading product intelligence..." />
    );
  }

  if (errorMessage || !product) {
    return (
      <section className="grid min-h-[calc(100vh-145px)] place-items-center bg-vextro-canvas px-4 py-16">
        <div className="w-full max-w-xl rounded-3xl border border-red-200 bg-white p-8 text-center shadow-vextro">
          <span className="mx-auto grid size-16 place-items-center rounded-2xl bg-red-50 text-3xl">
            !
          </span>

          <h1 className="mt-6 text-3xl font-black text-vextro-ink">
            Product could not be loaded
          </h1>

          <p className="mt-4 text-sm leading-7 text-vextro-muted">
            {errorMessage}
          </p>

          <Link
            className="mt-7 inline-flex min-h-12 items-center justify-center rounded-xl bg-vextro-primary px-6 text-sm font-black text-white"
            to="/products"
          >
            Return to Products
          </Link>
        </div>
      </section>
    );
  }

  return (
    <div className="bg-vextro-canvas">
      <section className="border-b border-vextro-border bg-white">
        <div className="mx-auto max-w-7xl px-4 py-5 sm:px-6 lg:px-8">
          <nav className="flex flex-wrap items-center gap-2 text-xs font-semibold text-vextro-muted">
            <Link
              className="transition hover:text-vextro-primary"
              to="/"
            >
              Home
            </Link>

            <span>/</span>

            <Link
              className="transition hover:text-vextro-primary"
              to="/products"
            >
              Products
            </Link>

            <span>/</span>

            <span className="text-vextro-ink">
              {product.name}
            </span>
          </nav>
        </div>
      </section>

      <section className="relative overflow-hidden py-14 sm:py-18">
        <div className="pointer-events-none absolute -right-40 top-0 size-96 rounded-full bg-blue-300/15 blur-3xl" />

        <div className="relative mx-auto grid max-w-7xl gap-10 px-4 sm:px-6 lg:grid-cols-[0.88fr_1.12fr] lg:px-8">
          <div>
            <div className="grid min-h-[480px] place-items-center overflow-hidden rounded-3xl border border-vextro-border bg-white p-7 shadow-sm">
              {selectedImage ? (
                <img
                  className="max-h-[430px] w-full object-contain"
                  src={selectedImage}
                  alt={product.name}
                />
              ) : (
                <div className="flex flex-col items-center gap-4 text-center">
                  <span className="grid size-24 place-items-center rounded-3xl bg-gradient-to-br from-vextro-primary to-violet-600 text-4xl font-black text-white shadow-vextro">
                    {product.name.charAt(0)}
                  </span>

                  <p className="text-sm font-semibold text-vextro-muted">
                    Product image unavailable
                  </p>
                </div>
              )}
            </div>

            {images.length > 1 ? (
              <div className="mt-4 grid grid-cols-4 gap-3 sm:grid-cols-5">
                {images.map((image) => (
                  <button
                    className={`grid h-20 place-items-center overflow-hidden rounded-xl bg-white p-2 transition ${
                      selectedImage === image.image_url
                        ? "border-2 border-vextro-primary"
                        : "border border-vextro-border hover:border-blue-300"
                    }`}
                    type="button"
                    key={image.id}
                    onClick={() =>
                      setSelectedImage(image.image_url)
                    }
                  >
                    <img
                      className="h-full w-full object-contain"
                      src={image.image_url}
                      alt={
                        image.alt_text ||
                        product.name
                      }
                    />
                  </button>
                ))}
              </div>
            ) : null}
          </div>

          <div className="flex flex-col justify-center">
            <div className="flex flex-wrap gap-2">
              <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[10px] font-black uppercase tracking-wider text-vextro-primary">
                {brand?.name || "Unbranded"}
              </span>

              <span className="rounded-full bg-violet-50 px-3 py-1.5 text-[10px] font-black uppercase tracking-wider text-violet-700">
                {category?.name ||
                  `Category #${product.category_id}`}
              </span>

              {product.is_active ? (
                <span className="rounded-full bg-emerald-50 px-3 py-1.5 text-[10px] font-black uppercase tracking-wider text-emerald-700">
                  Active Product
                </span>
              ) : null}
            </div>

            <h1 className="mt-6 text-4xl font-black leading-[1.02] tracking-[-0.05em] text-vextro-ink sm:text-5xl lg:text-6xl">
              {product.name}
            </h1>

            {product.model ? (
              <p className="mt-4 text-base font-bold text-vextro-primary">
                Model: {product.model}
              </p>
            ) : null}

            <p className="mt-6 text-sm leading-8 text-vextro-muted sm:text-base">
              {product.description ||
                "Detailed product information will be updated as marketplace data becomes available."}
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              <div className="rounded-2xl border border-vextro-border bg-white p-5">
                <span className="text-[10px] font-black uppercase text-vextro-muted">
                  Variants
                </span>

                <strong className="mt-2 block text-2xl font-black text-vextro-ink">
                  {variants.length}
                </strong>
              </div>

              <div className="rounded-2xl border border-vextro-border bg-white p-5">
                <span className="text-[10px] font-black uppercase text-vextro-muted">
                  Listings
                </span>

                <strong className="mt-2 block text-2xl font-black text-vextro-ink">
                  {listings.length}
                </strong>
              </div>

              <div className="rounded-2xl border border-vextro-border bg-white p-5">
                <span className="text-[10px] font-black uppercase text-vextro-muted">
                  Price Points
                </span>

                <strong className="mt-2 block text-2xl font-black text-vextro-ink">
                  {priceHistory?.total_points || 0}
                </strong>
              </div>
            </div>

            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <a
                className={`inline-flex min-h-12 items-center justify-center rounded-xl px-6 text-sm font-black text-white shadow-lg ${
                  lowestListingId
                    ? "bg-vextro-primary shadow-blue-500/20 hover:bg-vextro-primary-dark"
                    : "pointer-events-none bg-slate-400"
                }`}
                href={
                  sortedListings.find(
                    (listing) =>
                      listing.id === lowestListingId,
                  )?.product_url || "#"
                }
                target="_blank"
                rel="noreferrer"
              >
                View Lowest Price
              </a>

              <Link
                className="inline-flex min-h-12 items-center justify-center rounded-xl border border-vextro-border bg-white px-6 text-sm font-black text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50"
                to="/alerts"
              >
                Set Price Alert
              </Link>
            </div>
          </div>
        </div>
      </section>

      {sectionWarnings.length ? (
        <section className="mx-auto max-w-7xl px-4 pb-4 sm:px-6 lg:px-8">
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm font-semibold text-amber-800">
            {sectionWarnings.join(" ")}
          </div>
        </section>
      ) : null}

      {variants.length > 0 ? (
        <section className="border-y border-vextro-border bg-white py-14 sm:py-18">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
              Product Configurations
            </span>

            <h2 className="mt-3 text-3xl font-black tracking-tight text-vextro-ink">
              Available variants
            </h2>

            <div className="mt-7 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {variants.map((variant) => (
                <article
                  className="rounded-2xl border border-vextro-border bg-vextro-canvas p-5"
                  key={variant.id}
                >
                  <div className="flex items-center justify-between gap-4">
                    <strong className="text-sm font-black text-vextro-ink">
                      {variant.sku ||
                        `Variant #${variant.id}`}
                    </strong>

                    <span className="rounded-full bg-white px-3 py-1 text-[10px] font-black capitalize text-vextro-muted">
                      {variant.condition}
                    </span>
                  </div>

                  <div className="mt-5 grid grid-cols-3 gap-2">
                    <div>
                      <span className="block text-[9px] font-bold uppercase text-vextro-muted">
                        RAM
                      </span>

                      <strong className="mt-1 block text-sm text-vextro-ink">
                        {variant.ram_gb
                          ? `${variant.ram_gb} GB`
                          : "—"}
                      </strong>
                    </div>

                    <div>
                      <span className="block text-[9px] font-bold uppercase text-vextro-muted">
                        Storage
                      </span>

                      <strong className="mt-1 block text-sm text-vextro-ink">
                        {variant.storage_gb
                          ? `${variant.storage_gb} GB`
                          : "—"}
                      </strong>
                    </div>

                    <div>
                      <span className="block text-[9px] font-bold uppercase text-vextro-muted">
                        Color
                      </span>

                      <strong className="mt-1 block truncate text-sm text-vextro-ink">
                        {variant.color || "—"}
                      </strong>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          </div>
        </section>
      ) : null}

      {specifications.length > 0 ? (
        <section className="py-14 sm:py-18">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
              Technical Details
            </span>

            <h2 className="mt-3 text-3xl font-black tracking-tight text-vextro-ink">
              Product specifications
            </h2>

            <div className="mt-7 overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-sm">
              {specifications.map(
                ([key, value], index) => (
                  <div
                    className={`grid gap-3 px-6 py-5 sm:grid-cols-[0.4fr_0.6fr] ${
                      index !== specifications.length - 1
                        ? "border-b border-vextro-border"
                        : ""
                    }`}
                    key={key}
                  >
                    <span className="text-sm font-bold text-vextro-muted">
                      {formatSpecificationLabel(key)}
                    </span>

                    <strong className="text-sm leading-6 text-vextro-ink">
                      {formatSpecificationValue(value)}
                    </strong>
                  </div>
                ),
              )}
            </div>
          </div>
        </section>
      ) : null}

      <section className="border-y border-vextro-border bg-white py-14 sm:py-18">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
            Cross-Platform Comparison
          </span>

          <div className="mt-3 flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
            <div>
              <h2 className="text-3xl font-black tracking-tight text-vextro-ink">
                Marketplace listings
              </h2>

              <p className="mt-3 max-w-2xl text-sm leading-7 text-vextro-muted">
                Compare current price, seller, rating,
                availability and warranty across supported
                marketplaces.
              </p>
            </div>

            <span className="rounded-full bg-vextro-canvas px-4 py-2 text-xs font-black text-vextro-muted">
              Sorted by lowest price
            </span>
          </div>

          {sortedListings.length > 0 ? (
            <div className="mt-8 grid gap-6 lg:grid-cols-2">
              {sortedListings.map((listing) => (
                <MarketplaceListingCard
                  key={listing.id}
                  listing={listing}
                  platform={
                    platformById[listing.platform_id]
                  }
                  isLowestPrice={
                    listing.id === lowestListingId
                  }
                />
              ))}
            </div>
          ) : (
            <div className="mt-8 grid min-h-72 place-content-center justify-items-center rounded-3xl border border-dashed border-slate-300 bg-vextro-canvas p-8 text-center">
              <span className="text-4xl">🛒</span>

              <h3 className="mt-5 text-xl font-black text-vextro-ink">
                No marketplace listings available
              </h3>

              <p className="mt-3 max-w-lg text-sm leading-7 text-vextro-muted">
                Listings will appear after this product has been
                matched with supported marketplace offers.
              </p>
            </div>
          )}
        </div>
      </section>

      <section className="py-14 sm:py-18">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <PriceHistoryPanel
            history={priceHistory}
            platformById={platformById}
          />
        </div>
      </section>
    </div>
  );
}

export default ProductDetailPage;