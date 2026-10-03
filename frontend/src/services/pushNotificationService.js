import apiClient from "../api/httpClient";

const SERVICE_WORKER_PATH = "/service-worker.js";

export const PUSH_PERMISSION = {
  granted: "granted",
  denied: "denied",
  default: "default",
  unsupported: "unsupported",
};

export function isPushSupported() {
  return (
    typeof window !== "undefined" &&
    "serviceWorker" in navigator &&
    "PushManager" in window &&
    "Notification" in window
  );
}

export function readPushPermission() {
  if (!isPushSupported()) {
    return PUSH_PERMISSION.unsupported;
  }

  return Notification.permission;
}

function urlBase64ToUint8Array(base64String) {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);

  const base64 = (base64String + padding)
    .replace(/-/g, "+")
    .replace(/_/g, "/");

  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);

  for (let index = 0; index < rawData.length; index += 1) {
    outputArray[index] = rawData.charCodeAt(index);
  }

  return outputArray;
}

export async function registerServiceWorker() {
  if (!isPushSupported()) {
    return null;
  }

  const existingRegistration =
    await navigator.serviceWorker.getRegistration(SERVICE_WORKER_PATH);

  if (existingRegistration) {
    return existingRegistration;
  }

  return navigator.serviceWorker.register(SERVICE_WORKER_PATH, {
    scope: "/",
  });
}

export async function getNotificationPreferences() {
  const response = await apiClient.get(
    "/notifications/preferences",
  );

  return response.data;
}

export async function updateNotificationPreferences(changes) {
  const response = await apiClient.patch(
    "/notifications/preferences",
    changes,
  );

  return response.data;
}

async function sendSubscriptionToBackend(subscription) {
  const subscriptionJson = subscription.toJSON();

  const response = await apiClient.post(
    "/notifications/push/subscribe",
    {
      endpoint: subscriptionJson.endpoint,
      keys: {
        p256dh: subscriptionJson.keys?.p256dh,
        auth: subscriptionJson.keys?.auth,
      },
    },
  );

  return response.data;
}

/*
 * Permission is requested here and nowhere else, so the browser prompt
 * only ever appears after the user clicks "Enable browser notifications".
 */
export async function enableBrowserPush({ vapidPublicKey }) {
  if (!isPushSupported()) {
    return {
      status: PUSH_PERMISSION.unsupported,
    };
  }

  const applicationServerKey =
    vapidPublicKey ||
    import.meta.env.VITE_VAPID_PUBLIC_KEY ||
    "";

  if (!applicationServerKey) {
    return {
      status: "not_configured",
    };
  }

  const permission = await Notification.requestPermission();

  if (permission !== PUSH_PERMISSION.granted) {
    return {
      status: permission,
    };
  }

  const registration = await registerServiceWorker();

  if (!registration) {
    return {
      status: PUSH_PERMISSION.unsupported,
    };
  }

  await navigator.serviceWorker.ready;

  const existingSubscription =
    await registration.pushManager.getSubscription();

  const subscription =
    existingSubscription ||
    (await registration.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(
        applicationServerKey,
      ),
    }));

  await sendSubscriptionToBackend(subscription);

  return {
    status: PUSH_PERMISSION.granted,
  };
}

export async function disableBrowserPush() {
  if (!isPushSupported()) {
    return { status: PUSH_PERMISSION.unsupported };
  }

  const registration =
    await navigator.serviceWorker.getRegistration(
      SERVICE_WORKER_PATH,
    );

  const subscription = registration
    ? await registration.pushManager.getSubscription()
    : null;

  if (subscription) {
    try {
      await apiClient.delete(
        "/notifications/push/unsubscribe",
        {
          data: {
            endpoint: subscription.endpoint,
          },
        },
      );
    } finally {
      await subscription.unsubscribe();
    }
  }

  return { status: "disabled" };
}
