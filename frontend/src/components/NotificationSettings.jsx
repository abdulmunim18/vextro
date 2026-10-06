import {
  useCallback,
  useEffect,
  useState,
} from "react";

import { useAuth } from "../context/useAuth";
import {
  PUSH_PERMISSION,
  disableBrowserPush,
  enableBrowserPush,
  getNotificationPreferences,
  isPushSupported,
  readPushPermission,
  updateNotificationPreferences,
} from "../services/pushNotificationService";
import { getApiErrorMessage } from "../utils/apiError";

const DIGEST_OPTIONS = [
  {
    value: "off",
    label: "Off",
    hint: "No digest emails",
  },
  {
    value: "daily",
    label: "Daily",
    hint: "One summary each morning",
  },
  {
    value: "weekly",
    label: "Weekly",
    hint: "One summary each week",
  },
];

function ToggleRow({
  label,
  description,
  isChecked,
  isDisabled,
  disabledHint,
  onChange,
}) {
  return (
    <label
      className={`flex items-start justify-between gap-4 rounded-xl border border-vextro-border bg-white p-4 transition ${
        isDisabled
          ? "cursor-not-allowed opacity-60"
          : "cursor-pointer hover:border-blue-200 hover:bg-blue-50/40"
      }`}
    >
      <span className="min-w-0">
        <span className="block text-sm font-black text-vextro-ink">
          {label}
        </span>

        <span className="mt-1 block text-xs leading-5 text-vextro-muted">
          {isDisabled && disabledHint
            ? disabledHint
            : description}
        </span>
      </span>

      <input
        checked={isChecked}
        className="mt-1 size-5 shrink-0 accent-vextro-primary"
        disabled={isDisabled}
        type="checkbox"
        onChange={(event) =>
          onChange(event.target.checked)
        }
      />
    </label>
  );
}

function NotificationSettings() {
  const { hasRole } = useAuth();

  const showCompetitorSettings = hasRole("sme");

  const showPriceAlertSettings = hasRole("consumer");

  const [preferences, setPreferences] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [statusMessage, setStatusMessage] = useState("");

  const [pushPermission, setPushPermission] = useState(
    () => readPushPermission(),
  );

  const loadPreferences = useCallback(async () => {
    try {
      const response = await getNotificationPreferences();

      setPreferences(response);
      setErrorMessage("");
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Notification settings could not be loaded.",
        ),
      );
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    let isMounted = true;

    async function restorePreferences() {
      try {
        const response = await getNotificationPreferences();

        if (isMounted) {
          setPreferences(response);
        }
      } catch (error) {
        if (isMounted) {
          setErrorMessage(
            getApiErrorMessage(
              error,
              "Notification settings could not be loaded.",
            ),
          );
        }
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    restorePreferences();

    return () => {
      isMounted = false;
    };
  }, []);

  const savePreferences = useCallback(
    async (changes) => {
      setIsSaving(true);
      setErrorMessage("");
      setStatusMessage("");

      const previousPreferences = preferences;

      setPreferences((current) =>
        current ? { ...current, ...changes } : current,
      );

      try {
        const response =
          await updateNotificationPreferences(changes);

        setPreferences(response);
        setStatusMessage("Notification settings saved.");
      } catch (error) {
        setPreferences(previousPreferences);

        setErrorMessage(
          getApiErrorMessage(
            error,
            "Notification settings could not be saved.",
          ),
        );
      } finally {
        setIsSaving(false);
      }
    },
    [preferences],
  );

  async function handleEnablePush() {
    setErrorMessage("");
    setStatusMessage("");

    try {
      const result = await enableBrowserPush({
        vapidPublicKey: preferences?.vapid_public_key,
      });

      setPushPermission(readPushPermission());

      if (result.status === PUSH_PERMISSION.granted) {
        setStatusMessage(
          "Browser notifications are enabled on this device.",
        );

        await loadPreferences();
        return;
      }

      if (result.status === PUSH_PERMISSION.denied) {
        setErrorMessage(
          "Your browser blocked notifications. Allow them in the site " +
            "permissions and try again.",
        );
        return;
      }

      if (result.status === "not_configured") {
        setErrorMessage(
          "Browser push is not configured on this VEXTRO server yet.",
        );
        return;
      }

      if (result.status === PUSH_PERMISSION.unsupported) {
        setErrorMessage(
          "This browser does not support Web Push notifications.",
        );
        return;
      }

      setStatusMessage(
        "Browser notifications were not enabled.",
      );
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Browser notifications could not be enabled.",
        ),
      );
    }
  }

  async function handleDisablePush() {
    setErrorMessage("");
    setStatusMessage("");

    try {
      await disableBrowserPush();

      setStatusMessage(
        "Browser notifications are turned off on this device.",
      );

      await loadPreferences();
    } catch (error) {
      setErrorMessage(
        getApiErrorMessage(
          error,
          "Browser notifications could not be turned off.",
        ),
      );
    }
  }

  if (isLoading) {
    return (
      <section className="rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-7">
        <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
          Notification Settings
        </span>

        <p className="mt-5 text-sm font-medium text-vextro-muted">
          Loading notification settings...
        </p>
      </section>
    );
  }

  const pushSupported = isPushSupported();

  const hasActiveSubscription =
    (preferences?.active_push_subscription_count || 0) > 0;

  const isEmailConfigured = Boolean(
    preferences?.is_email_configured,
  );

  const isPushConfigured = Boolean(
    preferences?.is_push_configured,
  );

  const emailDisabledHint =
    "Email delivery is not configured on this VEXTRO server.";

  const pushDisabledHint = !pushSupported
    ? "This browser does not support Web Push notifications."
    : !isPushConfigured
      ? "Browser push is not configured on this VEXTRO server."
      : "Enable browser notifications on this device first.";

  const isPushToggleDisabled =
    !pushSupported ||
    !isPushConfigured ||
    !hasActiveSubscription;

  return (
    <section className="rounded-3xl border border-vextro-border bg-white p-6 shadow-sm sm:p-7">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <span className="text-xs font-black uppercase tracking-[0.16em] text-vextro-primary">
            Notification Settings
          </span>

          <h2 className="mt-3 text-xl font-black tracking-[-0.02em] text-vextro-ink">
            Choose how VEXTRO reaches you
          </h2>

          <p className="mt-2 max-w-xl text-xs leading-5 text-vextro-muted">
            In-app notifications always stay on. Email and browser push
            are optional extras you control per alert type.
          </p>
        </div>

        {isSaving ? (
          <span className="text-[11px] font-bold text-vextro-muted">
            Saving...
          </span>
        ) : null}
      </div>

      {errorMessage ? (
        <div
          className="mt-5 rounded-2xl border border-red-200 bg-red-50 p-4 text-xs font-semibold leading-5 text-red-700"
          role="alert"
        >
          {errorMessage}
        </div>
      ) : null}

      {statusMessage ? (
        <div
          className="mt-5 rounded-2xl border border-emerald-200 bg-emerald-50 p-4 text-xs font-semibold leading-5 text-emerald-700"
          role="status"
        >
          {statusMessage}
        </div>
      ) : null}

      <div className="mt-6 rounded-2xl border border-blue-100 bg-blue-50/60 p-4">
        <h3 className="text-sm font-black text-vextro-ink">
          Browser notifications on this device
        </h3>

        <p className="mt-1.5 text-xs leading-5 text-vextro-muted">
          VEXTRO can show a desktop notification the moment a tracked
          price moves, even when this tab is closed. Your browser will ask
          for permission once.
        </p>

        <div className="mt-3 flex flex-wrap items-center gap-3">
          {hasActiveSubscription ? (
            <button
              className="inline-flex min-h-10 items-center justify-center rounded-xl border border-vextro-border bg-white px-4 text-xs font-black text-vextro-ink transition hover:border-red-200 hover:bg-red-50 hover:text-red-700"
              type="button"
              onClick={handleDisablePush}
            >
              Turn off browser notifications
            </button>
          ) : (
            <button
              className="inline-flex min-h-10 items-center justify-center rounded-xl bg-vextro-primary px-4 text-xs font-black text-white transition hover:bg-vextro-primary-dark disabled:cursor-not-allowed disabled:opacity-50"
              disabled={!pushSupported || !isPushConfigured}
              type="button"
              onClick={handleEnablePush}
            >
              Enable browser notifications
            </button>
          )}

          <span className="text-[11px] font-bold text-vextro-muted">
            {!pushSupported
              ? "Not supported in this browser"
              : !isPushConfigured
                ? "Not configured on this server"
                : hasActiveSubscription
                  ? `Active on ${preferences.active_push_subscription_count} device(s)`
                  : pushPermission === PUSH_PERMISSION.denied
                    ? "Blocked in browser permissions"
                    : pushPermission === PUSH_PERMISSION.granted
                      ? "Permission granted, not subscribed yet"
                      : "Permission not requested yet"}
          </span>
        </div>
      </div>

      {showPriceAlertSettings ? (
        <div className="mt-6">
          <h3 className="text-[11px] font-black uppercase tracking-[0.16em] text-vextro-muted">
            Price alerts
          </h3>

          <div className="mt-3 grid gap-3">
            <ToggleRow
              description="Always delivered to your notification bell."
              isChecked
              isDisabled
              disabledHint="Always delivered to your notification bell."
              label="In app"
              onChange={() => {}}
            />

            <ToggleRow
              description="Email me when a target price is reached."
              disabledHint={emailDisabledHint}
              isChecked={Boolean(
                preferences?.price_alert_email,
              )}
              isDisabled={!isEmailConfigured}
              label="Email"
              onChange={(nextValue) =>
                savePreferences({
                  price_alert_email: nextValue,
                })
              }
            />

            <ToggleRow
              description="Show a browser notification on subscribed devices."
              disabledHint={pushDisabledHint}
              isChecked={Boolean(
                preferences?.price_alert_push,
              )}
              isDisabled={isPushToggleDisabled}
              label="Browser push"
              onChange={(nextValue) =>
                savePreferences({
                  price_alert_push: nextValue,
                })
              }
            />
          </div>
        </div>
      ) : null}

      {showCompetitorSettings ? (
        <div className="mt-6">
          <h3 className="text-[11px] font-black uppercase tracking-[0.16em] text-vextro-muted">
            Competitor alerts
          </h3>

          <div className="mt-3 grid gap-3">
            <ToggleRow
              description="Always delivered to your notification bell."
              isChecked
              isDisabled
              disabledHint="Always delivered to your notification bell."
              label="In app"
              onChange={() => {}}
            />

            <ToggleRow
              description="Email me when a competitor threatens your price."
              disabledHint={emailDisabledHint}
              isChecked={Boolean(
                preferences?.competitor_alert_email,
              )}
              isDisabled={!isEmailConfigured}
              label="Email"
              onChange={(nextValue) =>
                savePreferences({
                  competitor_alert_email: nextValue,
                })
              }
            />

            <ToggleRow
              description="Show a browser notification on subscribed devices."
              disabledHint={pushDisabledHint}
              isChecked={Boolean(
                preferences?.competitor_alert_push,
              )}
              isDisabled={isPushToggleDisabled}
              label="Browser push"
              onChange={(nextValue) =>
                savePreferences({
                  competitor_alert_push: nextValue,
                })
              }
            />
          </div>
        </div>
      ) : null}

      <div className="mt-6">
        <h3 className="text-[11px] font-black uppercase tracking-[0.16em] text-vextro-muted">
          Digest reports
        </h3>

        <p className="mt-2 text-xs leading-5 text-vextro-muted">
          A summary email of the period&apos;s activity, scheduled in{" "}
          {preferences?.digest_timezone || "the server timezone"}. VEXTRO
          skips the email entirely when nothing happened.
        </p>

        <div
          className="mt-3 grid gap-3 sm:grid-cols-3"
          role="radiogroup"
          aria-label="Digest frequency"
        >
          {DIGEST_OPTIONS.map((option) => {
            const isSelected =
              preferences?.digest_frequency === option.value;

            return (
              <button
                key={option.value}
                aria-checked={isSelected}
                className={`rounded-xl border p-4 text-left transition disabled:cursor-not-allowed disabled:opacity-60 ${
                  isSelected
                    ? "border-vextro-primary bg-blue-50"
                    : "border-vextro-border bg-white hover:border-blue-200 hover:bg-blue-50/40"
                }`}
                disabled={
                  !isEmailConfigured && option.value !== "off"
                }
                role="radio"
                type="button"
                onClick={() =>
                  savePreferences({
                    digest_frequency: option.value,
                  })
                }
              >
                <span className="block text-sm font-black text-vextro-ink">
                  {option.label}
                </span>

                <span className="mt-1 block text-[11px] leading-4 text-vextro-muted">
                  {!isEmailConfigured && option.value !== "off"
                    ? emailDisabledHint
                    : option.hint}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export default NotificationSettings;
