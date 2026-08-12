import {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from "react";

import {
  createBusinessProduct,
  getBusinessProducts,
  updateBusinessProduct,
} from "../services/smeService";
import { getApiErrorMessage } from "../utils/apiError";

const initialProductForm = {
  canonical_product_id: "",
  name: "",
  sku: "",
  cost_price: "",
  selling_price: "",
  currency: "PKR",
  stock_level: "0",
  reorder_level: "0",
};

function extractProducts(responseData) {
  if (Array.isArray(responseData)) {
    return responseData;
  }

  if (Array.isArray(responseData?.items)) {
    return responseData.items;
  }

  return [];
}

function formatPrice(value, currency = "PKR") {
  if (
    value === null ||
    value === undefined ||
    value === ""
  ) {
    return "Not provided";
  }

  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return `${currency} ${value}`;
  }

  return new Intl.NumberFormat("en-PK", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(numericValue);
}

function buildProductPayload(form) {
  const canonicalProductId =
    form.canonical_product_id.trim();

  const costPrice = form.cost_price.trim();
  const sellingPrice = form.selling_price.trim();

  return {
    canonical_product_id: canonicalProductId
      ? Number(canonicalProductId)
      : null,
    name: form.name.trim(),
    sku: form.sku.trim() || null,
    cost_price: costPrice
      ? Number(costPrice)
      : null,
    selling_price: sellingPrice
      ? Number(sellingPrice)
      : null,
    currency:
      form.currency.trim().toUpperCase() || "PKR",
    stock_level: Number(form.stock_level || 0),
    reorder_level: Number(
      form.reorder_level || 0,
    ),
  };
}

function createEditForm(product) {
  return {
    canonical_product_id:
      product.canonical_product_id?.toString() || "",
    name: product.name || "",
    sku: product.sku || "",
    cost_price:
      product.cost_price?.toString() || "",
    selling_price:
      product.selling_price?.toString() || "",
    currency: product.currency || "PKR",
    stock_level:
      product.stock_level?.toString() || "0",
    reorder_level:
      product.reorder_level?.toString() || "0",
  };
}

function ProductFields({
  form,
  setForm,
  idPrefix,
}) {
  function handleChange(event) {
    const { name, value } = event.target;

    setForm((currentForm) => ({
      ...currentForm,
      [name]: value,
    }));
  }

  const inputClasses =
    "min-h-12 w-full rounded-xl border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-4 focus:ring-blue-100";

  return (
    <div className="grid gap-5 md:grid-cols-2">
      <div className="md:col-span-2">
        <label
          className="mb-2 block text-sm font-black text-slate-800"
          htmlFor={`${idPrefix}-name`}
        >
          Product name
        </label>

        <input
          id={`${idPrefix}-name`}
          className={inputClasses}
          name="name"
          type="text"
          required
          minLength={1}
          maxLength={255}
          value={form.name}
          onChange={handleChange}
          placeholder="Example: Samsung Galaxy A55 5G"
        />
      </div>

      <div>
        <label
          className="mb-2 block text-sm font-black text-slate-800"
          htmlFor={`${idPrefix}-sku`}
        >
          Internal SKU
        </label>

        <input
          id={`${idPrefix}-sku`}
          className={inputClasses}
          name="sku"
          type="text"
          maxLength={120}
          value={form.sku}
          onChange={handleChange}
          placeholder="Example: SAM-A55-001"
        />
      </div>

      <div>
        <label
          className="mb-2 block text-sm font-black text-slate-800"
          htmlFor={`${idPrefix}-canonical-product`}
        >
          Catalog product ID
          <span className="ml-1 font-medium text-slate-400">
            optional
          </span>
        </label>

        <input
          id={`${idPrefix}-canonical-product`}
          className={inputClasses}
          name="canonical_product_id"
          type="number"
          min="1"
          step="1"
          value={form.canonical_product_id}
          onChange={handleChange}
          placeholder="Example: 12"
        />
      </div>

      <div>
        <label
          className="mb-2 block text-sm font-black text-slate-800"
          htmlFor={`${idPrefix}-cost-price`}
        >
          Cost price
        </label>

        <input
          id={`${idPrefix}-cost-price`}
          className={inputClasses}
          name="cost_price"
          type="number"
          min="0"
          step="0.01"
          value={form.cost_price}
          onChange={handleChange}
          placeholder="Example: 115000"
        />
      </div>

      <div>
        <label
          className="mb-2 block text-sm font-black text-slate-800"
          htmlFor={`${idPrefix}-selling-price`}
        >
          Selling price
        </label>

        <input
          id={`${idPrefix}-selling-price`}
          className={inputClasses}
          name="selling_price"
          type="number"
          min="0"
          step="0.01"
          value={form.selling_price}
          onChange={handleChange}
          placeholder="Example: 124999"
        />
      </div>

      <div>
        <label
          className="mb-2 block text-sm font-black text-slate-800"
          htmlFor={`${idPrefix}-currency`}
        >
          Currency
        </label>

        <input
          id={`${idPrefix}-currency`}
          className={inputClasses}
          name="currency"
          type="text"
          required
          minLength={3}
          maxLength={3}
          value={form.currency}
          onChange={handleChange}
          placeholder="PKR"
        />
      </div>

      <div>
        <label
          className="mb-2 block text-sm font-black text-slate-800"
          htmlFor={`${idPrefix}-stock-level`}
        >
          Current stock
        </label>

        <input
          id={`${idPrefix}-stock-level`}
          className={inputClasses}
          name="stock_level"
          type="number"
          required
          min="0"
          step="1"
          value={form.stock_level}
          onChange={handleChange}
        />
      </div>

      <div>
        <label
          className="mb-2 block text-sm font-black text-slate-800"
          htmlFor={`${idPrefix}-reorder-level`}
        >
          Reorder level
        </label>

        <input
          id={`${idPrefix}-reorder-level`}
          className={inputClasses}
          name="reorder_level"
          type="number"
          required
          min="0"
          step="1"
          value={form.reorder_level}
          onChange={handleChange}
        />

        <p className="mt-2 text-xs leading-5 text-slate-500">
          Stock is level tak pohanchne par reorder
          recommendation show hogi.
        </p>
      </div>
    </div>
  );
}

function ProductCard({
  product,
  isEditing,
  editForm,
  setEditForm,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onToggleStatus,
  isUpdating,
}) {
  const isLowStock =
    product.stock_level <= product.reorder_level;

  if (isEditing) {
    return (
      <article className="rounded-3xl border border-blue-300 bg-blue-50/50 p-6 shadow-sm">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.16em] text-blue-600">
              Editing product
            </p>

            <h3 className="mt-2 text-xl font-black text-slate-950">
              {product.name}
            </h3>
          </div>

          <button
            type="button"
            onClick={onCancelEdit}
            className="rounded-xl border border-slate-300 bg-white px-4 py-2 text-xs font-black text-slate-700 transition hover:bg-slate-100"
          >
            Cancel
          </button>
        </div>

        <form
          className="mt-6"
          onSubmit={onSaveEdit}
        >
          <ProductFields
            form={editForm}
            setForm={setEditForm}
            idPrefix={`edit-product-${product.id}`}
          />

          <button
            type="submit"
            disabled={isUpdating}
            className="mt-6 inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-blue-600 px-5 text-sm font-black text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isUpdating
              ? "Saving changes..."
              : "Save product changes"}
          </button>
        </form>
      </article>
    );
  }

  return (
    <article className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:border-blue-200 hover:shadow-lg">
      <div className="flex flex-col justify-between gap-5 sm:flex-row sm:items-start">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={[
                "rounded-full px-3 py-1 text-[10px] font-black uppercase",
                product.is_active
                  ? "bg-emerald-100 text-emerald-700"
                  : "bg-slate-200 text-slate-600",
              ].join(" ")}
            >
              {product.is_active
                ? "Active"
                : "Inactive"}
            </span>

            {isLowStock ? (
              <span className="rounded-full bg-red-100 px-3 py-1 text-[10px] font-black uppercase text-red-700">
                Low stock
              </span>
            ) : (
              <span className="rounded-full bg-blue-100 px-3 py-1 text-[10px] font-black uppercase text-blue-700">
                Stock healthy
              </span>
            )}
          </div>

          <h3 className="mt-4 truncate text-xl font-black tracking-tight text-slate-950">
            {product.name}
          </h3>

          <p className="mt-2 text-sm font-semibold text-slate-500">
            SKU: {product.sku || "Not assigned"}
          </p>

          {product.canonical_product_id ? (
            <p className="mt-1 text-xs font-semibold text-slate-400">
              Catalog product #
              {product.canonical_product_id}
            </p>
          ) : null}
        </div>

        <div className="flex shrink-0 gap-2">
          <button
            type="button"
            onClick={onStartEdit}
            className="rounded-xl border border-blue-200 bg-blue-50 px-4 py-2 text-xs font-black text-blue-700 transition hover:bg-blue-100"
          >
            Edit
          </button>

          <button
            type="button"
            disabled={isUpdating}
            onClick={onToggleStatus}
            className={[
              "rounded-xl border px-4 py-2 text-xs font-black transition disabled:cursor-not-allowed disabled:opacity-60",
              product.is_active
                ? "border-red-200 bg-red-50 text-red-700 hover:bg-red-100"
                : "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100",
            ].join(" ")}
          >
            {isUpdating
              ? "Updating..."
              : product.is_active
                ? "Deactivate"
                : "Activate"}
          </button>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <div className="rounded-2xl bg-slate-50 p-4">
          <p className="text-[10px] font-black uppercase tracking-wide text-slate-400">
            Cost price
          </p>

          <p className="mt-2 text-sm font-black text-slate-800">
            {formatPrice(
              product.cost_price,
              product.currency,
            )}
          </p>
        </div>

        <div className="rounded-2xl bg-blue-50 p-4">
          <p className="text-[10px] font-black uppercase tracking-wide text-blue-500">
            Selling price
          </p>

          <p className="mt-2 text-sm font-black text-blue-700">
            {formatPrice(
              product.selling_price,
              product.currency,
            )}
          </p>
        </div>

        <div
          className={[
            "rounded-2xl p-4",
            isLowStock
              ? "bg-red-50"
              : "bg-emerald-50",
          ].join(" ")}
        >
          <p
            className={[
              "text-[10px] font-black uppercase tracking-wide",
              isLowStock
                ? "text-red-500"
                : "text-emerald-500",
            ].join(" ")}
          >
            Current stock
          </p>

          <p
            className={[
              "mt-2 text-2xl font-black",
              isLowStock
                ? "text-red-700"
                : "text-emerald-700",
            ].join(" ")}
          >
            {product.stock_level}
          </p>
        </div>

        <div className="rounded-2xl bg-amber-50 p-4">
          <p className="text-[10px] font-black uppercase tracking-wide text-amber-500">
            Reorder level
          </p>

          <p className="mt-2 text-2xl font-black text-amber-700">
            {product.reorder_level}
          </p>
        </div>
      </div>
    </article>
  );
}

function SMEBusinessProducts({
  organizationId,
  organizationName,
}) {
  const [products, setProducts] = useState([]);
  const [productForm, setProductForm] = useState(
    initialProductForm,
  );

  const [editingProductId, setEditingProductId] =
    useState(null);

  const [editForm, setEditForm] = useState(
    initialProductForm,
  );

  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] =
    useState(false);
  const [updatingProductId, setUpdatingProductId] =
    useState(null);

  const [loadError, setLoadError] = useState("");
  const [formError, setFormError] = useState("");
  const [actionError, setActionError] =
    useState("");

  const loadProducts = useCallback(async () => {
    if (!organizationId) {
      setProducts([]);
      setIsLoading(false);
      return;
    }

    setIsLoading(true);
    setLoadError("");

    try {
      const responseData =
        await getBusinessProducts(
          organizationId,
          {
            page: 1,
            page_size: 100,
          },
        );

      setProducts(extractProducts(responseData));
    } catch (error) {
      setLoadError(
        getApiErrorMessage(
          error,
          "Business products could not be loaded.",
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }, [organizationId]);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setEditingProductId(null);
      setProductForm(initialProductForm);
      loadProducts();
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [loadProducts]);

  const statistics = useMemo(() => {
    const activeProducts = products.filter(
      (product) => product.is_active,
    ).length;

    const lowStockProducts = products.filter(
      (product) =>
        product.stock_level <= product.reorder_level,
    ).length;

    const totalStock = products.reduce(
      (total, product) =>
        total + Number(product.stock_level || 0),
      0,
    );

    return {
      activeProducts,
      lowStockProducts,
      totalStock,
    };
  }, [products]);

  async function handleCreateProduct(event) {
    event.preventDefault();

    if (!productForm.name.trim()) {
      setFormError("Product name is required.");
      return;
    }

    setIsCreating(true);
    setFormError("");

    try {
      const createdProduct =
        await createBusinessProduct(
          organizationId,
          buildProductPayload(productForm),
        );

      setProducts((currentProducts) => [
        createdProduct,
        ...currentProducts,
      ]);

      setProductForm(initialProductForm);
    } catch (error) {
      setFormError(
        getApiErrorMessage(
          error,
          "Product could not be created.",
        ),
      );
    } finally {
      setIsCreating(false);
    }
  }

  function handleStartEdit(product) {
    setActionError("");
    setEditingProductId(product.id);
    setEditForm(createEditForm(product));
  }

  async function handleSaveEdit(event) {
    event.preventDefault();

    const productId = editingProductId;

    if (!productId || !editForm.name.trim()) {
      return;
    }

    setUpdatingProductId(productId);
    setActionError("");

    try {
      const updatedProduct =
        await updateBusinessProduct(
          organizationId,
          productId,
          buildProductPayload(editForm),
        );

      setProducts((currentProducts) =>
        currentProducts.map((product) =>
          product.id === productId
            ? updatedProduct
            : product,
        ),
      );

      setEditingProductId(null);
    } catch (error) {
      setActionError(
        getApiErrorMessage(
          error,
          "Product changes could not be saved.",
        ),
      );
    } finally {
      setUpdatingProductId(null);
    }
  }

  async function handleToggleStatus(product) {
    setUpdatingProductId(product.id);
    setActionError("");

    try {
      const updatedProduct =
        await updateBusinessProduct(
          organizationId,
          product.id,
          {
            is_active: !product.is_active,
          },
        );

      setProducts((currentProducts) =>
        currentProducts.map((currentProduct) =>
          currentProduct.id === product.id
            ? updatedProduct
            : currentProduct,
        ),
      );
    } catch (error) {
      setActionError(
        getApiErrorMessage(
          error,
          "Product status could not be updated.",
        ),
      );
    } finally {
      setUpdatingProductId(null);
    }
  }

  return (
    <section className="mt-8">
      <div className="rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">
              Product management
            </p>

            <h2 className="mt-3 text-3xl font-black tracking-[-0.04em] text-slate-950">
              Business Products
            </h2>

            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-600">
              Manage products, pricing and stock for{" "}
              <strong className="text-slate-900">
                {organizationName}
              </strong>
              .
            </p>
          </div>

          <button
            type="button"
            onClick={loadProducts}
            disabled={isLoading}
            className="inline-flex min-h-11 items-center justify-center rounded-xl border border-slate-300 bg-white px-5 text-sm font-black text-slate-700 transition hover:border-blue-300 hover:bg-blue-50 disabled:opacity-60"
          >
            {isLoading
              ? "Refreshing..."
              : "Refresh products"}
          </button>
        </div>

        <div className="mt-7 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="rounded-2xl bg-slate-950 p-5 text-white">
            <p className="text-xs font-bold text-slate-400">
              Total products
            </p>

            <p className="mt-3 text-3xl font-black">
              {products.length}
            </p>
          </div>

          <div className="rounded-2xl bg-emerald-50 p-5">
            <p className="text-xs font-bold text-emerald-600">
              Active products
            </p>

            <p className="mt-3 text-3xl font-black text-emerald-700">
              {statistics.activeProducts}
            </p>
          </div>

          <div className="rounded-2xl bg-red-50 p-5">
            <p className="text-xs font-bold text-red-600">
              Low stock
            </p>

            <p className="mt-3 text-3xl font-black text-red-700">
              {statistics.lowStockProducts}
            </p>
          </div>

          <div className="rounded-2xl bg-blue-50 p-5">
            <p className="text-xs font-bold text-blue-600">
              Total stock units
            </p>

            <p className="mt-3 text-3xl font-black text-blue-700">
              {statistics.totalStock}
            </p>
          </div>
        </div>
      </div>

      <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
        <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">
          Add new product
        </p>

        <h3 className="mt-3 text-2xl font-black text-slate-950">
          Create a business product
        </h3>

        <form
          className="mt-7"
          onSubmit={handleCreateProduct}
        >
          <ProductFields
            form={productForm}
            setForm={setProductForm}
            idPrefix="create-business-product"
          />

          {formError ? (
            <div
              className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700"
              role="alert"
            >
              {formError}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={isCreating}
            className="mt-6 inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-blue-600 px-5 text-sm font-black text-white shadow-lg shadow-blue-600/20 transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isCreating
              ? "Creating product..."
              : "Add business product"}
          </button>
        </form>
      </section>

      <section className="mt-6">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">
            Product inventory
          </p>

          <h3 className="mt-2 text-3xl font-black text-slate-950">
            Managed products
          </h3>
        </div>

        {actionError ? (
          <div
            className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700"
            role="alert"
          >
            {actionError}
          </div>
        ) : null}

        {isLoading ? (
          <div className="mt-6 grid gap-5">
            {[1, 2].map((item) => (
              <div
                key={item}
                className="h-64 animate-pulse rounded-3xl border border-slate-200 bg-white"
              />
            ))}
          </div>
        ) : null}

        {!isLoading && loadError ? (
          <div className="mt-6 rounded-3xl border border-red-200 bg-white p-8 text-center">
            <h4 className="text-xl font-black text-slate-950">
              Products could not be loaded
            </h4>

            <p className="mt-3 text-sm text-red-700">
              {loadError}
            </p>

            <button
              type="button"
              onClick={loadProducts}
              className="mt-5 rounded-xl bg-slate-950 px-5 py-3 text-sm font-black text-white"
            >
              Try again
            </button>
          </div>
        ) : null}

        {!isLoading &&
        !loadError &&
        products.length === 0 ? (
          <div className="mt-6 rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
            <h4 className="text-xl font-black text-slate-950">
              No business products yet
            </h4>

            <p className="mt-3 text-sm leading-7 text-slate-600">
              Upar wala form use karke apna pehla
              product add karo.
            </p>
          </div>
        ) : null}

        {!isLoading &&
        !loadError &&
        products.length > 0 ? (
          <div className="mt-6 grid gap-5">
            {products.map((product) => (
              <ProductCard
                key={product.id}
                product={product}
                isEditing={
                  editingProductId === product.id
                }
                editForm={editForm}
                setEditForm={setEditForm}
                onStartEdit={() =>
                  handleStartEdit(product)
                }
                onCancelEdit={() =>
                  setEditingProductId(null)
                }
                onSaveEdit={handleSaveEdit}
                onToggleStatus={() =>
                  handleToggleStatus(product)
                }
                isUpdating={
                  updatingProductId === product.id
                }
              />
            ))}
          </div>
        ) : null}
      </section>
    </section>
  );
}

export default SMEBusinessProducts;
