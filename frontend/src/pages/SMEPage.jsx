import { useCallback, useEffect, useMemo, useState } from "react";
import SMEBusinessProducts from "../components/SMEBusinessProducts";
import SMECompetitorWatchlist from "../components/SMECompetitorWatchlist";
import SMESalesImport from "../components/SMESalesImport";
import SMESalesAnalytics from "../components/SMESalesAnalytics";
import {
  createOrganization,
  getOrganizations,
} from "../services/smeService";

const initialOrganizationForm = {
  name: "",
  industry: "",
};

function getApiErrorMessage(error) {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (
    detail &&
    typeof detail === "object" &&
    typeof detail.message === "string"
  ) {
    return detail.message;
  }

  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((item) => item?.msg)
      .filter(Boolean)
      .join(" ");
  }

  return (
    error?.message ||
    "Something went wrong while communicating with the server."
  );
}

function formatDate(value) {
  if (!value) {
    return "Not available";
  }

  return new Intl.DateTimeFormat("en-PK", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function LoadingState() {
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      {[1, 2, 3].map((item) => (
        <div
          key={item}
          className="animate-pulse rounded-3xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <div className="h-4 w-28 rounded-full bg-slate-200" />
          <div className="mt-5 h-8 w-48 rounded-lg bg-slate-200" />
          <div className="mt-4 h-4 w-full rounded-full bg-slate-100" />
          <div className="mt-2 h-4 w-3/4 rounded-full bg-slate-100" />
          <div className="mt-8 h-11 rounded-xl bg-slate-200" />
        </div>
      ))}
    </div>
  );
}

function OrganizationForm({
  form,
  setForm,
  onSubmit,
  isSubmitting,
  submitError,
  compact = false,
}) {
  function handleChange(event) {
    const { name, value } = event.target;

    setForm((currentForm) => ({
      ...currentForm,
      [name]: value,
    }));
  }

  return (
    <form
      className={
        compact
          ? "space-y-5"
          : "mx-auto mt-8 max-w-2xl space-y-6"
      }
      onSubmit={onSubmit}
    >
      <div>
        <label
          className="mb-2 block text-sm font-bold text-slate-800"
          htmlFor={compact ? "organization-name-small" : "organization-name"}
        >
          Business name
        </label>

        <input
          id={compact ? "organization-name-small" : "organization-name"}
          name="name"
          type="text"
          required
          minLength={2}
          maxLength={180}
          value={form.name}
          onChange={handleChange}
          placeholder="Example: Munim Mobile Store"
          className="min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-sm font-medium text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
        />

        <p className="mt-2 text-xs leading-5 text-slate-500">
          Ye naam SME dashboard aur business reports mein show hoga.
        </p>
      </div>

      <div>
        <label
          className="mb-2 block text-sm font-bold text-slate-800"
          htmlFor={compact ? "industry-small" : "industry"}
        >
          Industry
          <span className="ml-1 font-medium text-slate-400">
            optional
          </span>
        </label>

        <input
          id={compact ? "industry-small" : "industry"}
          name="industry"
          type="text"
          maxLength={120}
          value={form.industry}
          onChange={handleChange}
          placeholder="Example: Mobile Retail"
          className="min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-sm font-medium text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
        />
      </div>

      {submitError ? (
        <div
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold leading-6 text-red-700"
          role="alert"
        >
          {submitError}
        </div>
      ) : null}

      <button
        type="submit"
        disabled={isSubmitting}
        className="inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-blue-600 px-5 text-sm font-black text-white shadow-lg shadow-blue-600/20 transition hover:-translate-y-0.5 hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:translate-y-0"
      >
        {isSubmitting
          ? "Creating organization..."
          : "Create business organization"}
      </button>
    </form>
  );
}

function EmptyOrganizationState({
  form,
  setForm,
  onSubmit,
  isSubmitting,
  submitError,
}) {
  return (
    <section className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="grid lg:grid-cols-[0.9fr_1.1fr]">
        <div className="bg-slate-950 p-8 text-white sm:p-10 lg:p-12">
          <div className="inline-flex rounded-full border border-white/15 bg-white/10 px-4 py-2 text-xs font-black uppercase tracking-[0.18em] text-blue-200">
            Business setup
          </div>

          <h2 className="mt-7 text-3xl font-black tracking-[-0.04em] sm:text-4xl">
            Create your SME workspace
          </h2>

          <p className="mt-5 max-w-xl text-sm leading-7 text-slate-300 sm:text-base">
            Apni organization create karne ke baad tum business
            products add kar sako ge, competitor marketplace listings
            monitor kar sako ge aur pricing intelligence dashboard use
            kar sako ge.
          </p>

          <div className="mt-9 space-y-4">
            {[
              "Manage your own products and stock",
              "Monitor Daraz and PriceOye competitors",
              "Compare selling price with market price",
            ].map((feature, index) => (
              <div
                key={feature}
                className="flex items-start gap-4 rounded-2xl border border-white/10 bg-white/5 p-4"
              >
                <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-xl bg-blue-500 text-sm font-black text-white">
                  {index + 1}
                </span>

                <p className="pt-1 text-sm font-bold leading-6 text-slate-100">
                  {feature}
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="p-8 sm:p-10 lg:p-12">
          <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">
            Organization details
          </p>

          <h3 className="mt-3 text-2xl font-black tracking-[-0.03em] text-slate-950">
            Tell VEXTRO about your business
          </h3>

          <p className="mt-3 text-sm leading-7 text-slate-500">
            Abhi sirf basic information required hai. Products aur
            competitors aglay steps mein add honge.
          </p>

          <OrganizationForm
            form={form}
            setForm={setForm}
            onSubmit={onSubmit}
            isSubmitting={isSubmitting}
            submitError={submitError}
          />
        </div>
      </div>
    </section>
  );
}

function OrganizationCard({
  organization,
  isSelected,
  onSelect,
}) {
  return (
    <button
      type="button"
      onClick={() => onSelect(organization.id)}
      className={[
        "w-full rounded-3xl border p-6 text-left shadow-sm transition",
        isSelected
          ? "border-blue-500 bg-blue-50 ring-4 ring-blue-100"
          : "border-slate-200 bg-white hover:-translate-y-1 hover:border-blue-200 hover:shadow-lg",
      ].join(" ")}
    >
      <div className="flex items-start justify-between gap-4">
        <div className="inline-flex size-12 items-center justify-center rounded-2xl bg-slate-950 text-lg font-black text-white">
          {organization.name
            .split(" ")
            .slice(0, 2)
            .map((word) => word[0])
            .join("")
            .toUpperCase()}
        </div>

        <span
          className={[
            "rounded-full px-3 py-1 text-xs font-black",
            organization.is_active
              ? "bg-emerald-100 text-emerald-700"
              : "bg-slate-100 text-slate-500",
          ].join(" ")}
        >
          {organization.is_active ? "Active" : "Inactive"}
        </span>
      </div>

      <h3 className="mt-6 text-xl font-black tracking-[-0.03em] text-slate-950">
        {organization.name}
      </h3>

      <p className="mt-2 min-h-6 text-sm font-semibold text-slate-500">
        {organization.industry || "Industry not specified"}
      </p>

      <div className="mt-6 border-t border-slate-200 pt-5">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">
          Created
        </p>

        <p className="mt-2 text-sm font-bold text-slate-700">
          {formatDate(organization.created_at)}
        </p>
      </div>

      <div
        className={[
          "mt-6 flex min-h-11 items-center justify-center rounded-xl text-sm font-black",
          isSelected
            ? "bg-blue-600 text-white"
            : "bg-slate-100 text-slate-700",
        ].join(" ")}
      >
        {isSelected ? "Selected workspace" : "Select workspace"}
      </div>
    </button>
  );
}

function SelectedOrganizationPanel({ organization }) {
  const upcomingModules = [
    {
      label: "Business Products",
      description:
        "Add your products, selling price, cost and inventory levels.",
    },
    {
      label: "Competitor Watchlist",
      description:
        "Connect Daraz and PriceOye listings with your own products.",
    },
    {
      label: "Pricing Gap",
      description:
        "Compare your price with current marketplace competition.",
    },
  ];

  return (
    <section className="mt-8 rounded-3xl border border-slate-200 bg-slate-950 p-7 text-white shadow-xl shadow-slate-950/10 sm:p-9">
      <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-300">
            Active workspace
          </p>

          <h2 className="mt-3 text-3xl font-black tracking-[-0.04em]">
            {organization.name}
          </h2>

          <p className="mt-3 text-sm leading-7 text-slate-300">
            {organization.industry ||
              "No industry has been specified for this organization."}
          </p>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/5 px-5 py-4">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-slate-400">
            Workspace slug
          </p>

          <p className="mt-2 text-sm font-black text-white">
            {organization.slug}
          </p>
        </div>
      </div>

      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {upcomingModules.map((module, index) => (
          <div
            key={module.label}
            className="rounded-2xl border border-white/10 bg-white/5 p-5"
          >
            <span className="inline-flex size-9 items-center justify-center rounded-xl bg-blue-600 text-sm font-black">
              {index + 1}
            </span>

            <h3 className="mt-5 text-base font-black">
              {module.label}
            </h3>

            <p className="mt-2 text-sm leading-6 text-slate-400">
              {module.description}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function SMEPage() {
  const [organizations, setOrganizations] = useState([]);
  const [selectedOrganizationId, setSelectedOrganizationId] =
    useState(null);

  const [organizationForm, setOrganizationForm] = useState(
    initialOrganizationForm,
  );

  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const [loadError, setLoadError] = useState("");
  const [submitError, setSubmitError] = useState("");

  const loadOrganizations = useCallback(async () => {
    setIsLoading(true);
    setLoadError("");

    try {
      const data = await getOrganizations();
      const loadedOrganizations = Array.isArray(data?.items)
        ? data.items
        : [];

      setOrganizations(loadedOrganizations);

      setSelectedOrganizationId((currentId) => {
        const currentOrganizationStillExists =
          loadedOrganizations.some(
            (organization) => organization.id === currentId,
          );

        if (currentOrganizationStillExists) {
          return currentId;
        }

        return loadedOrganizations[0]?.id ?? null;
      });
    } catch (error) {
      setLoadError(getApiErrorMessage(error));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOrganizations();
  }, [loadOrganizations]);

  const selectedOrganization = useMemo(
    () =>
      organizations.find(
        (organization) =>
          organization.id === selectedOrganizationId,
      ) ?? null,
    [organizations, selectedOrganizationId],
  );

  async function handleCreateOrganization(event) {
    event.preventDefault();

    const normalizedName = organizationForm.name.trim();
    const normalizedIndustry = organizationForm.industry.trim();

    if (normalizedName.length < 2) {
      setSubmitError(
        "Business name must contain at least 2 characters.",
      );
      return;
    }

    setIsSubmitting(true);
    setSubmitError("");

    try {
      const createdOrganization = await createOrganization({
        name: normalizedName,
        industry: normalizedIndustry || null,
      });

      setOrganizations((currentOrganizations) => [
        createdOrganization,
        ...currentOrganizations,
      ]);

      setSelectedOrganizationId(createdOrganization.id);
      setOrganizationForm(initialOrganizationForm);
    } catch (error) {
      setSubmitError(getApiErrorMessage(error));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-50">
      <section className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8 lg:py-14">
          <div className="flex flex-col gap-7 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <div className="inline-flex items-center gap-2 rounded-full border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-black uppercase tracking-[0.16em] text-blue-700">
                <span className="size-2 rounded-full bg-blue-600" />
                SME Business Intelligence
              </div>

              <h1 className="mt-6 max-w-3xl text-4xl font-black tracking-[-0.05em] text-slate-950 sm:text-5xl">
                Manage your business with market intelligence.
              </h1>

              <p className="mt-5 max-w-3xl text-base leading-8 text-slate-600">
                Create your organization, manage business products and
                monitor marketplace competitors through one connected
                workspace.
              </p>
            </div>

            {!isLoading && organizations.length > 0 ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-6 py-5">
                <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">
                  Organizations
                </p>

                <p className="mt-2 text-3xl font-black text-slate-950">
                  {organizations.length}
                </p>
              </div>
            ) : null}
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-7xl px-4 py-10 sm:px-6 lg:px-8">
        {isLoading ? <LoadingState /> : null}

        {!isLoading && loadError ? (
          <section className="rounded-3xl border border-red-200 bg-white p-8 text-center shadow-sm">
            <div className="mx-auto inline-flex size-14 items-center justify-center rounded-2xl bg-red-100 text-xl font-black text-red-700">
              !
            </div>

            <h2 className="mt-5 text-2xl font-black text-slate-950">
              Organizations could not be loaded
            </h2>

            <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-slate-600">
              {loadError}
            </p>

            <button
              type="button"
              onClick={loadOrganizations}
              className="mt-6 inline-flex min-h-11 items-center justify-center rounded-xl bg-slate-950 px-6 text-sm font-black text-white transition hover:bg-slate-800"
            >
              Try again
            </button>
          </section>
        ) : null}

        {!isLoading &&
        !loadError &&
        organizations.length === 0 ? (
          <EmptyOrganizationState
            form={organizationForm}
            setForm={setOrganizationForm}
            onSubmit={handleCreateOrganization}
            isSubmitting={isSubmitting}
            submitError={submitError}
          />
        ) : null}

        {!isLoading &&
        !loadError &&
        organizations.length > 0 ? (
          <>
            <section>
              <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
                <div>
                  <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">
                    Your organizations
                  </p>

                  <h2 className="mt-2 text-3xl font-black tracking-[-0.04em] text-slate-950">
                    Select a business workspace
                  </h2>
                </div>

                <p className="text-sm font-semibold text-slate-500">
                  {organizations.length} workspace
                  {organizations.length === 1 ? "" : "s"} available
                </p>
              </div>

              <div className="mt-7 grid gap-5 md:grid-cols-2 xl:grid-cols-3">
                {organizations.map((organization) => (
                  <OrganizationCard
                    key={organization.id}
                    organization={organization}
                    isSelected={
                      organization.id === selectedOrganizationId
                    }
                    onSelect={setSelectedOrganizationId}
                  />
                ))}
              </div>
            </section>

{selectedOrganization ? (
  <>
    <SelectedOrganizationPanel
      organization={selectedOrganization}
    />

    <SMEBusinessProducts
      organizationId={selectedOrganization.id}
      organizationName={selectedOrganization.name}
    />
    <SMECompetitorWatchlist
  organizationId={selectedOrganization.id}
  organizationName={selectedOrganization.name}
/>
<SMESalesImport
  organizationId={selectedOrganization.id}
  organizationName={selectedOrganization.name}
/>
<SMESalesAnalytics
  organizationId={selectedOrganization.id}
  organizationName={selectedOrganization.name}
/>
  </>
) : null}

            <section className="mt-8 grid gap-7 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm lg:grid-cols-[0.8fr_1.2fr] lg:p-9">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">
                  Additional business
                </p>

                <h2 className="mt-3 text-2xl font-black tracking-[-0.03em] text-slate-950">
                  Create another organization
                </h2>

                <p className="mt-4 text-sm leading-7 text-slate-600">
                  Multiple businesses ko separate products, inventory
                  aur competitor watchlists ke saath manage kiya ja
                  sakta hai.
                </p>
              </div>

              <OrganizationForm
                form={organizationForm}
                setForm={setOrganizationForm}
                onSubmit={handleCreateOrganization}
                isSubmitting={isSubmitting}
                submitError={submitError}
                compact
              />
            </section>
          </>
        ) : null}
      </div>
    </main>
  );
}

export default SMEPage;