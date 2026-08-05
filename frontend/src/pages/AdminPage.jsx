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
  getAdminUsers,
  updateAdminUserStatus,
} from "../services/adminService";
import { getApiErrorMessage } from "../utils/apiError";
import { formatDateTime } from "../utils/productDisplay";

const PAGE_SIZE = 10;

const initialFilters = {
  query: "",
  role: "",
  status: "",
};

function AdminPage() {
  const { user: currentUser } = useAuth();

  const [dashboard, setDashboard] =
    useState(null);

  const [users, setUsers] = useState([]);
  const [page, setPage] = useState(1);
  const [totalItems, setTotalItems] =
    useState(0);

  const [totalPages, setTotalPages] =
    useState(0);

  const [draftFilters, setDraftFilters] =
    useState(initialFilters);

  const [appliedFilters, setAppliedFilters] =
    useState(initialFilters);

  const [
    isLoadingDashboard,
    setIsLoadingDashboard,
  ] = useState(true);

  const [isLoadingUsers, setIsLoadingUsers] =
    useState(true);

  const [
    processingUserId,
    setProcessingUserId,
  ] = useState(null);

  const [
    dashboardError,
    setDashboardError,
  ] = useState("");

  const [usersError, setUsersError] =
    useState("");

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

  const loadUsers = useCallback(async () => {
    setIsLoadingUsers(true);
    setUsersError("");

    const params = {
      page,
      page_size: PAGE_SIZE,
    };

    const normalizedQuery =
      appliedFilters.query.trim();

    if (normalizedQuery) {
      params.q = normalizedQuery;
    }

    if (appliedFilters.role) {
      params.role = appliedFilters.role;
    }

    if (appliedFilters.status === "active") {
      params.is_active = true;
    }

    if (appliedFilters.status === "inactive") {
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

      setTotalItems(
        Number(responseData?.total_items) || 0,
      );

      setTotalPages(
        Number(responseData?.total_pages) || 0,
      );
    } catch (error) {
      setUsers([]);
      setTotalItems(0);
      setTotalPages(0);

      setUsersError(
        getApiErrorMessage(
          error,
          "Unable to load registered users.",
        ),
      );
    } finally {
      setIsLoadingUsers(false);
    }
  }, [appliedFilters, page]);

  useEffect(() => {
    loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  const statistics = useMemo(
    () => [
      {
        label: "Total Users",
        value: dashboard?.total_users ?? 0,
        description: "All registered accounts",
        icon: "👥",
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
        icon: "🛍️",
        valueClass: "text-blue-600",
      },
      {
        label: "SME Accounts",
        value: dashboard?.sme_users ?? 0,
        description: "Business intelligence users",
        icon: "🏢",
        valueClass: "text-violet-600",
      },
      {
        label: "Products",
        value:
          dashboard?.canonical_products ?? 0,
        description: `${
          dashboard?.active_products ?? 0
        } active products`,
        icon: "📦",
        valueClass: "text-amber-600",
      },
      {
        label: "Listings",
        value:
          dashboard?.marketplace_listings ?? 0,
        description: `${
          dashboard?.available_listings ?? 0
        } currently available`,
        icon: "↔",
        valueClass: "text-cyan-600",
      },
      {
        label: "Active Alerts",
        value:
          dashboard?.active_price_alerts ?? 0,
        description: `${
          dashboard?.total_price_alerts ?? 0
        } total alerts`,
        icon: "🔔",
        valueClass: "text-emerald-600",
      },
      {
        label: "Triggered Alerts",
        value:
          dashboard?.triggered_price_alerts ??
          0,
        description: "Target prices reached",
        icon: "🎯",
        valueClass: "text-rose-600",
      },
    ],
    [dashboard],
  );

  function handleFilterChange(event) {
    const { name, value } = event.target;

    setDraftFilters((currentFilters) => ({
      ...currentFilters,
      [name]: value,
    }));

    setSuccessMessage("");
  }

  function handleApplyFilters(event) {
    event.preventDefault();

    setPage(1);

    setAppliedFilters({
      query: draftFilters.query.trim(),
      role: draftFilters.role,
      status: draftFilters.status,
    });
  }

  function handleResetFilters() {
    setDraftFilters(initialFilters);
    setAppliedFilters(initialFilters);
    setPage(1);
    setSuccessMessage("");
  }

  async function handleStatusChange(targetUser) {
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

  function changePage(nextPage) {
    setPage(nextPage);

    window.scrollTo({
      top: 500,
      behavior: "smooth",
    });
  }

  const hasAppliedFilters = Boolean(
    appliedFilters.query ||
      appliedFilters.role ||
      appliedFilters.status,
  );

  if (
    isLoadingDashboard &&
    isLoadingUsers &&
    !dashboard
  ) {
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
              Monitor platform activity, review user
              accounts and manage access from one
              secure administrator workspace.
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

        <div className="mt-10 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {statistics.map((statistic) => (
            <article
              className="rounded-2xl border border-vextro-border bg-white p-5 shadow-sm transition hover:-translate-y-1 hover:border-blue-200 hover:shadow-lg"
              key={statistic.label}
            >
              <div className="flex items-center justify-between gap-4">
                <span className="text-xs font-bold text-vextro-muted">
                  {statistic.label}
                </span>

                <span className="grid size-10 place-items-center rounded-xl bg-vextro-canvas text-lg">
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

        <section className="mt-10 overflow-hidden rounded-3xl border border-vextro-border bg-white shadow-sm">
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
                  {totalItems}
                </strong>{" "}
                matching users
              </div>
            </div>

            <form
              className="mt-7 grid gap-4 lg:grid-cols-[minmax(240px,1.4fr)_minmax(150px,0.6fr)_minmax(150px,0.6fr)_auto_auto] lg:items-end"
              onSubmit={handleApplyFilters}
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
                  value={draftFilters.query}
                  onChange={handleFilterChange}
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
                  value={draftFilters.role}
                  onChange={handleFilterChange}
                >
                  <option value="">All roles</option>
                  <option value="consumer">
                    Consumer
                  </option>
                  <option value="sme">SME</option>
                  <option value="admin">
                    Admin
                  </option>
                </select>
              </div>

              <div className="grid gap-2">
                <label
                  className="text-xs font-black text-vextro-ink"
                  htmlFor="admin-status-filter"
                >
                  Status
                </label>

                <select
                  id="admin-status-filter"
                  className="min-h-12 w-full rounded-xl border border-vextro-border bg-white px-4 text-sm font-semibold text-vextro-ink outline-none transition focus:border-vextro-primary focus:ring-4 focus:ring-blue-100"
                  name="status"
                  value={draftFilters.status}
                  onChange={handleFilterChange}
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
                onClick={handleResetFilters}
                disabled={!hasAppliedFilters}
              >
                Reset
              </button>
            </form>
          </div>

          {successMessage ? (
            <div
              className="mx-6 mt-6 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-sm font-bold text-emerald-700 sm:mx-8"
              role="status"
            >
              {successMessage}
            </div>
          ) : null}

          {usersError ? (
            <div
              className="mx-6 mt-6 flex flex-col items-start justify-between gap-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-red-700 sm:mx-8 sm:flex-row sm:items-center"
              role="alert"
            >
              <span className="text-sm font-bold">
                {usersError}
              </span>

              <button
                className="rounded-xl border border-red-200 bg-white px-4 py-2 text-xs font-black"
                type="button"
                onClick={loadUsers}
              >
                Reload Users
              </button>
            </div>
          ) : null}

          {isLoadingUsers ? (
            <div className="grid gap-4 p-6 sm:p-8">
              {Array.from({ length: 5 }).map(
                (_, index) => (
                  <div
                    className="grid gap-3 rounded-2xl border border-vextro-border p-5 sm:grid-cols-[1fr_130px_130px_120px]"
                    key={index}
                  >
                    <div className="h-12 animate-pulse rounded-xl bg-slate-200" />
                    <div className="h-12 animate-pulse rounded-xl bg-slate-200" />
                    <div className="h-12 animate-pulse rounded-xl bg-slate-200" />
                    <div className="h-12 animate-pulse rounded-xl bg-slate-200" />
                  </div>
                ),
              )}
            </div>
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
                  {users.map((registeredUser) => {
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
                                {registeredUser.email}
                              </p>
                            </div>
                          </div>
                        </td>

                        <td className="px-5 py-5">
                          <div className="flex flex-wrap gap-1">
                            {registeredUser.roles.map(
                              (role) => (
                                <span
                                  className="rounded-full bg-vextro-canvas px-3 py-1.5 text-[9px] font-black uppercase text-vextro-ink"
                                  key={role}
                                >
                                  {role}
                                </span>
                              ),
                            )}
                          </div>
                        </td>

                        <td className="px-5 py-5">
                          <span
                            className={`inline-flex rounded-full px-3 py-1.5 text-[9px] font-black uppercase ${
                              registeredUser.is_active
                                ? "bg-emerald-50 text-emerald-700"
                                : "bg-red-50 text-red-700"
                            }`}
                          >
                            {registeredUser.is_active
                              ? "Active"
                              : "Inactive"}
                          </span>
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
                              handleStatusChange(
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
                  })}
                </tbody>
              </table>
            </div>
          ) : null}

          {!isLoadingUsers &&
          !usersError &&
          users.length === 0 ? (
            <div className="grid min-h-80 place-content-center justify-items-center p-8 text-center">
              <span className="grid size-18 place-items-center rounded-3xl bg-blue-50 text-3xl">
                👥
              </span>

              <h3 className="mt-5 text-xl font-black text-vextro-ink">
                No matching users found
              </h3>

              <p className="mt-2 max-w-md text-sm leading-6 text-vextro-muted">
                Change the search term or remove the
                selected role and status filters.
              </p>

              <button
                className="mt-5 rounded-xl border border-vextro-border bg-white px-5 py-3 text-sm font-black text-vextro-ink"
                type="button"
                onClick={handleResetFilters}
              >
                Clear Filters
              </button>
            </div>
          ) : null}

          {!isLoadingUsers &&
          !usersError &&
          users.length > 0 ? (
            <nav
              className="flex flex-col items-center justify-between gap-4 border-t border-vextro-border px-6 py-5 sm:flex-row sm:px-8"
              aria-label="Admin users pagination"
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
                  onClick={() =>
                    changePage(page - 1)
                  }
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
                  onClick={() =>
                    changePage(page + 1)
                  }
                >
                  Next →
                </button>
              </div>
            </nav>
          ) : null}
        </section>
      </div>
    </section>
  );
}

export default AdminPage;