import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  getSalesImportRecords,
  getSalesImports,
  uploadSalesImport,
} from "../services/smeService";
import { getApiErrorMessage } from "../utils/apiError";


const MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024;

const acceptedColumns = [
  "sku",
  "sale_date",
  "quantity",
  "unit_price",
  "currency",
];


function extractItems(responseData) {
  if (Array.isArray(responseData)) {
    return responseData;
  }

  if (Array.isArray(responseData?.items)) {
    return responseData.items;
  }

  return [];
}


function formatDateTime(value) {
  if (!value) {
    return "Not available";
  }

  const parsedDate = new Date(value);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-PK", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parsedDate);
}


function formatSaleDate(value) {
  if (!value) {
    return "Not available";
  }

  const parsedDate = new Date(`${value}T00:00:00`);

  if (Number.isNaN(parsedDate.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-PK", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(parsedDate);
}


function formatPrice(value, currency = "PKR") {
  const numericValue = Number(value);

  if (!Number.isFinite(numericValue)) {
    return `${currency} ${value ?? "0"}`;
  }

  return new Intl.NumberFormat("en-PK", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(numericValue);
}


function getStatusDetails(status) {
  const statusMap = {
    pending: {
      label: "Pending",
      classes: "bg-amber-100 text-amber-700",
    },
    processing: {
      label: "Processing",
      classes: "bg-blue-100 text-blue-700",
    },
    completed: {
      label: "Completed",
      classes: "bg-emerald-100 text-emerald-700",
    },
    completed_with_errors: {
      label: "Completed with errors",
      classes: "bg-orange-100 text-orange-700",
    },
    failed: {
      label: "Failed",
      classes: "bg-red-100 text-red-700",
    },
  };

  return (
    statusMap[status] || {
      label: status || "Unknown",
      classes: "bg-slate-100 text-slate-700",
    }
  );
}


function ImportSummary({ salesImport }) {
  if (!salesImport) {
    return null;
  }

  const statusDetails = getStatusDetails(
    salesImport.status,
  );

  return (
    <section className="mt-6 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
      <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-emerald-600">
            Latest import result
          </p>

          <h3 className="mt-3 text-2xl font-black tracking-[-0.03em] text-slate-950">
            {salesImport.original_filename}
          </h3>

          <p className="mt-2 text-sm font-semibold text-slate-500">
            Processed {formatDateTime(salesImport.completed_at)}
          </p>
        </div>

        <span
          className={[
            "w-fit rounded-full px-4 py-2 text-xs font-black",
            statusDetails.classes,
          ].join(" ")}
        >
          {statusDetails.label}
        </span>
      </div>

      <div className="mt-7 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="rounded-2xl bg-slate-950 p-5 text-white">
          <p className="text-xs font-bold text-slate-400">
            Total rows
          </p>

          <p className="mt-3 text-3xl font-black">
            {salesImport.total_rows}
          </p>
        </div>

        <div className="rounded-2xl bg-emerald-50 p-5">
          <p className="text-xs font-bold text-emerald-600">
            Accepted
          </p>

          <p className="mt-3 text-3xl font-black text-emerald-700">
            {salesImport.accepted_rows}
          </p>
        </div>

        <div className="rounded-2xl bg-red-50 p-5">
          <p className="text-xs font-bold text-red-600">
            Rejected
          </p>

          <p className="mt-3 text-3xl font-black text-red-700">
            {salesImport.rejected_rows}
          </p>
        </div>

        <div className="rounded-2xl bg-blue-50 p-5">
          <p className="text-xs font-bold text-blue-600">
            Import ID
          </p>

          <p className="mt-3 text-3xl font-black text-blue-700">
            #{salesImport.id}
          </p>
        </div>
      </div>

      {salesImport.error_message ? (
        <div className="mt-5 rounded-xl border border-orange-200 bg-orange-50 px-4 py-3 text-sm font-semibold leading-6 text-orange-800">
          {salesImport.error_message}
        </div>
      ) : null}
    </section>
  );
}


function RowErrorsTable({ rowErrors }) {
  if (!Array.isArray(rowErrors) || rowErrors.length === 0) {
    return null;
  }

  const visibleErrors = rowErrors.slice(0, 100);

  return (
    <section className="mt-6 rounded-3xl border border-red-200 bg-white p-7 shadow-sm sm:p-9">
      <p className="text-xs font-black uppercase tracking-[0.18em] text-red-600">
        Rejected row details
      </p>

      <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <h3 className="text-2xl font-black tracking-[-0.03em] text-slate-950">
          Fix these CSV values
        </h3>

        <p className="text-sm font-bold text-red-700">
          {rowErrors.length} validation error
          {rowErrors.length === 1 ? "" : "s"}
        </p>
      </div>

      <div className="mt-6 overflow-x-auto rounded-2xl border border-slate-200">
        <table className="min-w-full divide-y divide-slate-200 text-left">
          <thead className="bg-slate-50">
            <tr>
              <th className="px-4 py-3 text-xs font-black uppercase tracking-wide text-slate-500">
                CSV row
              </th>

              <th className="px-4 py-3 text-xs font-black uppercase tracking-wide text-slate-500">
                Field
              </th>

              <th className="px-4 py-3 text-xs font-black uppercase tracking-wide text-slate-500">
                Problem
              </th>

              <th className="px-4 py-3 text-xs font-black uppercase tracking-wide text-slate-500">
                Supplied value
              </th>
            </tr>
          </thead>

          <tbody className="divide-y divide-slate-100 bg-white">
            {visibleErrors.map((error, index) => (
              <tr
                key={[
                  error.row_number,
                  error.field,
                  index,
                ].join("-")}
              >
                <td className="whitespace-nowrap px-4 py-4 text-sm font-black text-slate-900">
                  {error.row_number}
                </td>

                <td className="whitespace-nowrap px-4 py-4 text-sm font-bold text-red-700">
                  {error.field || "Complete row"}
                </td>

                <td className="min-w-72 px-4 py-4 text-sm leading-6 text-slate-700">
                  {error.message}
                </td>

                <td className="max-w-72 break-words px-4 py-4 text-sm font-semibold text-slate-500">
                  {error.value || "Empty"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {rowErrors.length > visibleErrors.length ? (
        <p className="mt-4 text-sm font-semibold text-slate-500">
          First {visibleErrors.length} errors are shown.
          Correct the CSV and upload it again.
        </p>
      ) : null}
    </section>
  );
}


function SMESalesImport({
  organizationId,
  organizationName,
}) {
  const fileInputRef = useRef(null);

  const [selectedFile, setSelectedFile] =
    useState(null);

  const [uploadResult, setUploadResult] =
    useState(null);

  const [imports, setImports] = useState([]);
  const [records, setRecords] = useState([]);

  const [selectedImportId, setSelectedImportId] =
    useState(null);

  const [isUploading, setIsUploading] =
    useState(false);

  const [isLoadingImports, setIsLoadingImports] =
    useState(true);

  const [isLoadingRecords, setIsLoadingRecords] =
    useState(false);

  const [uploadError, setUploadError] =
    useState("");

  const [importsError, setImportsError] =
    useState("");

  const [recordsError, setRecordsError] =
    useState("");

  const [successMessage, setSuccessMessage] =
    useState("");

  const loadImports = useCallback(async () => {
    if (!organizationId) {
      setImports([]);
      setIsLoadingImports(false);
      return;
    }

    setIsLoadingImports(true);
    setImportsError("");

    try {
      const responseData = await getSalesImports(
        organizationId,
        {
          page: 1,
          page_size: 50,
        },
      );

      setImports(extractItems(responseData));
    } catch (error) {
      setImportsError(
        getApiErrorMessage(
          error,
          "Sales import history could not be loaded.",
        ),
      );
    } finally {
      setIsLoadingImports(false);
    }
  }, [organizationId]);

  useEffect(() => {
    const resetTimeoutId = window.setTimeout(() => {
      setSelectedFile(null);
      setUploadResult(null);
      setSelectedImportId(null);
      setRecords([]);
      setUploadError("");
      setRecordsError("");
      setSuccessMessage("");

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      loadImports();
    }, 0);

    return () => {
      window.clearTimeout(resetTimeoutId);
    };
  }, [loadImports]);

  const importStatistics = useMemo(() => {
    const completedImports = imports.filter(
      (salesImport) =>
        salesImport.status === "completed",
    ).length;

    const importsWithErrors = imports.filter(
      (salesImport) =>
        salesImport.status ===
        "completed_with_errors",
    ).length;

    const totalAcceptedRows = imports.reduce(
      (total, salesImport) =>
        total +
        Number(salesImport.accepted_rows || 0),
      0,
    );

    return {
      completedImports,
      importsWithErrors,
      totalAcceptedRows,
    };
  }, [imports]);

  function handleFileChange(event) {
    const file = event.target.files?.[0];

    setUploadError("");
    setSuccessMessage("");
    setUploadResult(null);

    if (!file) {
      setSelectedFile(null);
      return;
    }

    if (!file.name.toLowerCase().endsWith(".csv")) {
      setSelectedFile(null);
      setUploadError(
        "Please select a file with a .csv extension.",
      );

      event.target.value = "";
      return;
    }

    if (file.size === 0) {
      setSelectedFile(null);
      setUploadError(
        "The selected CSV file is empty.",
      );

      event.target.value = "";
      return;
    }

    if (file.size > MAX_FILE_SIZE_BYTES) {
      setSelectedFile(null);
      setUploadError(
        "The CSV file must not exceed 2 MB.",
      );

      event.target.value = "";
      return;
    }

    setSelectedFile(file);
  }

  async function handleUpload(event) {
    event.preventDefault();

    if (!selectedFile) {
      setUploadError(
        "Select a CSV file before starting the import.",
      );
      return;
    }

    setIsUploading(true);
    setUploadError("");
    setSuccessMessage("");
    setRecords([]);
    setSelectedImportId(null);

    try {
      const result = await uploadSalesImport(
        organizationId,
        selectedFile,
      );

      setUploadResult(result);

      const acceptedRows = Number(
        result?.sales_import?.accepted_rows || 0,
      );

      const rejectedRows = Number(
        result?.sales_import?.rejected_rows || 0,
      );

      setSuccessMessage(
        rejectedRows > 0
          ? `${acceptedRows} row(s) imported and ${rejectedRows} row(s) rejected.`
          : `${acceptedRows} sales row(s) imported successfully.`,
      );

      setSelectedFile(null);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }

      await loadImports();
    } catch (error) {
      setUploadError(
        getApiErrorMessage(
          error,
          "The sales CSV could not be imported.",
        ),
      );
    } finally {
      setIsUploading(false);
    }
  }

  async function handleViewRecords(salesImport) {
    setSelectedImportId(salesImport.id);
    setIsLoadingRecords(true);
    setRecordsError("");
    setRecords([]);

    try {
      const responseData =
        await getSalesImportRecords(
          organizationId,
          salesImport.id,
          {
            page: 1,
            page_size: 100,
          },
        );

      setRecords(extractItems(responseData));
    } catch (error) {
      setRecordsError(
        getApiErrorMessage(
          error,
          "Saved sales records could not be loaded.",
        ),
      );
    } finally {
      setIsLoadingRecords(false);
    }
  }

  return (
    <section className="mt-8">
      <div className="rounded-3xl bg-gradient-to-br from-emerald-950 via-slate-950 to-slate-900 p-7 text-white shadow-xl sm:p-9">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-emerald-300">
              Sales intelligence
            </p>

            <h2 className="mt-3 text-3xl font-black tracking-[-0.04em]">
              Import Sales Data
            </h2>

            <p className="mt-3 max-w-2xl text-sm leading-7 text-slate-300">
              Upload historical sales for{" "}
              <strong className="text-white">
                {organizationName}
              </strong>
              . VEXTRO will match each SKU with your
              business products and store valid sales
              records.
            </p>
          </div>

          <button
            type="button"
            onClick={loadImports}
            disabled={isLoadingImports}
            className="inline-flex min-h-11 items-center justify-center rounded-xl border border-white/15 bg-white/10 px-5 text-sm font-black text-white transition hover:bg-white/15 disabled:opacity-60"
          >
            {isLoadingImports
              ? "Refreshing..."
              : "Refresh history"}
          </button>
        </div>

        <div className="mt-7 grid grid-cols-2 gap-4 lg:grid-cols-4">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs font-bold text-slate-400">
              Total imports
            </p>

            <p className="mt-3 text-3xl font-black">
              {imports.length}
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs font-bold text-slate-400">
              Fully completed
            </p>

            <p className="mt-3 text-3xl font-black text-emerald-300">
              {importStatistics.completedImports}
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs font-bold text-slate-400">
              With errors
            </p>

            <p className="mt-3 text-3xl font-black text-orange-300">
              {importStatistics.importsWithErrors}
            </p>
          </div>

          <div className="rounded-2xl border border-white/10 bg-white/5 p-5">
            <p className="text-xs font-bold text-slate-400">
              Accepted rows
            </p>

            <p className="mt-3 text-3xl font-black text-blue-300">
              {importStatistics.totalAcceptedRows}
            </p>
          </div>
        </div>
      </div>

      <section className="mt-6 grid gap-6 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm lg:grid-cols-[0.9fr_1.1fr] sm:p-9">
        <div>
          <p className="text-xs font-black uppercase tracking-[0.18em] text-emerald-600">
            CSV format
          </p>

          <h3 className="mt-3 text-2xl font-black tracking-[-0.03em] text-slate-950">
            Prepare your sales history
          </h3>

          <p className="mt-3 text-sm leading-7 text-slate-600">
            Har sales row ka SKU pehle Business Products
            section mein maujood active SKU se match hona
            chahiye.
          </p>

          <div className="mt-6 overflow-hidden rounded-2xl border border-slate-200">
            <div className="bg-slate-950 px-5 py-3 text-xs font-black uppercase tracking-[0.14em] text-white">
              Required CSV header
            </div>

            <pre className="overflow-x-auto bg-slate-50 p-5 text-xs font-bold leading-6 text-slate-700">
              {acceptedColumns.join(",")}
            </pre>
          </div>

          <div className="mt-5 rounded-2xl bg-emerald-50 p-5">
            <p className="text-xs font-black uppercase tracking-wide text-emerald-700">
              Example row
            </p>

            <p className="mt-3 break-all font-mono text-xs font-bold leading-6 text-emerald-900">
              PHONE-001,2026-08-01,2,125000,PKR
            </p>
          </div>

          <p className="mt-5 text-xs font-semibold leading-6 text-slate-500">
            Maximum file size: 2 MB. Maximum sales rows:
            5,000. Dates must use YYYY-MM-DD format.
          </p>
        </div>

        <form
          className="rounded-3xl border border-dashed border-emerald-300 bg-emerald-50/50 p-6 sm:p-8"
          onSubmit={handleUpload}
        >
          <label
            className="block text-sm font-black text-slate-900"
            htmlFor={`sales-csv-${organizationId}`}
          >
            Select sales CSV
          </label>

          <input
            ref={fileInputRef}
            id={`sales-csv-${organizationId}`}
            type="file"
            accept=".csv,text/csv"
            onChange={handleFileChange}
            className="mt-3 block w-full rounded-xl border border-slate-300 bg-white p-3 text-sm font-semibold text-slate-700 file:mr-4 file:rounded-lg file:border-0 file:bg-emerald-600 file:px-4 file:py-2 file:text-xs file:font-black file:text-white hover:file:bg-emerald-700"
          />

          {selectedFile ? (
            <div className="mt-5 rounded-2xl border border-emerald-200 bg-white p-5">
              <p className="text-xs font-black uppercase tracking-wide text-emerald-600">
                Ready to import
              </p>

              <p className="mt-2 break-all text-sm font-black text-slate-900">
                {selectedFile.name}
              </p>

              <p className="mt-2 text-xs font-semibold text-slate-500">
                {(selectedFile.size / 1024).toFixed(1)} KB
              </p>
            </div>
          ) : null}

          {uploadError ? (
            <div
              className="mt-5 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold leading-6 text-red-700"
              role="alert"
            >
              {uploadError}
            </div>
          ) : null}

          {successMessage ? (
            <div
              className="mt-5 rounded-xl border border-emerald-200 bg-white px-4 py-3 text-sm font-semibold leading-6 text-emerald-700"
              role="status"
            >
              {successMessage}
            </div>
          ) : null}

          <button
            type="submit"
            disabled={
              isUploading ||
              !selectedFile
            }
            className="mt-6 inline-flex min-h-12 w-full items-center justify-center rounded-xl bg-emerald-600 px-5 text-sm font-black text-white shadow-lg shadow-emerald-600/20 transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isUploading
              ? "Importing sales data..."
              : "Import sales history"}
          </button>
        </form>
      </section>

      <ImportSummary
        salesImport={uploadResult?.sales_import}
      />

      <RowErrorsTable
        rowErrors={uploadResult?.row_errors}
      />

      <section className="mt-8">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-black uppercase tracking-[0.18em] text-emerald-600">
              Previous uploads
            </p>

            <h3 className="mt-2 text-3xl font-black tracking-[-0.04em] text-slate-950">
              Sales import history
            </h3>
          </div>

          <p className="text-sm font-semibold text-slate-500">
            {imports.length} saved import
            {imports.length === 1 ? "" : "s"}
          </p>
        </div>

        {isLoadingImports ? (
          <div className="mt-6 grid gap-5">
            {[1, 2].map((item) => (
              <div
                key={item}
                className="h-48 animate-pulse rounded-3xl border border-slate-200 bg-white"
              />
            ))}
          </div>
        ) : null}

        {!isLoadingImports && importsError ? (
          <div className="mt-6 rounded-3xl border border-red-200 bg-white p-8 text-center">
            <h4 className="text-xl font-black text-slate-950">
              Import history could not be loaded
            </h4>

            <p className="mt-3 text-sm text-red-700">
              {importsError}
            </p>

            <button
              type="button"
              onClick={loadImports}
              className="mt-5 rounded-xl bg-slate-950 px-5 py-3 text-sm font-black text-white"
            >
              Try again
            </button>
          </div>
        ) : null}

        {!isLoadingImports &&
        !importsError &&
        imports.length === 0 ? (
          <div className="mt-6 rounded-3xl border border-dashed border-slate-300 bg-white p-10 text-center">
            <h4 className="text-xl font-black text-slate-950">
              No sales imports yet
            </h4>

            <p className="mt-3 text-sm leading-7 text-slate-600">
              Apni pehli CSV upload karne ke baad import
              history yahan show hogi.
            </p>
          </div>
        ) : null}

        {!isLoadingImports &&
        !importsError &&
        imports.length > 0 ? (
          <div className="mt-6 grid gap-5">
            {imports.map((salesImport) => {
              const statusDetails = getStatusDetails(
                salesImport.status,
              );

              const isSelected =
                selectedImportId === salesImport.id;

              return (
                <article
                  key={salesImport.id}
                  className={[
                    "rounded-3xl border bg-white p-6 shadow-sm transition sm:p-7",
                    isSelected
                      ? "border-emerald-500 ring-4 ring-emerald-100"
                      : "border-slate-200",
                  ].join(" ")}
                >
                  <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span
                          className={[
                            "rounded-full px-3 py-1 text-[10px] font-black uppercase",
                            statusDetails.classes,
                          ].join(" ")}
                        >
                          {statusDetails.label}
                        </span>

                        <span className="rounded-full bg-slate-100 px-3 py-1 text-[10px] font-black uppercase text-slate-600">
                          Import #{salesImport.id}
                        </span>
                      </div>

                      <h4 className="mt-4 break-all text-xl font-black text-slate-950">
                        {salesImport.original_filename}
                      </h4>

                      <p className="mt-2 text-sm font-semibold text-slate-500">
                        Uploaded{" "}
                        {formatDateTime(
                          salesImport.created_at,
                        )}
                      </p>
                    </div>

                    <button
                      type="button"
                      onClick={() =>
                        handleViewRecords(salesImport)
                      }
                      disabled={
                        isLoadingRecords &&
                        isSelected
                      }
                      className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-xl bg-slate-950 px-5 text-xs font-black text-white transition hover:bg-slate-800 disabled:opacity-60"
                    >
                      {isLoadingRecords && isSelected
                        ? "Loading records..."
                        : "View saved records"}
                    </button>
                  </div>

                  <div className="mt-6 grid grid-cols-3 gap-3">
                    <div className="rounded-2xl bg-slate-50 p-4">
                      <p className="text-[10px] font-black uppercase text-slate-400">
                        Total
                      </p>

                      <p className="mt-2 text-2xl font-black text-slate-900">
                        {salesImport.total_rows}
                      </p>
                    </div>

                    <div className="rounded-2xl bg-emerald-50 p-4">
                      <p className="text-[10px] font-black uppercase text-emerald-600">
                        Accepted
                      </p>

                      <p className="mt-2 text-2xl font-black text-emerald-700">
                        {salesImport.accepted_rows}
                      </p>
                    </div>

                    <div className="rounded-2xl bg-red-50 p-4">
                      <p className="text-[10px] font-black uppercase text-red-600">
                        Rejected
                      </p>

                      <p className="mt-2 text-2xl font-black text-red-700">
                        {salesImport.rejected_rows}
                      </p>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        ) : null}
      </section>

      {selectedImportId ? (
        <section className="mt-8 rounded-3xl border border-slate-200 bg-white p-7 shadow-sm sm:p-9">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-black uppercase tracking-[0.18em] text-blue-600">
                Imported transactions
              </p>

              <h3 className="mt-2 text-3xl font-black tracking-[-0.04em] text-slate-950">
                Saved sales records
              </h3>
            </div>

            <p className="text-sm font-black text-slate-500">
              Import #{selectedImportId}
            </p>
          </div>

          {isLoadingRecords ? (
            <div className="mt-6 h-48 animate-pulse rounded-2xl bg-slate-100" />
          ) : null}

          {!isLoadingRecords && recordsError ? (
            <div
              className="mt-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700"
              role="alert"
            >
              {recordsError}
            </div>
          ) : null}

          {!isLoadingRecords &&
          !recordsError &&
          records.length === 0 ? (
            <div className="mt-6 rounded-2xl border border-dashed border-slate-300 p-8 text-center">
              <p className="text-sm font-bold text-slate-600">
                Is import mein koi accepted sales record
                available nahi hai.
              </p>
            </div>
          ) : null}

          {!isLoadingRecords &&
          !recordsError &&
          records.length > 0 ? (
            <div className="mt-6 overflow-x-auto rounded-2xl border border-slate-200">
              <table className="min-w-full divide-y divide-slate-200 text-left">
                <thead className="bg-slate-50">
                  <tr>
                    {[
                      "CSV row",
                      "Product ID",
                      "Sale date",
                      "Quantity",
                      "Unit price",
                      "Revenue",
                    ].map((heading) => (
                      <th
                        key={heading}
                        className="whitespace-nowrap px-4 py-3 text-xs font-black uppercase tracking-wide text-slate-500"
                      >
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100 bg-white">
                  {records.map((record) => (
                    <tr key={record.id}>
                      <td className="px-4 py-4 text-sm font-black text-slate-900">
                        {record.source_row_number}
                      </td>

                      <td className="px-4 py-4 text-sm font-bold text-slate-700">
                        #{record.business_product_id}
                      </td>

                      <td className="whitespace-nowrap px-4 py-4 text-sm font-semibold text-slate-600">
                        {formatSaleDate(
                          record.sale_date,
                        )}
                      </td>

                      <td className="px-4 py-4 text-sm font-black text-blue-700">
                        {record.quantity}
                      </td>

                      <td className="whitespace-nowrap px-4 py-4 text-sm font-bold text-slate-700">
                        {formatPrice(
                          record.unit_price,
                          record.currency,
                        )}
                      </td>

                      <td className="whitespace-nowrap px-4 py-4 text-sm font-black text-emerald-700">
                        {formatPrice(
                          record.total_revenue,
                          record.currency,
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}


export default SMESalesImport;