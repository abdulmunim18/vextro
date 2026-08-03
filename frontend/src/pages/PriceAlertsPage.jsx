import {
  useEffect,
  useMemo,
  useState,
} from "react";
import {
  Link,
  useLocation,
} from "react-router-dom";

import PriceAlertCard from "../components/PriceAlertCard";
import RouteLoadingState from "../components/RouteLoadingState";
import {
  getProductListings,
  getProducts,
} from "../services/catalogService";
import {
  createPriceAlert,
  deactivatePriceAlert,
  getPriceAlerts,
  updatePriceAlert,
} from "../services/priceAlertService";
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

function getLowestListing(listings) {
  return [...listings]
    .filter(
      (listing) =>
        listing.is_available &&
        Number.isFinite(
          Number(listing.current_price),
        ),
    )
    .sort(
      (firstListing, secondListing) =>
        Number(firstListing.current_price) -
        Number(secondListing.current_price),
    )[0];
}

function PriceAlertsPage() {
  const location = useLocation();

  const [alerts, setAlerts] = useState([]);
  const [products, setProducts] = useState([]);
  const [listingsByProduct, setListingsByProduct] =
    useState({});

  const [targetType, setTargetType] =
    useState("product");

  const [selectedProductId, setSelectedProductId] =
    useState("");

  const [selectedListingId, setSelectedListingId] =
    useState("");

  const [targetPrice, setTargetPrice] =
    useState("");

  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] =
    useState(false);

  const [busyAlertId, setBusyAlertId] =
    useState(null);

  const [errorMessage, setErrorMessage] =
    useState("");

  const [successMessage, setSuccessMessage] =
    useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadPageData() {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const [alertsData, productsData] =
          await Promise.all([
            getPriceAlerts(),
            getProducts({
              page: 1,
              page_size: 100,
            }),
          ]);

        if (!isMounted) {
          return;
        }

        const loadedAlerts =
          extractItems(alertsData);

        const loadedProducts =
          extractItems(productsData);

        setAlerts(loadedAlerts);
        setProducts(loadedProducts);

        const listingResults =
          await Promise.allSettled(
            loadedProducts.map(async (product) => {
              const listingsData =
                await getProductListings(product.id);

              return {
                productId: product.id,
                productName: product.name,
                listings: extractItems(
                  listingsData,
                ).map((listing) => ({
                  ...listing,
                  canonical_product_id:
                    product.id,
                  product_name: product.name,
                })),
              };
            }),
          );

        if (!isMounted) {
          return;
        }

        const loadedListings = {};

        listingResults.forEach((result) => {
          if (result.status === "fulfilled") {
            loadedListings[
              result.value.productId
            ] = result.value.listings;
          }
        });

        setListingsByProduct(loadedListings);

        const routeProductId = Number(
          location.state?.canonicalProductId,
        );

        const productFromRoute =
          loadedProducts.find(
            (product) =>
              product.id === routeProductId,
          );

        const initialProduct =
          productFromRoute || loadedProducts[0];

        if (initialProduct) {
          setSelectedProductId(
            String(initialProduct.id),
          );

          const initialListings =
            loadedListings[
              initialProduct.id
            ] || [];

          if (initialListings.length) {
            setSelectedListingId(
              String(initialListings[0].id),
            );
          }
        }

        const suggestedPrice = Number(
          location.state?.suggestedTargetPrice,
        );

        if (
          Number.isFinite(suggestedPrice) &&
          suggestedPrice > 0
        ) {
          setTargetPrice(
            Math.floor(suggestedPrice * 0.95),
          );
        }
      } catch (error) {
        if (!isMounted) {
          return;
        }

        setErrorMessage(
          getApiErrorMessage(
            error,
            "Unable to load your price alerts.",
          ),
        );
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    loadPageData();

    return () => {
      isMounted = false;
    };
  }, [
    location.state?.canonicalProductId,
    location.state?.suggestedTargetPrice,
  ]);

  const productById = useMemo(
    () =>
      Object.fromEntries(
        products.map((product) => [
          product.id,
          product,
        ]),
      ),
    [products],
  );

  const listingById = useMemo(() => {
    const entries = [];

    Object.values(listingsByProduct).forEach(
      (listings) => {
        listings.forEach((listing) => {
          entries.push([listing.id, listing]);
        });
      },
    );

    return Object.fromEntries(entries);
  }, [listingsByProduct]);

  const selectedProductListings =
    listingsByProduct[
      Number(selectedProductId)
    ] || [];

  const selectedListing =
    listingById[Number(selectedListingId)];

  const selectedProduct =
    productById[Number(selectedProductId)];

  const lowestSelectedProductListing =
    getLowestListing(selectedProductListings);

  const activeAlerts = alerts.filter(
    (alert) => alert.is_active,
  ).length;

  const triggeredAlerts = alerts.filter(
    (alert) => alert.is_triggered,
  ).length;

  function handleProductChange(event) {
    const nextProductId = event.target.value;
    const nextListings =
      listingsByProduct[
        Number(nextProductId)
      ] || [];

    setSelectedProductId(nextProductId);

    setSelectedListingId(
      nextListings[0]
        ? String(nextListings[0].id)
        : "",
    );

    setSuccessMessage("");
    setErrorMessage("");
  }

  function handleTargetTypeChange(nextType) {
    setTargetType(nextType);
    setSuccessMessage("");
    setErrorMessage("");

    if (
      nextType === "listing" &&
      !selectedListingId &&
      selectedProductListings[0]
    ) {
      setSelectedListingId(
        String(
          selectedProductListings[0].id,
        ),
      );
    }
  }

  function applySuggestedPrice() {
    const referencePrice =
      targetType === "listing"
        ? Number(selectedListing?.current_price)
        : Number(
            lowestSelectedProductListing
              ?.current_price,
          );

    if (
      Number.isFinite(referencePrice) &&
      referencePrice > 0
    ) {
      setTargetPrice(
        Math.floor(referencePrice * 0.95),
      );
    }
  }

  async function handleCreateAlert(event) {
    event.preventDefault();

    const numericTargetPrice =
      Number(targetPrice);

    if (!selectedProductId) {
      setErrorMessage(
        "Please select a product.",
      );
      return;
    }

    if (
      targetType === "listing" &&
      !selectedListingId
    ) {
      setErrorMessage(
        "Please select a marketplace listing.",
      );
      return;
    }

    if (
      !Number.isFinite(numericTargetPrice) ||
      numericTargetPrice <= 0
    ) {
      setErrorMessage(
        "Target price must be greater than zero.",
      );
      return;
    }

    const payload = {
      target_price: numericTargetPrice,
      currency: "PKR",
    };

    if (targetType === "product") {
      payload.canonical_product_id =
        Number(selectedProductId);
    } else {
      payload.listing_id =
        Number(selectedListingId);
    }

    setIsCreating(true);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const createdAlert =
        await createPriceAlert(payload);

      setAlerts((currentAlerts) => [
        createdAlert,
        ...currentAlerts,
      ]);

      setSuccessMessage(
        "Price alert created successfully.",
      );

      setTargetPrice("");
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to create this price alert.",
        ),
      );
    } finally {
      setIsCreating(false);
    }
  }

  async function handleUpdateAlert(
    alertId,
    payload,
  ) {
    setBusyAlertId(alertId);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const updatedAlert =
        await updatePriceAlert(
          alertId,
          payload,
        );

      setAlerts((currentAlerts) =>
        currentAlerts.map((alert) =>
          alert.id === alertId
            ? updatedAlert
            : alert,
        ),
      );

      setSuccessMessage(
        "Price alert updated successfully.",
      );
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to update this alert.",
        ),
      );
    } finally {
      setBusyAlertId(null);
    }
  }

  async function handleDeactivateAlert(alertId) {
    setBusyAlertId(alertId);
    setErrorMessage("");
    setSuccessMessage("");

    try {
      const updatedAlert =
        await deactivatePriceAlert(alertId);

      setAlerts((currentAlerts) =>
        currentAlerts.map((alert) =>
          alert.id === alertId
            ? updatedAlert
            : alert,
        ),
      );

      setSuccessMessage(
        "Price alert deactivated successfully.",
      );
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to deactivate this alert.",
        ),
      );
    } finally {
      setBusyAlertId(null);
    }
  }

  if (isLoading) {
    return (
      <RouteLoadingState message="Loading your price alerts..." />
    );
  }

  return (
    <section className="relative min-h-[calc(100vh-145px)] overflow-hidden bg-vextro-canvas py-14 sm:py-18 lg:py-20">
      <div className="pointer-events-none absolute -right-40 top-0 size-96 rounded-full bg-blue-300/15 blur-3xl" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col justify-between gap-8 lg:flex-row lg:items-end">
          <div className="max-w-3xl">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
              Price Intelligence
            </span>

            <h1 className="mt-4 text-4xl font-black leading-[1.02] tracking-[-0.05em] text-vextro-ink sm:text-5xl lg:text-6xl">
              Track prices without checking every marketplace
            </h1>

            <p className="mt-5 max-w-2xl text-sm leading-7 text-vextro-muted sm:text-base">
              Create product-level or marketplace-specific alerts
              and let VEXTRO monitor your target price.
            </p>
          </div>

          <div className="grid w-full grid-cols-3 gap-3 sm:w-auto">
            <div className="min-w-28 rounded-2xl border border-vextro-border bg-white p-4 text-center">
              <strong className="text-2xl font-black text-vextro-ink">
                {alerts.length}
              </strong>

              <span className="mt-1 block text-[10px] font-bold uppercase text-vextro-muted">
                Total
              </span>
            </div>

            <div className="min-w-28 rounded-2xl border border-blue-200 bg-blue-50 p-4 text-center">
              <strong className="text-2xl font-black text-vextro-primary">
                {activeAlerts}
              </strong>

              <span className="mt-1 block text-[10px] font-bold uppercase text-blue-700">
                Active
              </span>
            </div>

            <div className="min-w-28 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-center">
              <strong className="text-2xl font-black text-emerald-700">
                {triggeredAlerts}
              </strong>

              <span className="mt-1 block text-[10px] font-bold uppercase text-emerald-700">
                Triggered
              </span>
            </div>
          </div>
        </div>

        {errorMessage ? (
          <div
            className="mt-8 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm font-semibold text-red-700"
            role="alert"
          >
            {errorMessage}
          </div>
        ) : null}

        {successMessage ? (
          <div
            className="mt-8 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-semibold text-emerald-700"
            role="status"
          >
            {successMessage}
          </div>
        ) : null}

        <div className="mt-10 grid gap-8 xl:grid-cols-[0.78fr_1.22fr]">
          <form
            className="h-fit rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-8 xl:sticky xl:top-28"
            onSubmit={handleCreateAlert}
          >
            <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
              New Alert
            </span>

            <h2 className="mt-3 text-2xl font-black tracking-tight text-vextro-ink">
              Create a target-price alert
            </h2>

            <p className="mt-3 text-sm leading-6 text-vextro-muted">
              Monitor an entire product or one specific
              marketplace listing.
            </p>

            <div className="mt-7 grid gap-3 sm:grid-cols-2">
              <button
                className={`rounded-2xl border p-4 text-left transition ${
                  targetType === "product"
                    ? "border-vextro-primary bg-blue-50 ring-2 ring-blue-100"
                    : "border-vextro-border hover:border-blue-200"
                }`}
                type="button"
                onClick={() =>
                  handleTargetTypeChange("product")
                }
              >
                <strong className="block text-sm font-black text-vextro-ink">
                  Product Alert
                </strong>

                <span className="mt-1 block text-xs leading-5 text-vextro-muted">
                  Monitor the lowest price across all listings.
                </span>
              </button>

              <button
                className={`rounded-2xl border p-4 text-left transition ${
                  targetType === "listing"
                    ? "border-vextro-primary bg-blue-50 ring-2 ring-blue-100"
                    : "border-vextro-border hover:border-blue-200"
                }`}
                type="button"
                onClick={() =>
                  handleTargetTypeChange("listing")
                }
              >
                <strong className="block text-sm font-black text-vextro-ink">
                  Listing Alert
                </strong>

                <span className="mt-1 block text-xs leading-5 text-vextro-muted">
                  Monitor one Daraz or PriceOye offer.
                </span>
              </button>
            </div>

            <div className="mt-6 grid gap-2">
              <label
                className="text-sm font-black text-vextro-ink"
                htmlFor="alert-product"
              >
                Product
              </label>

              <select
                id="alert-product"
                className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                value={selectedProductId}
                onChange={handleProductChange}
                required
              >
                <option value="">
                  Select a product
                </option>

                {products.map((product) => (
                  <option
                    key={product.id}
                    value={product.id}
                  >
                    {product.name}
                  </option>
                ))}
              </select>
            </div>

            {targetType === "listing" ? (
              <div className="mt-5 grid gap-2">
                <label
                  className="text-sm font-black text-vextro-ink"
                  htmlFor="alert-listing"
                >
                  Marketplace listing
                </label>

                <select
                  id="alert-listing"
                  className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                  value={selectedListingId}
                  onChange={(event) =>
                    setSelectedListingId(
                      event.target.value,
                    )
                  }
                  required
                >
                  <option value="">
                    Select a listing
                  </option>

                  {selectedProductListings.map(
                    (listing) => (
                      <option
                        key={listing.id}
                        value={listing.id}
                      >
                        {listing.title} — PKR{" "}
                        {Number(
                          listing.current_price,
                        ).toLocaleString("en-PK")}
                      </option>
                    ),
                  )}
                </select>
              </div>
            ) : null}

            <div className="mt-5 grid gap-2">
              <div className="flex items-center justify-between gap-4">
                <label
                  className="text-sm font-black text-vextro-ink"
                  htmlFor="new-target-price"
                >
                  Target price
                </label>

                <button
                  className="text-xs font-black text-vextro-primary hover:text-vextro-primary-dark"
                  type="button"
                  onClick={applySuggestedPrice}
                >
                  Suggest 5% lower
                </button>
              </div>

              <div className="flex min-h-12 items-center rounded-xl border border-vextro-border bg-white transition focus-within:border-vextro-primary focus-within:ring-4 focus-within:ring-blue-100">
                <span className="border-r border-vextro-border px-4 text-xs font-black text-vextro-muted">
                  PKR
                </span>

                <input
                  id="new-target-price"
                  className="min-w-0 flex-1 border-0 bg-transparent px-4 text-sm font-semibold text-vextro-ink outline-none"
                  type="number"
                  min="0.01"
                  step="0.01"
                  value={targetPrice}
                  onChange={(event) =>
                    setTargetPrice(
                      event.target.value,
                    )
                  }
                  placeholder="Enter target price"
                  required
                />
              </div>
            </div>

            <div className="mt-5 rounded-2xl bg-vextro-canvas p-4 text-xs leading-6 text-vextro-muted">
              Selected product:{" "}
              <strong className="text-vextro-ink">
                {selectedProduct?.name ||
                  "None selected"}
              </strong>
            </div>

            <button
              className="mt-6 min-h-12 w-full rounded-xl bg-vextro-primary px-5 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:-translate-y-0.5 hover:bg-vextro-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
              type="submit"
              disabled={isCreating}
            >
              {isCreating
                ? "Creating alert..."
                : "Create Price Alert"}
            </button>
          </form>

          <div>
            <div className="flex items-center justify-between gap-5">
              <div>
                <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
                  Your Alerts
                </span>

                <h2 className="mt-2 text-2xl font-black text-vextro-ink">
                  Saved price targets
                </h2>
              </div>

              <Link
                className="rounded-xl border border-vextro-border bg-white px-4 py-2.5 text-xs font-black text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50"
                to="/products"
              >
                Browse Products
              </Link>
            </div>

            {alerts.length ? (
              <div className="mt-6 grid gap-6 lg:grid-cols-2">
                {alerts.map((alert) => {
                  const listing =
                    listingById[alert.listing_id];

                  const product =
                    alert.canonical_product_id
                      ? productById[
                          alert
                            .canonical_product_id
                        ]
                      : productById[
                          listing
                            ?.canonical_product_id
                        ];

                  return (
                    <PriceAlertCard
                      key={alert.id}
                      alert={alert}
                      productName={
                        product?.name ||
                        listing?.product_name ||
                        "Unknown Product"
                      }
                      listingTitle={
                        listing?.title || ""
                      }
                      currentPrice={
                        listing?.current_price ||
                        getLowestListing(
                          listingsByProduct[
                            alert
                              .canonical_product_id
                          ] || [],
                        )?.current_price
                      }
                      onUpdate={
                        handleUpdateAlert
                      }
                      onDeactivate={
                        handleDeactivateAlert
                      }
                      isBusy={
                        busyAlertId === alert.id
                      }
                    />
                  );
                })}
              </div>
            ) : (
              <div className="mt-6 grid min-h-96 place-content-center justify-items-center rounded-3xl border border-dashed border-slate-300 bg-white p-8 text-center">
                <span className="grid size-18 place-items-center rounded-3xl bg-blue-50 text-4xl">
                  🔔
                </span>

                <h3 className="mt-6 text-2xl font-black text-vextro-ink">
                  No price alerts yet
                </h3>

                <p className="mt-3 max-w-lg text-sm leading-7 text-vextro-muted">
                  Select a product and create your first target
                  price alert.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

export default PriceAlertsPage;