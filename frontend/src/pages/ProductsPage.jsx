import {
  useEffect,
  useMemo,
  useState,
} from "react";
import { Link } from "react-router-dom";
import ProductCard from "../components/ProductCard";
import {
  getBrands,
  getCategories,
  getPlatforms,
  getProducts,
} from "../services/catalogService";
import { getApiErrorMessage } from "../utils/apiError";

const PAGE_SIZE = 12;

const initialFilters = {
  query: "",
  categorySlug: "",
  brandSlug: "",
  minPrice: "",
  maxPrice: "",
  platformCode: "",
  minRating: "",
  availability: "available",
  sortBy: "name_asc",
};

function extractItems(responseData) {
  if (Array.isArray(responseData)) {
    return responseData;
  }

  if (Array.isArray(responseData?.items)) {
    return responseData.items;
  }

  if (Array.isArray(responseData?.products)) {
    return responseData.products;
  }

  return [];
}

function ProductsPage() {
  const [draftFilters, setDraftFilters] = useState(
    initialFilters,
  );

  const [appliedFilters, setAppliedFilters] = useState(
    initialFilters,
  );

const [products, setProducts] = useState([]);
const [selectedProducts, setSelectedProducts] =
  useState([]);

const [categories, setCategories] = useState([]);
const [brands, setBrands] = useState([]);
const [platforms, setPlatforms] = useState([]);

  const [page, setPage] = useState(1);
  const [reloadKey, setReloadKey] = useState(0);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);

  const [isLoadingProducts, setIsLoadingProducts] =
    useState(true);

  const [isLoadingFilters, setIsLoadingFilters] =
    useState(true);

  const [errorMessage, setErrorMessage] = useState("");

  useEffect(() => {
    let isMounted = true;

    async function loadFilterOptions() {
      setIsLoadingFilters(true);

      try {
          const [categoryData, brandData, platformData] =
          await Promise.all([
            getCategories(),
            getBrands(),
            getPlatforms(),
          ]);

        if (!isMounted) {
          return;
        }

        setCategories(extractItems(categoryData));
        setBrands(extractItems(brandData));
        setPlatforms(extractItems(platformData));
      } catch (error) {
        if (!isMounted) {
          return;
        }

        setErrorMessage(
          getApiErrorMessage(
            error,
            "Unable to load product filters.",
          ),
        );
      } finally {
        if (isMounted) {
          setIsLoadingFilters(false);
        }
      }
    }

    loadFilterOptions();

    return () => {
      isMounted = false;
    };
  }, []);

useEffect(() => {
  let isCancelled = false;

  const params = {
    page,
    page_size: PAGE_SIZE,
  };

  const normalizedQuery =
    appliedFilters.query.trim();

  if (normalizedQuery) {
    params.q = normalizedQuery;
    params.search = normalizedQuery;
  }

  if (appliedFilters.categorySlug) {
    params.category_slug =
      appliedFilters.categorySlug;
  }

  if (appliedFilters.brandSlug) {
    params.brand_slug =
      appliedFilters.brandSlug;
  }

  if (appliedFilters.minPrice) {
    params.min_price = appliedFilters.minPrice;
  }

  if (appliedFilters.maxPrice) {
    params.max_price = appliedFilters.maxPrice;
  }

  if (appliedFilters.platformCode) {
    params.platform_code = appliedFilters.platformCode;
  }

  if (appliedFilters.minRating) {
    params.min_rating = appliedFilters.minRating;
  }

  if (appliedFilters.availability) {
    params.is_available =
      appliedFilters.availability === "available";
  }

  params.sort_by = appliedFilters.sortBy;

  getProducts(params)
    .then((responseData) => {
      if (isCancelled) {
        return;
      }

      const responseItems =
        extractItems(responseData);

      const responseTotalItems = Number(
        responseData?.total_items ??
          responseData?.total ??
          responseItems.length,
      );

      const responseTotalPages = Number(
        responseData?.total_pages ??
          responseData?.pages ??
          Math.ceil(
            responseTotalItems / PAGE_SIZE,
          ),
      );

      setProducts(responseItems);

      setTotalItems(
        Number.isFinite(responseTotalItems)
          ? responseTotalItems
          : responseItems.length,
      );

      setTotalPages(
        Number.isFinite(responseTotalPages) &&
          responseTotalPages > 0
          ? responseTotalPages
          : 1,
      );
    })
    .catch((error) => {
      if (isCancelled) {
        return;
      }

      setProducts([]);
      setTotalItems(0);
      setTotalPages(1);

      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to load marketplace products.",
        ),
      );
    })
    .finally(() => {
      if (!isCancelled) {
        setIsLoadingProducts(false);
      }
    });

  return () => {
    isCancelled = true;
  };
}, [appliedFilters, page, reloadKey]);



  function handleFilterChange(event) {
    const { name, value } = event.target;

    setDraftFilters((currentFilters) => ({
      ...currentFilters,
      [name]: value,
    }));
  }

 function handleSearch(event) {
  event.preventDefault();

  setIsLoadingProducts(true);
  setErrorMessage("");
  setPage(1);

  setAppliedFilters({
    ...draftFilters,
    query: draftFilters.query.trim(),
  });
}

function handleReset() {
  setIsLoadingProducts(true);
  setErrorMessage("");
  setDraftFilters(initialFilters);
  setAppliedFilters(initialFilters);
  setPage(1);
}

function handleRetry() {
  setIsLoadingProducts(true);
  setErrorMessage("");
  setReloadKey((currentKey) => currentKey + 1);
}

function changePage(nextPage) {
  setIsLoadingProducts(true);
  setErrorMessage("");
  setPage(nextPage);

  window.scrollTo({
    top: 0,
    behavior: "smooth",
  });
}
function handleToggleCompare(product) {
  setSelectedProducts((currentProducts) => {
    const isAlreadySelected =
      currentProducts.some(
        (selectedProduct) =>
          selectedProduct.id === product.id,
      );

    if (isAlreadySelected) {
      return currentProducts.filter(
        (selectedProduct) =>
          selectedProduct.id !== product.id,
      );
    }

    if (currentProducts.length >= 3) {
      return currentProducts;
    }

    return [
      ...currentProducts,
      product,
    ];
  });
}
function handleClearComparison() {
  setSelectedProducts([]);
}

const categoryNameById = useMemo(
  () =>
    new Map(
      categories.map((category) => [
        category.id,
        category.name,
      ]),
    ),
  [categories],
);

const brandNameById = useMemo(
  () =>
    new Map(
      brands.map((brand) => [
        brand.id,
        brand.name,
      ]),
    ),
  [brands],
);
const hasAppliedFilters = Boolean(
  appliedFilters.query ||
    appliedFilters.categorySlug ||
    appliedFilters.brandSlug ||
    appliedFilters.minPrice ||
    appliedFilters.maxPrice ||
    appliedFilters.platformCode ||
    appliedFilters.minRating ||
    appliedFilters.availability !== "available" ||
    appliedFilters.sortBy !== "name_asc",
);
const selectedProductIds = useMemo(
  () =>
    new Set(
      selectedProducts.map(
        (selectedProduct) => selectedProduct.id,
      ),
    ),
  [selectedProducts],
);
const comparisonUrl =
  selectedProducts.length >= 2
    ? `/compare?ids=${selectedProducts
        .map((product) => product.id)
        .join(",")}`
    : "";
  return (
    <section className="relative min-h-[calc(100vh-145px)] overflow-x-hidden bg-vextro-canvas py-14 sm:py-18 lg:py-20">
      <div className="pointer-events-none absolute -right-48 top-0 size-[460px] rounded-full bg-blue-300/15 blur-3xl" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-start justify-between gap-7 lg:flex-row lg:items-end">
          <div className="max-w-3xl">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
              Product Discovery
            </span>

            <h1 className="mt-4 text-4xl font-black leading-[1.02] tracking-[-0.05em] text-vextro-ink sm:text-5xl lg:text-6xl">
              Find and compare marketplace products
            </h1>

            <p className="mt-5 max-w-2xl text-sm leading-7 text-vextro-muted sm:text-base">
              Search VEXTRO&apos;s normalized catalog and compare
              products collected from supported ecommerce
              marketplaces.
            </p>
          </div>

          <div className="flex min-w-44 flex-col rounded-2xl border border-vextro-border bg-white p-5 shadow-sm">
            <span className="text-xs font-bold text-vextro-muted">
              Catalog results
            </span>

            <strong className="mt-1 text-3xl font-black tracking-tight text-vextro-primary">
              {totalItems}
            </strong>

            <small className="mt-1 text-xs text-vextro-muted">
              matching products
            </small>
          </div>
        </div>

        <form
          className="mt-10 grid gap-4 rounded-3xl border border-vextro-border bg-white p-5 shadow-sm sm:grid-cols-2 lg:grid-cols-4 lg:items-end"
          onSubmit={handleSearch}
        >
          <div className="grid gap-2">
            <label
              className="text-xs font-black text-vextro-ink"
              htmlFor="product-search"
            >
              Search products
            </label>

            <div className="flex min-h-12 items-center gap-3 rounded-xl border border-vextro-border bg-white px-4 transition focus-within:border-vextro-primary focus-within:ring-4 focus-within:ring-blue-100">
              <span className="text-xl text-vextro-muted">
                ⌕
              </span>

              <input
                id="product-search"
                className="w-full border-0 bg-transparent text-sm text-vextro-ink outline-none placeholder:text-slate-400"
                name="query"
                type="search"
                value={draftFilters.query}
                onChange={handleFilterChange}
                placeholder="Product, brand or model..."
              />
            </div>
          </div>

          <div className="grid gap-2">
            <label
              className="text-xs font-black text-vextro-ink"
              htmlFor="category-filter"
            >
              Category
            </label>

            <select
  id="category-filter"
  className="min-h-12 w-full cursor-pointer rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
  name="categorySlug"
  value={draftFilters.categorySlug}
  onChange={handleFilterChange}
  disabled={isLoadingFilters}
>
  <option value="">All categories</option>

  {categories.map((category) => (
    <option
      key={category.id}
      value={category.slug}
    >
      {category.name}
    </option>
  ))}
</select>
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-black text-vextro-ink" htmlFor="platform-filter">
              Platform
            </label>
            <select id="platform-filter" name="platformCode" value={draftFilters.platformCode} onChange={handleFilterChange} className="min-h-12 rounded-xl border border-vextro-border bg-white px-4 text-sm">
              <option value="">All platforms</option>
              {platforms.map((platform) => (
                <option key={platform.id} value={platform.code}>
                  {platform.name}
                </option>
              ))}
            </select>
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-black text-vextro-ink" htmlFor="minimum-price">
              Minimum price
            </label>
            <input id="minimum-price" name="minPrice" type="number" min="0" step="1" value={draftFilters.minPrice} onChange={handleFilterChange} placeholder="PKR 0" className="min-h-12 rounded-xl border border-vextro-border px-4 text-sm" />
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-black text-vextro-ink" htmlFor="maximum-price">
              Maximum price
            </label>
            <input id="maximum-price" name="maxPrice" type="number" min="0" step="1" value={draftFilters.maxPrice} onChange={handleFilterChange} placeholder="No maximum" className="min-h-12 rounded-xl border border-vextro-border px-4 text-sm" />
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-black text-vextro-ink" htmlFor="rating-filter">
              Minimum rating
            </label>
            <select id="rating-filter" name="minRating" value={draftFilters.minRating} onChange={handleFilterChange} className="min-h-12 rounded-xl border border-vextro-border bg-white px-4 text-sm">
              <option value="">Any rating</option>
              <option value="4">4.0 and above</option>
              <option value="4.5">4.5 and above</option>
            </select>
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-black text-vextro-ink" htmlFor="availability-filter">
              Availability
            </label>
            <select id="availability-filter" name="availability" value={draftFilters.availability} onChange={handleFilterChange} className="min-h-12 rounded-xl border border-vextro-border bg-white px-4 text-sm">
              <option value="available">Available offers</option>
              <option value="unavailable">Unavailable offers</option>
              <option value="">Any availability</option>
            </select>
          </div>

          <div className="grid gap-2">
            <label className="text-xs font-black text-vextro-ink" htmlFor="sort-products">
              Sort by
            </label>
            <select id="sort-products" name="sortBy" value={draftFilters.sortBy} onChange={handleFilterChange} className="min-h-12 rounded-xl border border-vextro-border bg-white px-4 text-sm">
              <option value="name_asc">Name A-Z</option>
              <option value="newest">Newest</option>
              <option value="price_asc">Lowest price</option>
              <option value="price_desc">Highest price</option>
              <option value="rating_desc">Highest rating</option>
            </select>
          </div>

          <div className="grid gap-2">
            <label
              className="text-xs font-black text-vextro-ink"
              htmlFor="brand-filter"
            >
              Brand
            </label>

            <select
  id="brand-filter"
  className="min-h-12 w-full cursor-pointer rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
  name="brandSlug"
  value={draftFilters.brandSlug}
  onChange={handleFilterChange}
  disabled={isLoadingFilters}
>
  <option value="">All brands</option>

  {brands.map((brand) => (
    <option
      key={brand.id}
      value={brand.slug}
    >
      {brand.name}
    </option>
  ))}
</select>
          </div>

          <button
            className="min-h-12 rounded-xl bg-vextro-primary px-5 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:bg-vextro-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
            type="submit"
            disabled={isLoadingProducts}
          >
            {isLoadingProducts
              ? "Searching..."
              : "Search"}
          </button>

          <button
            className="min-h-12 rounded-xl border border-vextro-border bg-white px-5 text-sm font-black text-vextro-muted transition hover:border-blue-200 hover:bg-blue-50 hover:text-vextro-primary disabled:cursor-not-allowed disabled:opacity-40"
            type="button"
            onClick={handleReset}
            disabled={!hasAppliedFilters}
          >
            Reset
          </button>
        </form>

        {errorMessage ? (
          <div
            className="mt-7 flex flex-col items-start justify-between gap-5 rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700 sm:flex-row sm:items-center"
            role="alert"
          >
            <div>
              <strong className="block text-sm font-black">
                Products could not be loaded
              </strong>

              <p className="mt-1 text-xs leading-5">
                {errorMessage}
              </p>
            </div>

            <button
              className="min-h-10 rounded-xl border border-red-200 bg-white px-4 text-xs font-black text-red-700 transition hover:bg-red-100"
              type="button"
              onClick={handleRetry}
            >
              Try again
            </button>
          </div>
        ) : null}

        {!errorMessage ? (
          <div className="mt-8 flex items-center justify-between gap-5">
            <div>
              <strong className="block text-sm font-black text-vextro-ink">
                {isLoadingProducts
                  ? "Loading products..."
                  : `${totalItems} product${
                      totalItems === 1 ? "" : "s"
                    } found`}
              </strong>

              <span className="mt-1 block text-xs text-vextro-muted">
                Page {page} of {totalPages}
              </span>
            </div>

            {hasAppliedFilters ? (
              <span className="rounded-full bg-blue-100 px-3 py-1.5 text-[10px] font-black uppercase tracking-wide text-vextro-primary">
                Filters applied
              </span>
            ) : null}
          </div>
        ) : null}

        {isLoadingProducts ? (
          <div className="mt-5 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {Array.from({ length: 6 }).map(
              (_, index) => (
                <div
                  className="overflow-hidden rounded-3xl border border-vextro-border bg-white"
                  key={index}
                >
                  <div className="h-64 animate-pulse bg-slate-200" />

                  <div className="grid gap-4 p-6">
                    <span className="h-3 w-2/5 animate-pulse rounded-full bg-slate-200" />
                    <span className="h-6 w-4/5 animate-pulse rounded-full bg-slate-200" />
                    <span className="h-3 w-3/5 animate-pulse rounded-full bg-slate-200" />
                    <span className="mt-4 h-8 w-1/2 animate-pulse rounded-full bg-slate-200" />
                  </div>
                </div>
              ),
            )}
          </div>
        ) : null}

        {!isLoadingProducts &&
        !errorMessage &&
        products.length > 0 ? (
          <div className="mt-5 grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {products.map((product) => (
  <ProductCard
  key={product.id}
  product={{
    ...product,
    brand_name:
      brandNameById.get(product.brand_id) ||
      "Unbranded",
    category_name:
      categoryNameById.get(
        product.category_id,
      ) || "General",
  }}
  isSelected={selectedProductIds.has(product.id)}
  compareDisabled={
    selectedProducts.length >= 3 &&
    !selectedProductIds.has(product.id)
  }
  onToggleCompare={handleToggleCompare}
/>
))}
          </div>
        ) : null}

        {!isLoadingProducts &&
        !errorMessage &&
        products.length === 0 ? (
          <div className="mt-6 grid min-h-96 place-content-center justify-items-center rounded-3xl border border-dashed border-slate-300 bg-white p-8 text-center">
            <span className="grid size-18 place-items-center rounded-3xl bg-blue-50 text-4xl text-vextro-primary">
              ⌕
            </span>

            <h2 className="mt-6 text-2xl font-black text-vextro-ink">
              No matching products found
            </h2>

            <p className="mt-3 max-w-lg text-sm leading-7 text-vextro-muted">
              Try another search term or remove the selected
              category and brand filters.
            </p>

            <button
              className="mt-6 min-h-11 rounded-xl border border-vextro-border bg-white px-5 text-sm font-black text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50"
              type="button"
              onClick={handleReset}
            >
              Clear all filters
            </button>
          </div>
        ) : null}

        {!isLoadingProducts &&
        !errorMessage &&
        products.length > 0 ? (
          <nav
            className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row"
            aria-label="Product pagination"
          >
            <button
              className="min-h-11 rounded-xl border border-vextro-border bg-white px-5 text-sm font-black text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40"
              type="button"
              onClick={() => changePage(page - 1)}
              disabled={page <= 1}
            >
              ← Previous
            </button>

            <span className="text-sm text-vextro-muted">
              Page{" "}
              <strong className="text-vextro-ink">
                {page}
              </strong>{" "}
              of{" "}
              <strong className="text-vextro-ink">
                {totalPages}
              </strong>
            </span>

            <button
              className="min-h-11 rounded-xl border border-vextro-border bg-white px-5 text-sm font-black text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40"
              type="button"
              onClick={() => changePage(page + 1)}
              disabled={page >= totalPages}
            >
              Next →
            </button>
          </nav>
        ) : null}
      </div>

        {selectedProducts.length > 0 ? (
          <div className="fixed inset-x-0 bottom-0 z-50 border-t border-vextro-border bg-white/95 px-4 py-4 shadow-[0_-12px_35px_rgba(15,23,42,0.12)] backdrop-blur">
            <div className="mx-auto flex max-w-7xl flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <div className="flex items-center gap-3">
                  <strong className="text-sm font-black text-vextro-ink">
                    Compare products
                  </strong>

                  <span className="rounded-full bg-blue-50 px-3 py-1 text-[10px] font-black text-vextro-primary">
                    {selectedProducts.length}/3 selected
                  </span>
                </div>

                <div className="mt-2 flex flex-wrap gap-2">
                  {selectedProducts.map((product) => (
                    <span
                      className="max-w-52 truncate rounded-lg bg-vextro-canvas px-3 py-2 text-xs font-bold text-vextro-ink"
                      key={product.id}
                    >
                      {product.name}
                    </span>
                  ))}
                </div>
              </div>

              <div className="flex shrink-0 items-center gap-3">
                <button
                  className="min-h-11 rounded-xl border border-vextro-border bg-white px-4 text-sm font-black text-vextro-muted transition hover:border-red-200 hover:bg-red-50 hover:text-red-700"
                  type="button"
                  onClick={handleClearComparison}
                >
                  Clear
                </button>

                {selectedProducts.length >= 2 ? (
                  <Link
                    className="inline-flex min-h-11 items-center justify-center rounded-xl bg-vextro-primary px-5 text-sm font-black text-white shadow-lg shadow-blue-500/20 transition hover:bg-vextro-primary-dark"
                    to={comparisonUrl}
                  >
                    Compare {selectedProducts.length} Products →
                  </Link>
                ) : (
                  <button
                    className="min-h-11 cursor-not-allowed rounded-xl bg-slate-200 px-5 text-sm font-black text-slate-500"
                    type="button"
                    disabled
                  >
                    Select 1 more product
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : null}
    </section>
  );
}

export default ProductsPage;
