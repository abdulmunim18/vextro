import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import RouteLoadingState from "../components/RouteLoadingState";
import { useAuth } from "../context/AuthContext";
import {
  getAdminDashboard,
  getAdminListings,
  getAdminProducts,
  getAdminUsers,
  updateAdminProductStatus,
  updateAdminUserStatus,
} from "../services/adminService";
import {
  getBrands,
  getCategories,
  getPlatforms,
} from "../services/catalogService";
import { getApiErrorMessage } from "../utils/apiError";
import { formatDateTime } from "../utils/productDisplay";

const PAGE_SIZE = 10;

const TABS = [
  {
    id: "overview",
    label: "Overview",
  },
  {
    id: "users",
    label: "Users",
  },
  {
    id: "products",
    label: "Products",
  },
  {
    id: "listings",
    label: "Listings",
  },
];

const initialUserFilters = {
  query: "",
  role: "",
  status: "",
};

const initialProductFilters = {
  query: "",
  categoryId: "",
  brandId: "",
  status: "",
};

const initialListingFilters = {
  query: "",
  platformId: "",
  productId: "",
  availability: "",
};

function normalizeCollection(responseData) {
  if (Array.isArray(responseData)) {
    return responseData;
  }

  if (Array.isArray(responseData?.items)) {
    return responseData.items;
  }

  return [];
}

function formatCurrency(value, currency = "PKR") {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return "—";
  }

  return new Intl.NumberFormat("en-PK", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(numericValue);
}

function getVariantLabel(listing) {
  const parts = [];

  if (listing.ram_gb) {
    parts.push(`${listing.ram_gb} GB RAM`);
  }

  if (listing.storage_gb) {
    parts.push(`${listing.storage_gb} GB`);
  }

  if (listing.color) {
    parts.push(listing.color);
  }

  return parts.length > 0
    ? parts.join(" · ")
    : listing.variant_sku || "Standard variant";
}

function TabButton({
  activeTab,
  tab,
  onSelect,
}) {
  const isActive = activeTab === tab.id;

  return (
    <button
      className={`min-h-11 whitespace-nowrap rounded-xl px-5 text-sm font-black transition ${
        isActive
          ? "bg-vextro-primary text-white shadow-sm"
          : "text-vextro-muted hover:bg-blue-50 hover:text-vextro-primary"
      }`}
      type="button"
      onClick={() => onSelect(tab.id)}
    >
      {tab.label}
    </button>
  );
}

function StatusBadge({
  isActive,
  activeLabel = "Active",
  inactiveLabel = "Inactive",
}) {
  return (
    <span
      className={`inline-flex rounded-full px-3 py-1.5 text-[9px] font-black uppercase ${
        isActive
          ? "bg-emerald-50 text-emerald-700"
          : "bg-red-50 text-red-700"
      }`}
    >
      {isActive ? activeLabel : inactiveLabel}
    </span>
  );
}

function TableSkeleton({
  columns = 5,
  rows = 5,
}) {
  return (
    <div className="grid gap-4 p-6 sm:p-8">
      {Array.from({ length: rows }).map(
        (_, rowIndex) => (
          <div
            className="grid gap-3 rounded-2xl border border-vextro-border p-5"
            key={rowIndex}
            style={{
              gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
            }}
          >
            {Array.from({ length: columns }).map(
              (_, columnIndex) => (
                <div
                  className="h-11 animate-pulse rounded-xl bg-slate-200"
                  key={columnIndex}
                />
              ),
            )}
          </div>
        ),
      )}
    </div>
  );
}

function Pagination({
  page,
  totalPages,
  onChange,
  label,
}) {
  return (
    <nav
      className="flex flex-col items-center justify-between gap-4 border-t border-vextro-border px-6 py-5 sm:flex-row sm:px-8"
      aria-label={label}
    >
      <p className="text-xs text-vextro-muted">
        Page{" "}
        <strong className="text-vextro-ink">
          {page}
        </strong>{" "}
        of{" "}
        <strong className="text-vextro-ink">
          {totalPages || 1}
        </strong>
      </p>

      <div className="flex gap-3">
        <button
          className="min-h-10 rounded-xl border border-vextro-border bg-white px-4 text-xs font-black text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40"
          type="button"
          disabled={page <= 1}
          onClick={() => onChange(page - 1)}
        >
          ← Previous
        </button>

        <button
          className="min-h-10 rounded-xl border border-vextro-border bg-white px-4 text-xs font-black text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-40"
          type="button"
          disabled={
            totalPages === 0 ||
            page >= totalPages
          }
          onClick={() => onChange(page + 1)}
        >
          Next →
        </button>
      </div>
    </nav>
  );
}

function ErrorPanel({
  message,
  actionLabel,
  onRetry,
}) {
  if (!message) {
    return null;
  }

  return (
    <div
      className="mx-6 mt-6 flex flex-col items-start justify-between gap-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700 sm:mx-8 sm:flex-row sm:items-center"
      role="alert"
    >
      <span className="text-sm font-bold">
        {message}
      </span>

      <button
        className="rounded-xl border border-red-200 bg-white px-4 py-2 text-xs font-black transition hover:bg-red-100"
        type="button"
        onClick={onRetry}
      >
        {actionLabel}
      </button>
    </div>
  );
}

function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  onAction,
}) {
  return (
    <div className="grid min-h-80 place-content-center justify-items-center p-8 text-center">
      <span className="grid size-18 place-items-center rounded-3xl bg-blue-50 text-3xl">
        {icon}
      </span>

      <h3 className="mt-5 text-xl font-black text-vextro-ink">
        {title}
      </h3>

      <p className="mt-2 max-w-md text-sm leading-6 text-vextro-muted">
        {description}
      </p>

      {onAction ? (
        <button
          className="mt-5 rounded-xl border border-vextro-border bg-white px-5 py-3 text-sm font-black text-vextro-ink transition hover:bg-blue-50"
          type="button"
          onClick={onAction}
        >
          {actionLabel}
        </button>
      ) : null}
    </div>
  );
}

function AdminPage() {
  const { user: currentUser } = useAuth();

  const [activeTab, setActiveTab] =
    useState("overview");

  const [dashboard, setDashboard] =
    useState(null);

  const [categories, setCategories] =
    useState([]);

  const [brands, setBrands] = useState([]);
  const [platforms, setPlatforms] =
    useState([]);

  const [users, setUsers] = useState([]);
  const [userPage, setUserPage] = useState(1);
  const [userTotalItems, setUserTotalItems] =
    useState(0);
  const [userTotalPages, setUserTotalPages] =
    useState(0);

  const [
    draftUserFilters,
    setDraftUserFilters,
  ] = useState(initialUserFilters);

  const [
    appliedUserFilters,
    setAppliedUserFilters,
  ] = useState(initialUserFilters);

  const [products, setProducts] = useState([]);
  const [productPage, setProductPage] =
    useState(1);

  const [
    productTotalItems,
    setProductTotalItems,
  ] = useState(0);

  const [
    productTotalPages,
    setProductTotalPages,
  ] = useState(0);

  const [
    draftProductFilters,
    setDraftProductFilters,
  ] = useState(initialProductFilters);

  const [
    appliedProductFilters,
    setAppliedProductFilters,
  ] = useState(initialProductFilters);

  const [listings, setListings] = useState([]);
  const [listingPage, setListingPage] =
    useState(1);

  const [
    listingTotalItems,
    setListingTotalItems,
  ] = useState(0);

  const [
    listingTotalPages,
    setListingTotalPages,
  ] = useState(0);

  const [
    draftListingFilters,
    setDraftListingFilters,
  ] = useState(initialListingFilters);

  const [
    appliedListingFilters,
    setAppliedListingFilters,
  ] = useState(initialListingFilters);

  const [
    isLoadingDashboard,
    setIsLoadingDashboard,
  ] = useState(true);

  const [isLoadingUsers, setIsLoadingUsers] =
    useState(false);

  const [
    isLoadingProducts,
    setIsLoadingProducts,
  ] = useState(false);

  const [
    isLoadingListings,
    setIsLoadingListings,
  ] = useState(false);

  const [
    processingUserId,
    setProcessingUserId,
  ] = useState(null);

  const [
    processingProductId,
    setProcessingProductId,
  ] = useState(null);

  const [
    dashboardError,
    setDashboardError,
  ] = useState("");

  const [usersError, setUsersError] =
    useState("");

  const [productsError, setProductsError] =
    useState("");

  const [listingsError, setListingsError] =
    useState("");

  const [
    referenceDataError,
    setReferenceDataError,
  ] = useState("");

  const [
    successMessage,
    setSuccessMessage,
  ] = useState("");

  const loadDashboard = useCallback(async () => {
    setIsLoadingDashboard(true);
    setDashboardError("");

    try {
      const responseData =
        await getAdminDashboard();

      setDashboard(responseData);
    } catch (error) {
      setDashboardError(
        getApiErrorMessage(
          error,
          "Unable to load administrator statistics.",
        ),
      );
    } finally {
      setIsLoadingDashboard(false);
    }
  }, []);

  const loadReferenceData =
    useCallback(async () => {
      setReferenceDataError("");

      try {
        const [
          categoriesResponse,
          brandsResponse,
          platformsResponse,
        ] = await Promise.all([
          getCategories(),
          getBrands(),
          getPlatforms(),
        ]);

        setCategories(
          normalizeCollection(categoriesResponse),
        );

        setBrands(
          normalizeCollection(brandsResponse),
        );

        setPlatforms(
          normalizeCollection(platformsResponse),
        );
      } catch (error) {
        setReferenceDataError(
          getApiErrorMessage(
            error,
            "Some catalog filters could not be loaded.",
          ),
        );
      }
    }, []);

  const loadUsers = useCallback(async () => {
    setIsLoadingUsers(true);
    setUsersError("");

    const params = {
      page: userPage,
      page_size: PAGE_SIZE,
    };

    const normalizedQuery =
      appliedUserFilters.query.trim();

    if (normalizedQuery) {
      params.q = normalizedQuery;
    }

    if (appliedUserFilters.role) {
      params.role = appliedUserFilters.role;
    }

    if (
      appliedUserFilters.status === "active"
    ) {
      params.is_active = true;
    }

    if (
      appliedUserFilters.status === "inactive"
    ) {
      params.is_active = false;
    }

    try {
      const responseData =
        await getAdminUsers(params);

      setUsers(
        Array.isArray(responseData?.items)
          ? responseData.items
          : [],
      );

      setUserTotalItems(
        Number(responseData?.total_items) || 0,
      );

      setUserTotalPages(
        Number(responseData?.total_pages) || 0,
      );
    } catch (error) {
      setUsers([]);
      setUserTotalItems(0);
      setUserTotalPages(0);

      setUsersError(
        getApiErrorMessage(
          error,
          "Unable to load registered users.",
        ),
      );
    } finally {
      setIsLoadingUsers(false);
    }
  }, [appliedUserFilters, userPage]);

  const loadProducts = useCallback(async () => {
    setIsLoadingProducts(true);
    setProductsError("");

    const params = {
      page: productPage,
      page_size: PAGE_SIZE,
    };

    const normalizedQuery =
      appliedProductFilters.query.trim();

    if (normalizedQuery) {
      params.q = normalizedQuery;
    }

    if (appliedProductFilters.categoryId) {
      params.category_id = Number(
        appliedProductFilters.categoryId,
      );
    }

    if (appliedProductFilters.brandId) {
      params.brand_id = Number(
        appliedProductFilters.brandId,
      );
    }

    if (
      appliedProductFilters.status ===
      "active"
    ) {
      params.is_active = true;
    }

    if (
      appliedProductFilters.status ===
      "inactive"
    ) {
      params.is_active = false;
    }

    try {
      const responseData =
        await getAdminProducts(params);

      setProducts(
        Array.isArray(responseData?.items)
          ? responseData.items
          : [],
      );

      setProductTotalItems(
        Number(responseData?.total_items) || 0,
      );

      setProductTotalPages(
        Number(responseData?.total_pages) || 0,
      );
    } catch (error) {
      setProducts([]);
      setProductTotalItems(0);
      setProductTotalPages(0);

      setProductsError(
        getApiErrorMessage(
          error,
          "Unable to load catalog products.",
        ),
      );
    } finally {
      setIsLoadingProducts(false);
    }
  }, [appliedProductFilters, productPage]);

  const loadListings = useCallback(async () => {
    setIsLoadingListings(true);
    setListingsError("");

    const params = {
      page: listingPage,
      page_size: PAGE_SIZE,
    };

    const normalizedQuery =
      appliedListingFilters.query.trim();

    if (normalizedQuery) {
      params.q = normalizedQuery;
    }

    if (
      appliedListingFilters.platformId
    ) {
      params.platform_id = Number(
        appliedListingFilters.platformId,
      );
    }

    if (appliedListingFilters.productId) {
      params.product_id = Number(
        appliedListingFilters.productId,
      );
    }

    if (
      appliedListingFilters.availability ===
      "available"
    ) {
      params.is_available = true;
    }

    if (
      appliedListingFilters.availability ===
      "unavailable"
    ) {
      params.is_available = false;
    }

    try {
      const responseData =
        await getAdminListings(params);

      setListings(
        Array.isArray(responseData?.items)
          ? responseData.items
          : [],
      );

      setListingTotalItems(
        Number(responseData?.total_items) || 0,
      );

      setListingTotalPages(
        Number(responseData?.total_pages) || 0,
      );
    } catch (error) {
      setListings([]);
      setListingTotalItems(0);
      setListingTotalPages(0);

      setListingsError(
        getApiErrorMessage(
          error,
          "Unable to load marketplace listings.",
        ),
      );
    } finally {
      setIsLoadingListings(false);
    }
  }, [appliedListingFilters, listingPage]);

  useEffect(() => {
    loadDashboard();
    loadReferenceData();
  }, [loadDashboard, loadReferenceData]);

  useEffect(() => {
    if (activeTab === "users") {
      loadUsers();
    }
  }, [activeTab, loadUsers]);

  useEffect(() => {
    if (activeTab === "products") {
      loadProducts();
    }
  }, [activeTab, loadProducts]);

  useEffect(() => {
    if (activeTab === "listings") {
      loadListings();
    }
  }, [activeTab, loadListings]);

  const statistics = useMemo(
    () => [
      {
        label: "Total Users",
        value: dashboard?.total_users ?? 0,
        description: "All registered accounts",
        icon: "U",
        valueClass: "text-vextro-primary",
      },
      {
        label: "Active Users",
        value: dashboard?.active_users ?? 0,
        description: "Accounts currently enabled",
        icon: "✓",
        valueClass: "text-emerald-600",
      },
      {
        label: "Consumers",
        value: dashboard?.consumer_users ?? 0,
        description: "Comparison and alert users",
        icon: "C",
        valueClass: "text-blue-600",
      },
      {
        label: "SME Accounts",
        value: dashboard?.sme_users ?? 0,
        description: "Business intelligence users",
        icon: "S",
        valueClass: "text-violet-600",
      },
      {
        label: "Products",
        value:
          dashboard?.canonical_products ?? 0,
        description: `${
          dashboard?.active_products ?? 0
        } active products`,
        icon: "P",
        valueClass: "text-amber-600",
      },
      {
        label: "Listings",
        value:
          dashboard?.marketplace_listings ?? 0,
        description: `${
          dashboard?.available_listings ?? 0
        } currently available`,
        icon: "L",
        valueClass: "text-cyan-600",
      },
      {
        label: "Active Alerts",
        value:
          dashboard?.active_price_alerts ?? 0,
        description: `${
          dashboard?.total_price_alerts ?? 0
        } total alerts`,
        icon: "A",
        valueClass: "text-emerald-600",
      },
      {
        label: "Triggered Alerts",
        value:
          dashboard?.triggered_price_alerts ??
          0,
        description: "Target prices reached",
        icon: "T",
        valueClass: "text-rose-600",
      },
    ],
    [dashboard],
  );

  function handleTabSelect(tabId) {
    setActiveTab(tabId);
    setSuccessMessage("");
  }

  function handleUserFilterChange(event) {
    const { name, value } = event.target;

    setDraftUserFilters((currentFilters) => ({
      ...currentFilters,
      [name]: value,
    }));

    setSuccessMessage("");
  }

  function handleApplyUserFilters(event) {
    event.preventDefault();

    setUserPage(1);

    setAppliedUserFilters({
      query: draftUserFilters.query.trim(),
      role: draftUserFilters.role,
      status: draftUserFilters.status,
    });
  }

  function handleResetUserFilters() {
    setDraftUserFilters(initialUserFilters);
    setAppliedUserFilters(initialUserFilters);
    setUserPage(1);
    setSuccessMessage("");
  }

  function handleProductFilterChange(event) {
    const { name, value } = event.target;

    setDraftProductFilters(
      (currentFilters) => ({
        ...currentFilters,
        [name]: value,
      }),
    );

    setSuccessMessage("");
  }

  function handleApplyProductFilters(event) {
    event.preventDefault();

    setProductPage(1);

    setAppliedProductFilters({
      query: draftProductFilters.query.trim(),
      categoryId:
        draftProductFilters.categoryId,
      brandId: draftProductFilters.brandId,
      status: draftProductFilters.status,
    });
  }

  function handleResetProductFilters() {
    setDraftProductFilters(
      initialProductFilters,
    );

    setAppliedProductFilters(
      initialProductFilters,
    );

    setProductPage(1);
    setSuccessMessage("");
  }

  function handleListingFilterChange(event) {
    const { name, value } = event.target;

    setDraftListingFilters(
      (currentFilters) => ({
        ...currentFilters,
        [name]: value,
      }),
    );

    setSuccessMessage("");
  }

  function handleApplyListingFilters(event) {
    event.preventDefault();

    setListingPage(1);

    setAppliedListingFilters({
      query: draftListingFilters.query.trim(),
      platformId:
        draftListingFilters.platformId,
      productId:
        draftListingFilters.productId,
      availability:
        draftListingFilters.availability,
    });
  }

  function handleResetListingFilters() {
    setDraftListingFilters(
      initialListingFilters,
    );

    setAppliedListingFilters(
      initialListingFilters,
    );

    setListingPage(1);
    setSuccessMessage("");
  }

  async function handleUserStatusChange(
    targetUser,
  ) {
    const nextStatus = !targetUser.is_active;

    if (
      targetUser.id === currentUser?.id &&
      nextStatus === false
    ) {
      setUsersError(
        "You cannot deactivate your own administrator account.",
      );

      return;
    }

    const actionLabel = nextStatus
      ? "activate"
      : "deactivate";

    const confirmed = window.confirm(
      `Are you sure you want to ${actionLabel} ${targetUser.full_name}?`,
    );

    if (!confirmed) {
      return;
    }

    setProcessingUserId(targetUser.id);
    setUsersError("");
    setSuccessMessage("");

    try {
      await updateAdminUserStatus(
        targetUser.id,
        nextStatus,
      );

      setSuccessMessage(
        `${targetUser.full_name} was ${
          nextStatus
            ? "activated"
            : "deactivated"
        } successfully.`,
      );

      await Promise.all([
        loadDashboard(),
        loadUsers(),
      ]);
    } catch (error) {
      setUsersError(
        getApiErrorMessage(
          error,
          `Unable to ${actionLabel} this user.`,
        ),
      );
    } finally {
      setProcessingUserId(null);
    }
  }

  async function handleProductStatusChange(
    targetProduct,
  ) {
    const nextStatus = !targetProduct.is_active;

    const actionLabel = nextStatus
      ? "activate"
      : "deactivate";

    const confirmed = window.confirm(
      `Are you sure you want to ${actionLabel} ${targetProduct.name}?`,
    );

    if (!confirmed) {
      return;
    }

    setProcessingProductId(targetProduct.id);
    setProductsError("");
    setSuccessMessage("");

    try {
      await updateAdminProductStatus(
        targetProduct.id,
        nextStatus,
      );

      setSuccessMessage(
        `${targetProduct.name} was ${
          nextStatus
            ? "activated"
            : "deactivated"
        } successfully.`,
      );

      await Promise.all([
        loadDashboard(),
        loadProducts(),
      ]);
    } catch (error) {
      setProductsError(
        getApiErrorMessage(
          error,
          `Unable to ${actionLabel} this product.`,
        ),
      );
    } finally {
      setProcessingProductId(null);
    }
  }

  function changePage(setPage, nextPage) {
    setPage(nextPage);

    window.scrollTo({
      top: 430,
      behavior: "smooth",
    });
  }

  const hasAppliedUserFilters = Boolean(
    appliedUserFilters.query ||
      appliedUserFilters.role ||
      appliedUserFilters.status,
  );

  const hasAppliedProductFilters = Boolean(
    appliedProductFilters.query ||
      appliedProductFilters.categoryId ||
      appliedProductFilters.brandId ||
      appliedProductFilters.status,
  );

  const hasAppliedListingFilters = Boolean(
    appliedListingFilters.query ||
      appliedListingFilters.platformId ||
      appliedListingFilters.productId ||
      appliedListingFilters.availability,
  );

  if (isLoadingDashboard && !dashboard) {
    return (
      <RouteLoadingState message="Loading the VEXTRO administrator workspace..." />
    );
  }

  return (
    <section className="relative min-h-[calc(100vh-145px)] overflow-hidden bg-vextro-canvas py-14 sm:py-16 lg:py-20">
      <div className="pointer-events-none absolute -left-48 top-16 size-[430px] rounded-full bg-blue-300/15 blur-3xl" />

      <div className="pointer-events-none absolute -right-48 top-0 size-[460px] rounded-full bg-violet-300/15 blur-3xl" />

      <div className="relative mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col items-start justify-between gap-7 lg:flex-row lg:items-end">
          <div className="max-w-3xl">
            <span className="text-xs font-black uppercase tracking-[0.18em] text-vextro-primary">
              Administration
            </span>

            <h1 className="mt-4 text-4xl font-black leading-[1.02] tracking-[-0.05em] text-vextro-ink sm:text-5xl lg:text-6xl">
              VEXTRO Admin Panel
            </h1>

            <p className="mt-5 max-w-2xl text-sm leading-7 text-vextro-muted sm:text-base">
              Monitor platform activity, manage
              users, control the product catalog and
              inspect marketplace listings from one
              secure workspace.
            </p>
          </div>

          <div className="rounded-2xl border border-vextro-border bg-white p-4 shadow-sm">
            <span className="block text-[10px] font-black uppercase tracking-wide text-vextro-muted">
              Signed in as
            </span>

            <strong className="mt-1 block text-sm font-black text-vextro-ink">
              {currentUser?.full_name}
            </strong>

            <span className="mt-1 block text-xs text-vextro-primary">
              Administrator
            </span>
          </div>
        </div>

        <div className="mt-9 overflow-x-auto rounded-2xl border border-vextro-border bg-white p-2 shadow-sm">
          <div className="flex min-w-max gap-2">
            {TABS.map((tab) => (
              <TabButton
                activeTab={activeTab}
                key={tab.id}
                tab={tab}
                onSelect={handleTabSelect}
              />
            ))}
          </div>
        </div>

        {successMessage ? (
          <div
            className="mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-bold text-emerald-700"
            role="status"
          >
            {successMessage}
          </div>
        ) : null}

        {referenceDataError ? (
          <div
            className="mt-6 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm font-bold text-amber-800"
            role="status"
          >
            {referenceDataError}
          </div>
        ) : null}

        {activeTab === "overview" ? (
          <>
            {dashboardError ? (
              <div
                className="mt-8 flex flex-col items-start justify-between gap-4 rounded-2xl border border-red-200 bg-red-50 p-5 text-red-700 sm:flex-row sm:items-center"
                role="alert"
              >
                <span className="text-sm font-bold">
                  {dashboardError}
                </span>

                <button
                  className="rounded-xl border border-red-200 bg-white px-4 py-2 text-xs font-black transition hover:bg-red-100"
                  type="button"
                  onClick={loadDashboard}
                >
                  Reload Statistics
                </button>
              </div>
            ) : null}

            <div className="mt-8 grid grid-cols-2 gap-4 lg:grid-cols-4">
              {statistics.map((statistic) => (
                <article
                  className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:border-blue-200 hover:shadow-lg"
                  key={statistic.label}
                >
                  <div className="flex items-center justify-between gap-4">
                    <span className="text-xs font-bold text-vextro-muted">
                      {statistic.label}
                    </span>

                    <span className="grid size-10 place-items-center rounded-xl bg-vextro-canvas text-sm font-black text-vextro-primary">
                      {statistic.icon}
                    </span>
                  </div>

                  {isLoadingDashboard ? (
                    <div className="mt-4 h-9 w-20 animate-pulse rounded-lg bg-slate-200" />
                  ) : (
                    <strong
                      className={`mt-4 block text-3xl font-black tracking-tight ${statistic.valueClass}`}
                    >
                      {statistic.value}
                    </strong>
                  )}

                  <p className="mt-2 text-[11px] leading-5 text-vextro-muted">
                    {statistic.description}
                  </p>
                </article>
              ))}
            </div>

            <div className="mt-8 grid gap-5 lg:grid-cols-3">
              <article className="rounded-3xl border border-vextro-border bg-white p-7 shadow-sm lg:col-span-2">
                <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
                  Platform Operations
                </span>

                <h2 className="mt-3 text-2xl font-black tracking-tight text-vextro-ink">
                  Management workspace is connected
                </h2>

                <p className="mt-3 max-w-2xl text-sm leading-7 text-vextro-muted">
                  User access, canonical products and
                  Daraz or PriceOye listings can now
                  be reviewed through role-protected
                  administrator APIs.
                </p>

                <div className="mt-6 grid gap-4 sm:grid-cols-3">
                  <button
                    className="rounded-2xl border border-vextro-border bg-vextro-canvas p-5 text-left transition hover:border-blue-200 hover:bg-blue-50"
                    type="button"
                    onClick={() =>
                      handleTabSelect("users")
                    }
                  >
                    <strong className="block text-sm font-black text-vextro-ink">
                      Manage users
                    </strong>

                    <span className="mt-2 block text-xs leading-5 text-vextro-muted">
                      Search and control account
                      access.
                    </span>
                  </button>

                  <button
                    className="rounded-2xl border border-vextro-border bg-vextro-canvas p-5 text-left transition hover:border-blue-200 hover:bg-blue-50"
                    type="button"
                    onClick={() =>
                      handleTabSelect("products")
                    }
                  >
                    <strong className="block text-sm font-black text-vextro-ink">
                      Manage products
                    </strong>

                    <span className="mt-2 block text-xs leading-5 text-vextro-muted">
                      Review catalog coverage and
                      status.
                    </span>
                  </button>

                  <button
                    className="rounded-2xl border border-vextro-border bg-vextro-canvas p-5 text-left transition hover:border-blue-200 hover:bg-blue-50"
                    type="button"
                    onClick={() =>
                      handleTabSelect("listings")
                    }
                  >
                    <strong className="block text-sm font-black text-vextro-ink">
                      Monitor listings
                    </strong>

                    <span className="mt-2 block text-xs leading-5 text-vextro-muted">
                      Inspect price and availability.
                    </span>
                  </button>
                </div>
              </article>

              <article className="rounded-3xl border border-vextro-border bg-gradient-to-br from-vextro-primary to-violet-700 p-7 text-white shadow-lg">
                <span className="text-xs font-black uppercase tracking-[0.16em] text-blue-100">
                  Current Role
                </span>

                <h2 className="mt-3 text-2xl font-black">
                  Administrator
                </h2>

                <p className="mt-3 text-sm leading-7 text-blue-100">
                  You have permission to manage users,
                  products and operational catalog
                  monitoring.
                </p>

                <button
                  className="mt-6 rounded-xl bg-white px-5 py-3 text-sm font-black text-vextro-primary transition hover:bg-blue-50"
                  type="button"
                  onClick={loadDashboard}
                >
                  Refresh dashboard
                </button>
              </article>
            </div>
          </>
        ) : null}

        {activeTab === "users" ? (
          <section className="mt-8 overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-sm">
            <div className="border-b border-vextro-border p-6 sm:p-8">
              <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
                <div>
                  <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
                    User Management
                  </span>

                  <h2 className="mt-2 text-3xl font-black tracking-tight text-vextro-ink">
                    Registered accounts
                  </h2>

                  <p className="mt-3 text-sm leading-7 text-vextro-muted">
                    Search users and control account
                    access without deleting historical
                    platform data.
                  </p>
                </div>

                <div className="rounded-xl bg-vextro-canvas px-4 py-3 text-sm text-vextro-muted">
                  <strong className="text-vextro-ink">
                    {userTotalItems}
                  </strong>{" "}
                  matching users
                </div>
              </div>

              <form
                className="mt-7 grid gap-4 lg:grid-cols-[minmax(240px,1.4fr)_minmax(150px,0.6fr)_minmax(150px,0.6fr)_auto_auto] lg:items-end"
                onSubmit={handleApplyUserFilters}
              >
                <div className="grid gap-2">
                  <label
                    className="text-xs font-black text-vextro-ink"
                    htmlFor="admin-user-search"
                  >
                    Search users
                  </label>

                  <input
                    id="admin-user-search"
                    className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition placeholder:text-slate-400 focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="query"
                    type="search"
                    value={draftUserFilters.query}
                    onChange={handleUserFilterChange}
                    placeholder="Name or email address..."
                  />
                </div>

                <div className="grid gap-2">
                  <label
                    className="text-xs font-black text-vextro-ink"
                    htmlFor="admin-role-filter"
                  >
                    Role
                  </label>

                  <select
                    id="admin-role-filter"
                    className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm font-semibold text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="role"
                    value={draftUserFilters.role}
                    onChange={handleUserFilterChange}
                  >
                    <option value="">
                      All roles
                    </option>
                    <option value="consumer">
                      Consumer
                    </option>
                    <option value="sme">
                      SME
                    </option>
                    <option value="admin">
                      Admin
                    </option>
                  </select>
                </div>

                <div className="grid gap-2">
                  <label
                    className="text-xs font-black text-vextro-ink"
                    htmlFor="admin-user-status-filter"
                  >
                    Status
                  </label>

                  <select
                    id="admin-user-status-filter"
                    className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm font-semibold text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="status"
                    value={draftUserFilters.status}
                    onChange={handleUserFilterChange}
                  >
                    <option value="">
                      All statuses
                    </option>
                    <option value="active">
                      Active
                    </option>
                    <option value="inactive">
                      Inactive
                    </option>
                  </select>
                </div>

                <button
                  className="min-h-12 rounded-xl bg-vextro-primary px-5 text-sm font-black text-white transition hover:bg-vextro-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
                  type="submit"
                  disabled={isLoadingUsers}
                >
                  {isLoadingUsers
                    ? "Loading..."
                    : "Apply Filters"}
                </button>

                <button
                  className="min-h-12 rounded-xl border border-vextro-border bg-white px-5 text-sm font-black text-vextro-muted transition hover:border-blue-200 hover:bg-blue-50 hover:text-vextro-primary disabled:cursor-not-allowed disabled:opacity-40"
                  type="button"
                  onClick={handleResetUserFilters}
                  disabled={
                    !hasAppliedUserFilters
                  }
                >
                  Reset
                </button>
              </form>
            </div>

            <ErrorPanel
              actionLabel="Reload Users"
              message={usersError}
              onRetry={loadUsers}
            />

            {isLoadingUsers ? (
              <TableSkeleton columns={5} />
            ) : null}

            {!isLoadingUsers &&
            !usersError &&
            users.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="border-b border-vextro-border bg-slate-50/80 text-left">
                      <th className="px-6 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted sm:px-8">
                        User
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Role
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Status
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Verification
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Joined
                      </th>
                      <th className="px-6 py-4 text-right text-[10px] font-black uppercase tracking-wide text-vextro-muted sm:px-8">
                        Action
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {users.map(
                      (registeredUser) => {
                        const isCurrentAdmin =
                          registeredUser.id ===
                          currentUser?.id;

                        const isProcessing =
                          processingUserId ===
                          registeredUser.id;

                        return (
                          <tr
                            className="border-b border-vextro-border last:border-b-0 hover:bg-blue-50/30"
                            key={registeredUser.id}
                          >
                            <td className="px-6 py-5 sm:px-8">
                              <div className="flex min-w-56 items-center gap-3">
                                <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-gradient-to-br from-vextro-primary to-violet-600 text-sm font-black text-white">
                                  {registeredUser.full_name
                                    .charAt(0)
                                    .toUpperCase()}
                                </span>

                                <div className="min-w-0">
                                  <div className="flex flex-wrap items-center gap-2">
                                    <strong className="truncate text-sm font-black text-vextro-ink">
                                      {
                                        registeredUser.full_name
                                      }
                                    </strong>

                                    {isCurrentAdmin ? (
                                      <span className="rounded-full bg-blue-100 px-2 py-1 text-[8px] font-black uppercase text-vextro-primary">
                                        You
                                      </span>
                                    ) : null}
                                  </div>

                                  <p className="mt-1 break-all text-xs text-vextro-muted">
                                    {
                                      registeredUser.email
                                    }
                                  </p>
                                </div>
                              </div>
                            </td>

                            <td className="px-5 py-5">
                              <div className="flex flex-wrap gap-1">
                                {Array.isArray(
                                  registeredUser.roles,
                                )
                                  ? registeredUser.roles.map(
                                      (role) => (
                                        <span
                                          className="rounded-full bg-vextro-canvas px-3 py-1.5 text-[9px] font-black uppercase text-vextro-ink"
                                          key={role}
                                        >
                                          {role}
                                        </span>
                                      ),
                                    )
                                  : null}
                              </div>
                            </td>

                            <td className="px-5 py-5">
                              <StatusBadge
                                isActive={
                                  registeredUser.is_active
                                }
                              />
                            </td>

                            <td className="px-5 py-5">
                              <span
                                className={`text-xs font-bold ${
                                  registeredUser.is_verified
                                    ? "text-emerald-600"
                                    : "text-vextro-muted"
                                }`}
                              >
                                {registeredUser.is_verified
                                  ? "✓ Verified"
                                  : "Standard"}
                              </span>
                            </td>

                            <td className="whitespace-nowrap px-5 py-5 text-xs font-semibold text-vextro-muted">
                              {formatDateTime(
                                registeredUser.created_at,
                              )}
                            </td>

                            <td className="px-6 py-5 text-right sm:px-8">
                              <button
                                className={`min-h-10 min-w-24 rounded-xl px-4 text-xs font-black transition disabled:cursor-not-allowed disabled:opacity-50 ${
                                  registeredUser.is_active
                                    ? "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                                    : "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                                }`}
                                type="button"
                                disabled={
                                  isProcessing ||
                                  (isCurrentAdmin &&
                                    registeredUser.is_active)
                                }
                                title={
                                  isCurrentAdmin
                                    ? "You cannot deactivate your own account."
                                    : undefined
                                }
                                onClick={() =>
                                  handleUserStatusChange(
                                    registeredUser,
                                  )
                                }
                              >
                                {isProcessing
                                  ? "Working..."
                                  : registeredUser.is_active
                                    ? "Deactivate"
                                    : "Activate"}
                              </button>
                            </td>
                          </tr>
                        );
                      },
                    )}
                  </tbody>
                </table>
              </div>
            ) : null}

            {!isLoadingUsers &&
            !usersError &&
            users.length === 0 ? (
              <EmptyState
                actionLabel="Clear Filters"
                description="Change the search term or remove the selected role and status filters."
                icon="U"
                title="No matching users found"
                onAction={handleResetUserFilters}
              />
            ) : null}

            {!isLoadingUsers &&
            !usersError &&
            users.length > 0 ? (
              <Pagination
                label="Admin users pagination"
                page={userPage}
                totalPages={userTotalPages}
                onChange={(nextPage) =>
                  changePage(
                    setUserPage,
                    nextPage,
                  )
                }
              />
            ) : null}
          </section>
        ) : null}

        {activeTab === "products" ? (
          <section className="mt-8 overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-sm">
            <div className="border-b border-vextro-border p-6 sm:p-8">
              <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
                <div>
                  <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
                    Catalog Management
                  </span>

                  <h2 className="mt-2 text-3xl font-black tracking-tight text-vextro-ink">
                    Canonical products
                  </h2>

                  <p className="mt-3 text-sm leading-7 text-vextro-muted">
                    Review normalized products,
                    marketplace coverage and active
                    catalog status.
                  </p>
                </div>

                <div className="rounded-xl bg-vextro-canvas px-4 py-3 text-sm text-vextro-muted">
                  <strong className="text-vextro-ink">
                    {productTotalItems}
                  </strong>{" "}
                  matching products
                </div>
              </div>

              <form
                className="mt-7 grid gap-4 xl:grid-cols-[minmax(230px,1.3fr)_minmax(145px,0.7fr)_minmax(145px,0.7fr)_minmax(140px,0.6fr)_auto_auto] xl:items-end"
                onSubmit={handleApplyProductFilters}
              >
                <div className="grid gap-2">
                  <label
                    className="text-xs font-black text-vextro-ink"
                    htmlFor="admin-product-search"
                  >
                    Search products
                  </label>

                  <input
                    id="admin-product-search"
                    className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition placeholder:text-slate-400 focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="query"
                    type="search"
                    value={
                      draftProductFilters.query
                    }
                    onChange={
                      handleProductFilterChange
                    }
                    placeholder="Name, model or brand..."
                  />
                </div>

                <div className="grid gap-2">
                  <label
                    className="text-xs font-black text-vextro-ink"
                    htmlFor="admin-category-filter"
                  >
                    Category
                  </label>

                  <select
                    id="admin-category-filter"
                    className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm font-semibold text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="categoryId"
                    value={
                      draftProductFilters.categoryId
                    }
                    onChange={
                      handleProductFilterChange
                    }
                  >
                    <option value="">
                      All categories
                    </option>

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
                    htmlFor="admin-brand-filter"
                  >
                    Brand
                  </label>

                  <select
                    id="admin-brand-filter"
                    className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm font-semibold text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="brandId"
                    value={
                      draftProductFilters.brandId
                    }
                    onChange={
                      handleProductFilterChange
                    }
                  >
                    <option value="">
                      All brands
                    </option>

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

                <div className="grid gap-2">
                  <label
                    className="text-xs font-black text-vextro-ink"
                    htmlFor="admin-product-status-filter"
                  >
                    Status
                  </label>

                  <select
                    id="admin-product-status-filter"
                    className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm font-semibold text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="status"
                    value={
                      draftProductFilters.status
                    }
                    onChange={
                      handleProductFilterChange
                    }
                  >
                    <option value="">
                      All statuses
                    </option>
                    <option value="active">
                      Active
                    </option>
                    <option value="inactive">
                      Inactive
                    </option>
                  </select>
                </div>

                <button
                  className="min-h-12 rounded-xl bg-vextro-primary px-5 text-sm font-black text-white transition hover:bg-vextro-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
                  type="submit"
                  disabled={isLoadingProducts}
                >
                  {isLoadingProducts
                    ? "Loading..."
                    : "Apply Filters"}
                </button>

                <button
                  className="min-h-12 rounded-xl border border-vextro-border bg-white px-5 text-sm font-black text-vextro-muted transition hover:border-blue-200 hover:bg-blue-50 hover:text-vextro-primary disabled:cursor-not-allowed disabled:opacity-40"
                  type="button"
                  onClick={
                    handleResetProductFilters
                  }
                  disabled={
                    !hasAppliedProductFilters
                  }
                >
                  Reset
                </button>
              </form>
            </div>

            <ErrorPanel
              actionLabel="Reload Products"
              message={productsError}
              onRetry={loadProducts}
            />

            {isLoadingProducts ? (
              <TableSkeleton columns={5} />
            ) : null}

            {!isLoadingProducts &&
            !productsError &&
            products.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="border-b border-vextro-border bg-slate-50/80 text-left">
                      <th className="px-6 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted sm:px-8">
                        Product
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Category / Brand
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Coverage
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Status
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Updated
                      </th>
                      <th className="px-6 py-4 text-right text-[10px] font-black uppercase tracking-wide text-vextro-muted sm:px-8">
                        Action
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {products.map((product) => {
                      const isProcessing =
                        processingProductId ===
                        product.id;

                      return (
                        <tr
                          className="border-b border-vextro-border last:border-b-0 hover:bg-blue-50/30"
                          key={product.id}
                        >
                          <td className="px-6 py-5 sm:px-8">
                            <div className="min-w-60">
                              <strong className="block text-sm font-black text-vextro-ink">
                                {product.name}
                              </strong>

                              <p className="mt-1 text-xs text-vextro-muted">
                                {product.model ||
                                  "No model"}{" "}
                                · ID {product.id}
                              </p>
                            </div>
                          </td>

                          <td className="px-5 py-5">
                            <strong className="block text-xs font-black text-vextro-ink">
                              {product.category_name}
                            </strong>

                            <span className="mt-1 block text-xs text-vextro-muted">
                              {product.brand_name ||
                                "Unbranded"}
                            </span>
                          </td>

                          <td className="px-5 py-5">
                            <div className="grid min-w-40 gap-1 text-xs text-vextro-muted">
                              <span>
                                <strong className="text-vextro-ink">
                                  {
                                    product.variant_count
                                  }
                                </strong>{" "}
                                variants
                              </span>

                              <span>
                                <strong className="text-vextro-ink">
                                  {
                                    product.listing_count
                                  }
                                </strong>{" "}
                                listings
                              </span>

                              <span className="text-emerald-600">
                                {
                                  product.available_listing_count
                                }{" "}
                                available
                              </span>
                            </div>
                          </td>

                          <td className="px-5 py-5">
                            <StatusBadge
                              isActive={
                                product.is_active
                              }
                            />
                          </td>

                          <td className="whitespace-nowrap px-5 py-5 text-xs font-semibold text-vextro-muted">
                            {formatDateTime(
                              product.updated_at,
                            )}
                          </td>

                          <td className="px-6 py-5 text-right sm:px-8">
                            <button
                              className={`min-h-10 min-w-24 rounded-xl px-4 text-xs font-black transition disabled:cursor-not-allowed disabled:opacity-50 ${
                                product.is_active
                                  ? "border border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                                  : "border border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100"
                              }`}
                              type="button"
                              disabled={isProcessing}
                              onClick={() =>
                                handleProductStatusChange(
                                  product,
                                )
                              }
                            >
                              {isProcessing
                                ? "Working..."
                                : product.is_active
                                  ? "Deactivate"
                                  : "Activate"}
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            ) : null}

            {!isLoadingProducts &&
            !productsError &&
            products.length === 0 ? (
              <EmptyState
                actionLabel="Clear Filters"
                description="Change the search term or remove the category, brand and status filters."
                icon="P"
                title="No matching products found"
                onAction={
                  handleResetProductFilters
                }
              />
            ) : null}

            {!isLoadingProducts &&
            !productsError &&
            products.length > 0 ? (
              <Pagination
                label="Admin products pagination"
                page={productPage}
                totalPages={productTotalPages}
                onChange={(nextPage) =>
                  changePage(
                    setProductPage,
                    nextPage,
                  )
                }
              />
            ) : null}
          </section>
        ) : null}

        {activeTab === "listings" ? (
          <section className="mt-8 overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-sm">
            <div className="border-b border-vextro-border p-6 sm:p-8">
              <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
                <div>
                  <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
                    Marketplace Monitoring
                  </span>

                  <h2 className="mt-2 text-3xl font-black tracking-tight text-vextro-ink">
                    Daraz and PriceOye listings
                  </h2>

                  <p className="mt-3 text-sm leading-7 text-vextro-muted">
                    Monitor seller, pricing,
                    availability, rating and last-seen
                    information across supported
                    platforms.
                  </p>
                </div>

                <div className="rounded-xl bg-vextro-canvas px-4 py-3 text-sm text-vextro-muted">
                  <strong className="text-vextro-ink">
                    {listingTotalItems}
                  </strong>{" "}
                  matching listings
                </div>
              </div>

              <form
                className="mt-7 grid gap-4 xl:grid-cols-[minmax(230px,1.3fr)_minmax(150px,0.65fr)_minmax(140px,0.55fr)_minmax(150px,0.65fr)_auto_auto] xl:items-end"
                onSubmit={handleApplyListingFilters}
              >
                <div className="grid gap-2">
                  <label
                    className="text-xs font-black text-vextro-ink"
                    htmlFor="admin-listing-search"
                  >
                    Search listings
                  </label>

                  <input
                    id="admin-listing-search"
                    className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition placeholder:text-slate-400 focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="query"
                    type="search"
                    value={
                      draftListingFilters.query
                    }
                    onChange={
                      handleListingFilterChange
                    }
                    placeholder="Listing, product or seller..."
                  />
                </div>

                <div className="grid gap-2">
                  <label
                    className="text-xs font-black text-vextro-ink"
                    htmlFor="admin-platform-filter"
                  >
                    Platform
                  </label>

                  <select
                    id="admin-platform-filter"
                    className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm font-semibold text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="platformId"
                    value={
                      draftListingFilters.platformId
                    }
                    onChange={
                      handleListingFilterChange
                    }
                  >
                    <option value="">
                      All platforms
                    </option>

                    {platforms.map((platform) => (
                      <option
                        key={platform.id}
                        value={platform.id}
                      >
                        {platform.name}
                      </option>
                    ))}
                  </select>
                </div>

                <div className="grid gap-2">
                  <label
                    className="text-xs font-black text-vextro-ink"
                    htmlFor="admin-listing-product-id"
                  >
                    Product ID
                  </label>

                  <input
                    id="admin-listing-product-id"
                    className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm text-vextro-ink outline-none transition placeholder:text-slate-400 focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    min="1"
                    name="productId"
                    type="number"
                    value={
                      draftListingFilters.productId
                    }
                    onChange={
                      handleListingFilterChange
                    }
                    placeholder="Any"
                  />
                </div>

                <div className="grid gap-2">
                  <label
                    className="text-xs font-black text-vextro-ink"
                    htmlFor="admin-availability-filter"
                  >
                    Availability
                  </label>

                  <select
                    id="admin-availability-filter"
                    className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm font-semibold text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                    name="availability"
                    value={
                      draftListingFilters.availability
                    }
                    onChange={
                      handleListingFilterChange
                    }
                  >
                    <option value="">
                      All listings
                    </option>
                    <option value="available">
                      Available
                    </option>
                    <option value="unavailable">
                      Unavailable
                    </option>
                  </select>
                </div>

                <button
                  className="min-h-12 rounded-xl bg-vextro-primary px-5 text-sm font-black text-white transition hover:bg-vextro-primary-dark disabled:cursor-not-allowed disabled:opacity-60"
                  type="submit"
                  disabled={isLoadingListings}
                >
                  {isLoadingListings
                    ? "Loading..."
                    : "Apply Filters"}
                </button>

                <button
                  className="min-h-12 rounded-xl border border-vextro-border bg-white px-5 text-sm font-black text-vextro-muted transition hover:border-blue-200 hover:bg-blue-50 hover:text-vextro-primary disabled:cursor-not-allowed disabled:opacity-40"
                  type="button"
                  onClick={
                    handleResetListingFilters
                  }
                  disabled={
                    !hasAppliedListingFilters
                  }
                >
                  Reset
                </button>
              </form>
            </div>

            <ErrorPanel
              actionLabel="Reload Listings"
              message={listingsError}
              onRetry={loadListings}
            />

            {isLoadingListings ? (
              <TableSkeleton columns={5} />
            ) : null}

            {!isLoadingListings &&
            !listingsError &&
            listings.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full border-collapse">
                  <thead>
                    <tr className="border-b border-vextro-border bg-slate-50/80 text-left">
                      <th className="px-6 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted sm:px-8">
                        Listing
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Platform / Seller
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Price
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Rating
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Availability
                      </th>
                      <th className="px-5 py-4 text-[10px] font-black uppercase tracking-wide text-vextro-muted">
                        Last Seen
                      </th>
                      <th className="px-6 py-4 text-right text-[10px] font-black uppercase tracking-wide text-vextro-muted sm:px-8">
                        Link
                      </th>
                    </tr>
                  </thead>

                  <tbody>
                    {listings.map((listing) => (
                      <tr
                        className="border-b border-vextro-border last:border-b-0 hover:bg-blue-50/30"
                        key={listing.id}
                      >
                        <td className="px-6 py-5 sm:px-8">
                          <div className="min-w-72">
                            <strong className="line-clamp-2 text-sm font-black leading-5 text-vextro-ink">
                              {listing.title}
                            </strong>

                            <p className="mt-2 text-xs text-vextro-muted">
                              {listing.product_name}
                            </p>

                            <p className="mt-1 text-[10px] font-bold text-vextro-muted">
                              {getVariantLabel(
                                listing,
                              )}
                            </p>
                          </div>
                        </td>

                        <td className="px-5 py-5">
                          <span className="inline-flex rounded-full bg-blue-50 px-3 py-1.5 text-[9px] font-black uppercase text-vextro-primary">
                            {listing.platform_name}
                          </span>

                          <strong className="mt-2 block min-w-36 text-xs font-black text-vextro-ink">
                            {listing.seller_name ||
                              "Marketplace seller"}
                          </strong>

                          {listing.seller_is_verified ? (
                            <span className="mt-1 block text-[10px] font-bold text-emerald-600">
                              ✓ Verified seller
                            </span>
                          ) : null}
                        </td>

                        <td className="px-5 py-5">
                          <strong className="whitespace-nowrap text-sm font-black text-vextro-ink">
                            {formatCurrency(
                              listing.current_price,
                              listing.currency,
                            )}
                          </strong>

                          {listing.original_price ? (
                            <span className="mt-1 block whitespace-nowrap text-[10px] text-vextro-muted line-through">
                              {formatCurrency(
                                listing.original_price,
                                listing.currency,
                              )}
                            </span>
                          ) : null}
                        </td>

                        <td className="px-5 py-5">
                          <strong className="text-sm font-black text-amber-600">
                            {listing.rating
                              ? `${Number(
                                  listing.rating,
                                ).toFixed(1)} ★`
                              : "—"}
                          </strong>

                          <span className="mt-1 block text-[10px] text-vextro-muted">
                            {
                              listing.review_count
                            }{" "}
                            reviews
                          </span>
                        </td>

                        <td className="px-5 py-5">
                          <StatusBadge
                            activeLabel="Available"
                            inactiveLabel="Unavailable"
                            isActive={
                              listing.is_available
                            }
                          />
                        </td>

                        <td className="whitespace-nowrap px-5 py-5 text-xs font-semibold text-vextro-muted">
                          {formatDateTime(
                            listing.last_seen_at,
                          )}
                        </td>

                        <td className="px-6 py-5 text-right sm:px-8">
                          <a
                            className="inline-flex min-h-10 items-center rounded-xl border border-blue-200 bg-blue-50 px-4 text-xs font-black text-vextro-primary transition hover:bg-blue-100"
                            href={listing.product_url}
                            target="_blank"
                            rel="noreferrer"
                          >
                            Open listing
                          </a>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : null}

            {!isLoadingListings &&
            !listingsError &&
            listings.length === 0 ? (
              <EmptyState
                actionLabel="Clear Filters"
                description="Change the search term or remove the platform, product and availability filters."
                icon="L"
                title="No matching listings found"
                onAction={
                  handleResetListingFilters
                }
              />
            ) : null}

            {!isLoadingListings &&
            !listingsError &&
            listings.length > 0 ? (
              <Pagination
                label="Admin listings pagination"
                page={listingPage}
                totalPages={listingTotalPages}
                onChange={(nextPage) =>
                  changePage(
                    setListingPage,
                    nextPage,
                  )
                }
              />
            ) : null}
          </section>
        ) : null}
      </div>
    </section>
  );
}

export default AdminPage;