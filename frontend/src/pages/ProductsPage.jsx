import {
  useCallback,
  useEffect,
  useState,
} from "react";

import ProductCard from "../components/ProductCard";
import {
  getBrands,
  getCategories,
  getProducts,
} from "../services/catalogService";
import { getApiErrorMessage } from "../utils/apiError";

const PAGE_SIZE = 12;

const initialFilters = {
  query: "",
  categoryId: "",
  brandId: "",
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
  const [categories, setCategories] = useState([]);
  const [brands, setBrands] = useState([]);

  const [page, setPage] = useState(1);
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
        const [categoryData, brandData] =
          await Promise.all([
            getCategories(),
            getBrands(),
          ]);

        if (!isMounted) {
          return;
        }

        setCategories(extractItems(categoryData));
        setBrands(extractItems(brandData));
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

  const loadProducts = useCallback(async () => {
    setIsLoadingProducts(true);
    setErrorMessage("");

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

    if (appliedFilters.categoryId) {
      params.category_id = Number(
        appliedFilters.categoryId,
      );
    }

    if (appliedFilters.brandId) {
      params.brand_id = Number(
        appliedFilters.brandId,
      );
    }

    try {
      const responseData = await getProducts(params);
      const responseItems = extractItems(responseData);

      const responseTotalItems = Number(
        responseData?.total_items ??
          responseData?.total ??
          responseItems.length,
      );

      const responseTotalPages = Number(
        responseData?.total_pages ??
          responseData?.pages ??
          Math.ceil(responseTotalItems / PAGE_SIZE),
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
    } catch (error) {
      setProducts([]);
      setTotalItems(0);
      setTotalPages(1);

      setErrorMessage(
        getApiErrorMessage(
          error,
          "Unable to load marketplace products.",
        ),
      );
    } finally {
      setIsLoadingProducts(false);
    }
  }, [appliedFilters, page]);

  useEffect(() => {
    loadProducts();
  }, [loadProducts]);

  function handleFilterChange(event) {
    const { name, value } = event.target;

    setDraftFilters((currentFilters) => ({
      ...currentFilters,
      [name]: value,
    }));
  }

  function handleSearch(event) {
    event.preventDefault();

    setPage(1);

    setAppliedFilters({
      query: draftFilters.query.trim(),
      categoryId: draftFilters.categoryId,
      brandId: draftFilters.brandId,
    });
  }

  function handleReset() {
    setDraftFilters(initialFilters);
    setAppliedFilters(initialFilters);
    setPage(1);
  }

  function changePage(nextPage) {
    setPage(nextPage);

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }

  const hasAppliedFilters = Boolean(
    appliedFilters.query ||
      appliedFilters.categoryId ||
      appliedFilters.brandId,
  );

  return (
    <section className="relative min-h-[calc(100vh-145px)] overflow-hidden bg-vextro-canvas py-14 sm:py-18 lg:py-20">
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
          className="mt-10 grid gap-4 rounded-3xl border border-vextro-border bg-white p-5 shadow-sm lg:grid-cols-[minmax(260px,1.6fr)_minmax(170px,0.7fr)_minmax(170px,0.7fr)_auto_auto] lg:items-end"
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
              name="categoryId"
              value={draftFilters.categoryId}
              onChange={handleFilterChange}
              disabled={isLoadingFilters}
            >
              <option value="">All categories</option>

              {categories.map((category) => (
                <option
                  key={category.id}
                  value={category.id}
                >
                  {category.name}
                </option>
              ))}
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
              name="brandId"
              value={draftFilters.brandId}
              onChange={handleFilterChange}
              disabled={isLoadingFilters}
            >
              <option value="">All brands</option>

              {brands.map((brand) => (
                <option
                  key={brand.id}
                  value={brand.id}
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
              onClick={loadProducts}
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
                product={product}
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
    </section>
  );
}

export default ProductsPage;