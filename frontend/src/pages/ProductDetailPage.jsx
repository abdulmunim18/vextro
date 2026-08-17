import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Link,
  useParams,
} from "react-router-dom";

import CreatePriceAlertCard from "../components/CreatePriceAlertCard";
import MarketplaceListingCard from "../components/MarketplaceListingCard";
import PriceHistoryChart from "../components/PriceHistoryChart";
import PriceForecastCard from "../components/PriceForecastCard";
import BuyTimeGuidanceCard from "../components/BuyTimeGuidanceCard";
import RouteLoadingState from "../components/RouteLoadingState";
import { useAuth } from "../context/useAuth";
import {
  getBrands,
  getCategories,
  getPlatforms,
  getProductById,
  getProductListings,
  getProductPriceHistory,
  getProductPriceForecast,
  getProductBuyGuidance,
  getPersonalizedProductBuyGuidance,
} from "../services/catalogService";
import { getApiErrorMessage } from "../utils/apiError";
import {
  formatAttributeLabel,
  formatPrice,
  toFiniteNumber,
} from "../utils/productDisplay";

function extractItems(responseData) {
  if (Array.isArray(responseData)) {
    return responseData;
  }

  if (Array.isArray(responseData?.items)) {
    return responseData.items;
  }

  return [];
}

function ProductDetailPage() {
  const { productId } = useParams();
  const {
    isAuthenticated,
    hasRole,
  } = useAuth();

  const canPersonalizeGuidance =
    isAuthenticated && hasRole("consumer", "admin");

  const [product, setProduct] = useState(null);
  const [listingResponse, setListingResponse] =
    useState(null);

  const [priceHistory, setPriceHistory] =
    useState(null);
  const [priceForecast, setPriceForecast] =
    useState(null);
  const [buyGuidance, setBuyGuidance] = useState(null);

  const [platforms, setPlatforms] = useState([]);
  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);

  const [selectedImage, setSelectedImage] =
    useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] =
    useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadProductPage() {
      const numericProductId = Number(productId);

      if (
        !Number.isInteger(numericProductId) ||
        numericProductId < 1
      ) {
        setErrorMessage("Invalid product ID.");
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setErrorMessage("");

      try {
        const [
          productData,
          listingsData,
          historyData,
          forecastData,
          guidanceData,
          platformData,
          categoryData,
          brandData,
        ] = await Promise.all([
          getProductById(numericProductId),
          getProductListings(numericProductId),
          getProductPriceHistory(numericProductId),
          getProductPriceForecast(numericProductId),
          canPersonalizeGuidance
            ? getPersonalizedProductBuyGuidance(
                numericProductId,
              )
            : getProductBuyGuidance(numericProductId),
          getPlatforms(),
          getCategories(),
          getBrands(),
        ]);

        if (!isMounted) {
          return;
        }

        setProduct(productData);
        setListingResponse(listingsData);
        setPriceHistory(historyData);
        setPriceForecast(forecastData);
        setBuyGuidance(guidanceData);
        setPlatforms(extractItems(platformData));
        setCategories(extractItems(categoryData));
        setBrands(extractItems(brandData));

        const productImages = Array.isArray(
          productData?.images,
        )
          ? productData.images
          : [];

        const primaryImage =
          productImages.find(
            (image) => image.is_primary,
          ) || productImages[0];

        setSelectedImage(
          primaryImage?.image_url || "",
        );
      } catch (error) {
        if (!isMounted) {
          return;
        }

        setErrorMessage(
          getApiErrorMessage(
            error,
            "Unable to load this product.",
          ),
        );
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadProductPage();

    return () => {
      isMounted = false;
    };
  }, [canPersonalizeGuidance, productId]);

  const refreshPersonalizedGuidance = useCallback(
    async () => {
      if (!canPersonalizeGuidance) {
        return;
      }

      const numericProductId = Number(productId);

      if (
        !Number.isInteger(numericProductId) ||
        numericProductId < 1
      ) {
        return;
      }

      try {
        const guidanceData =
          await getPersonalizedProductBuyGuidance(
            numericProductId,
          );

        setBuyGuidance(guidanceData);
      } catch {
        // Alert creation remains successful even if this optional refresh fails.
      }
    },
    [canPersonalizeGuidance, productId],
  );

  const listings = useMemo(
    () =>
      Array.isArray(listingResponse?.items)
        ? listingResponse.items
        : [],
    [listingResponse],
  );

  const platformNames = useMemo(
    () =>
      new Map(
        platforms.map((platform) => [
          platform.id,
          platform.name,
        ]),
      ),
    [platforms],
  );

  const brandName =
    brands.find(
      (brand) => brand.id === product?.brand_id,
    )?.name || "Unbranded";

  const categoryName =
    categories.find(
      (category) =>
        category.id === product?.category_id,
    )?.name || "General";

  const availableListings = listings.filter(
    (listing) =>
      listing.is_available &&
      toFiniteNumber(listing.current_price) !== null,
  );

  const lowestListing =
    availableListings.length > 0
      ? availableListings.reduce(
          (lowestItem, currentItem) =>
            toFiniteNumber(
              currentItem.current_price,
            ) <
            toFiniteNumber(
              lowestItem.current_price,
            )
              ? currentItem
              : lowestItem,
        )
      : null;

  const historicalPrices = useMemo(
    () =>
      (priceHistory?.listings || [])
        .flatMap((listing) => listing.points || [])
        .map((point) => toFiniteNumber(point.price))
        .filter((price) => price !== null),
    [priceHistory],
  );

  const historicalMinimum =
    historicalPrices.length > 0
      ? Math.min(...historicalPrices)
      : null;

  const historicalMaximum =
    historicalPrices.length > 0
      ? Math.max(...historicalPrices)
      : null;

  const historicalAverage =
    historicalPrices.length > 0
      ? historicalPrices.reduce(
          (total, price) => total + price,
          0,
        ) / historicalPrices.length
      : null;

  const defaultCurrency =
    lowestListing?.currency ||
    listings[0]?.currency ||
    "PKR";

  const variants = Array.isArray(product?.variants)
    ? product.variants
    : [];

  const productImages = Array.isArray(product?.images)
    ? product.images
    : [];

  const specifications = Object.entries(
    product?.specifications || {},
  );

  if (isLoading) {
    return (
      <RouteLoadingState message="Loading product comparison and price intelligence..." />
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

          <p className="mt-3 text-sm leading-7 text-vextro-muted">
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
    <section className="relative overflow-hidden bg-vextro-canvas py-12 sm:py-16 lg:py-20">
      <div className="pointer-events-none absolute -right-48 top-0 size-[460px] rounded-full bg-blue-300/15 blur-3xl" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <nav className="mb-8 flex flex-wrap items-center gap-2 text-xs font-semibold text-vextro-muted">
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

        <div className="grid gap-8 lg:grid-cols-[0.9fr_1.1fr]">
          <div>
            <div className="grid min-h-[430px] place-items-center overflow-hidden rounded-3xl border border-vextro-border bg-white p-8 shadow-sm">
              {selectedImage ? (
                <img
                  className="max-h-[390px] w-full object-contain"
                  src={selectedImage}
                  alt={product.name}
                />
              ) : (
                <div className="flex flex-col items-center gap-4 text-vextro-muted">
                  <span className="grid size-28 place-items-center rounded-[32px] bg-gradient-to-br from-vextro-primary to-violet-600 text-5xl font-black text-white shadow-vextro">
                    {product.name
                      .charAt(0)
                      .toUpperCase()}
                  </span>

                  <p className="text-sm font-semibold">
                    Product image unavailable
                  </p>
                </div>
              )}
            </div>

            {productImages.length > 1 ? (
              <div className="mt-4 grid grid-cols-4 gap-3 sm:grid-cols-5">
                {productImages.map((image) => (
                  <button
                    className={`grid aspect-square place-items-center overflow-hidden rounded-2xl border bg-white p-2 transition ${
                      selectedImage === image.image_url
                        ? "border-2 border-vextro-primary shadow-md"
                        : "border-vextro-border hover:border-blue-200"
                    }`}
                    key={image.id}
                    type="button"
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

          <div className="rounded-3xl border border-vextro-border bg-white p-7 shadow-sm sm:p-9">
            <div className="flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-blue-50 px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.14em] text-vextro-primary">
                {brandName}
              </span>

              <span className="rounded-full bg-vextro-canvas px-3 py-1.5 text-[10px] font-black uppercase tracking-[0.14em] text-vextro-muted">
                {categoryName}
              </span>

              <span
                className={`rounded-full px-3 py-1.5 text-[10px] font-black ${
                  product.is_active
                    ? "bg-emerald-50 text-emerald-700"
                    : "bg-red-50 text-red-700"
                }`}
              >
                {product.is_active
                  ? "Active product"
                  : "Inactive product"}
              </span>
            </div>

            <h1 className="mt-6 text-4xl font-black leading-[1.03] tracking-[-0.05em] text-vextro-ink sm:text-5xl">
              {product.name}
            </h1>

            {product.model ? (
              <p className="mt-3 text-base font-bold text-vextro-primary">
                Model: {product.model}
              </p>
            ) : null}

            <p className="mt-6 text-sm leading-7 text-vextro-muted sm:text-base">
              {product.description ||
                "Marketplace listings and historical price intelligence for this standardized VEXTRO product."}
            </p>

            <div className="mt-8 grid grid-cols-2 gap-3 sm:grid-cols-4">
              <div className="rounded-2xl bg-vextro-canvas p-4">
                <span className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                  Listings
                </span>

                <strong className="mt-2 block text-2xl font-black text-vextro-ink">
                  {listings.length}
                </strong>
              </div>

              <div className="rounded-2xl bg-vextro-canvas p-4">
                <span className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                  Available
                </span>

                <strong className="mt-2 block text-2xl font-black text-emerald-600">
                  {availableListings.length}
                </strong>
              </div>

              <div className="rounded-2xl bg-vextro-canvas p-4">
                <span className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                  Variants
                </span>

                <strong className="mt-2 block text-2xl font-black text-vextro-primary">
                  {variants.length}
                </strong>
              </div>

              <div className="rounded-2xl bg-vextro-canvas p-4">
                <span className="text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                  Snapshots
                </span>

                <strong className="mt-2 block text-2xl font-black text-violet-600">
                  {priceHistory?.total_points || 0}
                </strong>
              </div>
            </div>

            <div className="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-5">
              
              <span className="text-[10px] font-black uppercase tracking-wide text-emerald-700">
                Lowest current marketplace price
              </span>

              <strong className="mt-2 block text-3xl font-black tracking-tight text-emerald-700">
                {lowestListing
                  ? formatPrice(
                      lowestListing.current_price,
                      lowestListing.currency,
                    )
                  : "No available offer"}
              </strong>

              {lowestListing ? (
                <p className="mt-2 text-xs font-semibold text-emerald-700">
                  Available on{" "}
                  {platformNames.get(
                    lowestListing.platform_id,
                  ) ||
                    `Platform ${lowestListing.platform_id}`}
                </p>
              ) : null}
            </div>
            <CreatePriceAlertCard
              product={product}
              listings={listings}
              platformNames={platformNames}
              lowestListing={lowestListing}
              onAlertCreated={refreshPersonalizedGuidance}
            />
          </div>
        </div>

        {variants.length > 0 ? (
          <section className="mt-10 rounded-3xl border border-vextro-border bg-white p-7 shadow-sm sm:p-9">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
              Product Variants
            </span>

            <h2 className="mt-3 text-3xl font-black tracking-tight text-vextro-ink">
              Available configurations
            </h2>

            <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {variants.map((variant) => (
                <article
                  className="rounded-2xl border border-vextro-border bg-vextro-canvas p-5"
                  key={variant.id}
                >
                  <div className="flex items-center justify-between gap-4">
                    <strong className="text-sm font-black text-vextro-ink">
                      {variant.sku ||
                        `Variant ${variant.id}`}
                    </strong>

                    <span className="rounded-full bg-white px-3 py-1 text-[10px] font-black capitalize text-vextro-muted">
                      {variant.condition}
                    </span>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-2">
                    {variant.ram_gb ? (
                      <span className="rounded-lg bg-white px-3 py-2 text-xs font-bold text-vextro-ink">
                        {variant.ram_gb} GB RAM
                      </span>
                    ) : null}

                    {variant.storage_gb ? (
                      <span className="rounded-lg bg-white px-3 py-2 text-xs font-bold text-vextro-ink">
                        {variant.storage_gb} GB Storage
                      </span>
                    ) : null}

                    {variant.color ? (
                      <span className="rounded-lg bg-white px-3 py-2 text-xs font-bold text-vextro-ink">
                        {variant.color}
                      </span>
                    ) : null}
                  </div>
                </article>
              ))}
            </div>
          </section>
        ) : null}

        <section className="mt-10">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
            <div>
              <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
                Marketplace Comparison
              </span>

              <h2 className="mt-3 text-3xl font-black tracking-tight text-vextro-ink sm:text-4xl">
                Compare current offers
              </h2>

              <p className="mt-3 text-sm leading-7 text-vextro-muted">
                Prices, availability and seller information are
                loaded from the VEXTRO marketplace catalog.
              </p>
            </div>

            <span className="rounded-full border border-vextro-border bg-white px-4 py-2 text-xs font-black text-vextro-muted">
              {listingResponse?.total || 0} offers
            </span>
          </div>

          {listings.length > 0 ? (
            <div className="mt-7 grid gap-5">
              {listings
                .slice()
                .sort(
                  (firstListing, secondListing) =>
                    (toFiniteNumber(
                      firstListing.current_price,
                    ) ?? Number.MAX_VALUE) -
                    (toFiniteNumber(
                      secondListing.current_price,
                    ) ?? Number.MAX_VALUE),
                )
                .map((listing) => (
                  <MarketplaceListingCard
                    key={listing.id}
                    listing={listing}
                    platformName={
                      platformNames.get(
                        listing.platform_id,
                      ) ||
                      `Platform ${listing.platform_id}`
                    }
                    isLowest={
                      listing.id === lowestListing?.id
                    }
                  />
                ))}
            </div>
          ) : (
            <div className="mt-7 rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
              <h3 className="text-xl font-black text-vextro-ink">
                No marketplace listings found
              </h3>

              <p className="mt-2 text-sm text-vextro-muted">
                Offers will appear after marketplace data is
                imported.
              </p>
            </div>
          )}
        </section>

        <section className="mt-10 rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-9">
          <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
            <div>
              <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
                Price Intelligence
              </span>

              <h2 className="mt-3 text-3xl font-black tracking-tight text-vextro-ink sm:text-4xl">
                Historical price movement
              </h2>

              <p className="mt-3 text-sm leading-7 text-vextro-muted">
                Every marketplace snapshot is preserved instead
                of replacing previous prices.
              </p>
            </div>

            <div className="grid grid-cols-3 gap-2">
              <div className="rounded-xl bg-vextro-canvas p-3 text-center">
                <span className="block text-[9px] font-black uppercase text-vextro-muted">
                  Minimum
                </span>

                <strong className="mt-1 block text-xs font-black text-emerald-600">
                  {formatPrice(
                    historicalMinimum,
                    defaultCurrency,
                  )}
                </strong>
              </div>

              <div className="rounded-xl bg-vextro-canvas p-3 text-center">
                <span className="block text-[9px] font-black uppercase text-vextro-muted">
                  Average
                </span>

                <strong className="mt-1 block text-xs font-black text-vextro-primary">
                  {formatPrice(
                    historicalAverage,
                    defaultCurrency,
                  )}
                </strong>
              </div>

              <div className="rounded-xl bg-vextro-canvas p-3 text-center">
                <span className="block text-[9px] font-black uppercase text-vextro-muted">
                  Maximum
                </span>

                <strong className="mt-1 block text-xs font-black text-red-600">
                  {formatPrice(
                    historicalMaximum,
                    defaultCurrency,
                  )}
                </strong>
              </div>
            </div>
          </div>

          <div className="mt-8">
            <PriceHistoryChart history={priceHistory} />
          </div>
        </section>

        <PriceForecastCard
          history={priceHistory}
          forecast={priceForecast}
        />

        <BuyTimeGuidanceCard guidance={buyGuidance} />

        {specifications.length > 0 ? (
          <section className="mt-10 rounded-3xl border border-vextro-border bg-white p-7 shadow-sm sm:p-9">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
              Product Information
            </span>

            <h2 className="mt-3 text-3xl font-black tracking-tight text-vextro-ink">
              Specifications
            </h2>

            <dl className="mt-7 grid gap-px overflow-hidden rounded-2xl border border-vextro-border bg-vextro-border sm:grid-cols-2">
              {specifications.map(
                ([attribute, value]) => (
                  <div
                    className="flex items-center justify-between gap-5 bg-white p-5"
                    key={attribute}
                  >
                    <dt className="text-sm font-bold text-vextro-muted">
                      {formatAttributeLabel(attribute)}
                    </dt>

                    <dd className="text-right text-sm font-black text-vextro-ink">
                      {typeof value === "object"
                        ? JSON.stringify(value)
                        : String(value)}
                    </dd>
                  </div>
                ),
              )}
            </dl>
          </section>
        ) : null}
      </div>
    </section>
  );
}

export default ProductDetailPage;
