/*
 * VEXTRO Web Push service worker.
 *
 * Served from /service-worker.js so its scope covers the whole app. It
 * only handles push delivery and notification clicks; it does not cache
 * or intercept any application request.
 */

const DEFAULT_TITLE = "VEXTRO";
const DEFAULT_BODY = "You have a new VEXTRO notification.";
const FALLBACK_PATH = "/dashboard";

self.addEventListener("install", () => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

function readPushPayload(event) {
  if (!event.data) {
    return {};
  }

  try {
    return event.data.json() || {};
  } catch {
    try {
      return { body: event.data.text() };
    } catch {
      return {};
    }
  }
}

/*
 * Only same-origin absolute paths are ever opened, so a crafted payload
 * cannot turn a notification click into an open redirect.
 */
function safeTargetPath(actionPath) {
  if (typeof actionPath !== "string") {
    return FALLBACK_PATH;
  }

  if (!actionPath.startsWith("/") || actionPath.startsWith("//")) {
    return FALLBACK_PATH;
  }

  return actionPath;
}

self.addEventListener("push", (event) => {
  const payload = readPushPayload(event);

  const title =
    typeof payload.title === "string" && payload.title
      ? payload.title
      : DEFAULT_TITLE;

  const body =
    typeof payload.body === "string" && payload.body
      ? payload.body
      : DEFAULT_BODY;

  const targetPath = safeTargetPath(payload.action_path);

  event.waitUntil(
    self.registration.showNotification(title, {
      body,
      icon: "/favicon.svg",
      badge: "/favicon.svg",
      tag: typeof payload.tag === "string" ? payload.tag : undefined,
      renotify: false,
      data: {
        targetPath,
      },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();

  const targetPath = safeTargetPath(event.notification.data?.targetPath);
  const targetUrl = new URL(targetPath, self.location.origin).href;

  event.waitUntil(
    self.clients
      .matchAll({
        type: "window",
        includeUncontrolled: true,
      })
      .then((windowClients) => {
        for (const windowClient of windowClients) {
          if (new URL(windowClient.url).origin !== self.location.origin) {
            continue;
          }

          if ("focus" in windowClient) {
            windowClient.focus();

            if ("navigate" in windowClient) {
              return windowClient.navigate(targetUrl);
            }

            return undefined;
          }
        }

        if (self.clients.openWindow) {
          return self.clients.openWindow(targetUrl);
        }

        return undefined;
      }),
  );
});
