import {
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { useNavigate } from "react-router-dom";

import {
  getNotifications,
  getUnreadNotificationCount,
  markAllNotificationsRead,
  markNotificationRead,
} from "../services/notificationService";


function formatNotificationTime(value) {
  if (!value) {
    return "";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat(
    "en-US",
    {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    },
  ).format(date);
}


function BellIcon() {
  return (
    <svg
      aria-hidden="true"
      className="size-5"
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth="1.8"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M14.857 17.082A23.848 23.848 0 0 0 18 16.75c-1.132-1.353-1.846-3.03-1.846-4.875V10.5a4.154 4.154 0 1 0-8.308 0v1.375c0 1.845-.714 3.522-1.846 4.875 1.032.177 2.08.288 3.143.332m5.714 0a3 3 0 0 1-5.714 0m5.714 0a24.255 24.255 0 0 1-5.714 0"
      />
    </svg>
  );
}


function NotificationBell() {
  const navigate = useNavigate();
  const containerRef = useRef(null);

  const [isOpen, setIsOpen] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);


  const refreshUnreadCount = useCallback(
    async () => {
      try {
        const response =
          await getUnreadNotificationCount();

        setUnreadCount(response.unread_count || 0);
      } catch {
        // Keep the header usable if a background refresh fails.
      }
    },
    [],
  );


  const loadNotifications = useCallback(
    async () => {
      setIsLoading(true);
      setErrorMessage("");

      try {
        const response = await getNotifications({
          limit: 8,
          offset: 0,
        });

        setNotifications(response.items || []);
        setUnreadCount(response.unread_count || 0);
      } catch {
        setErrorMessage(
          "Notifications could not be loaded.",
        );
      } finally {
        setIsLoading(false);
      }
    },
    [],
  );


  useEffect(() => {
    refreshUnreadCount();

    const intervalId = window.setInterval(
      refreshUnreadCount,
      20000,
    );

    function handleFocus() {
      refreshUnreadCount();
    }

    function handleNotificationsUpdated() {
      refreshUnreadCount();

      if (isOpen) {
        loadNotifications();
      }
    }

    window.addEventListener(
      "focus",
      handleFocus,
    );

    window.addEventListener(
      "vextro:notifications-updated",
      handleNotificationsUpdated,
    );

    return () => {
      window.clearInterval(intervalId);

      window.removeEventListener(
        "focus",
        handleFocus,
      );

      window.removeEventListener(
        "vextro:notifications-updated",
        handleNotificationsUpdated,
      );
    };
  }, [
    isOpen,
    loadNotifications,
    refreshUnreadCount,
  ]);


  useEffect(() => {
    function handleOutsideClick(event) {
      if (
        containerRef.current &&
        !containerRef.current.contains(event.target)
      ) {
        setIsOpen(false);
      }
    }

    document.addEventListener(
      "mousedown",
      handleOutsideClick,
    );

    return () => {
      document.removeEventListener(
        "mousedown",
        handleOutsideClick,
      );
    };
  }, []);


  async function handleToggle() {
    const nextOpenState = !isOpen;

    setIsOpen(nextOpenState);

    if (nextOpenState) {
      await loadNotifications();
    }
  }


  async function handleNotificationClick(
    notification,
  ) {
    try {
      if (!notification.is_read) {
        const updatedNotification =
          await markNotificationRead(
            notification.id,
          );

        setNotifications((currentItems) =>
          currentItems.map((item) =>
            item.id === updatedNotification.id
              ? updatedNotification
              : item,
          ),
        );

        setUnreadCount((currentCount) =>
          Math.max(0, currentCount - 1),
        );

        window.dispatchEvent(
          new Event(
            "vextro:notifications-updated",
          ),
        );
      }
    } catch {
      // Navigation still remains available.
    }

    setIsOpen(false);

    navigate(
      notification.action_path || "/alerts",
    );
  }


  async function handleMarkAllRead() {
    try {
      const response =
        await markAllNotificationsRead();

      const now = new Date().toISOString();

      setNotifications((currentItems) =>
        currentItems.map((item) => ({
          ...item,
          is_read: true,
          read_at: item.read_at || now,
        })),
      );

      setUnreadCount(
        response.unread_count || 0,
      );

      window.dispatchEvent(
        new Event(
          "vextro:notifications-updated",
        ),
      );
    } catch {
      setErrorMessage(
        "Notifications could not be updated.",
      );
    }
  }


  const badgeText =
    unreadCount > 99
      ? "99+"
      : String(unreadCount);


  return (
    <div
      ref={containerRef}
      className="relative shrink-0"
    >
      <button
        type="button"
        className="relative grid size-10 place-items-center rounded-xl border border-vextro-border bg-white text-vextro-ink transition hover:border-blue-200 hover:bg-blue-50 hover:text-vextro-primary"
        aria-label="Notifications"
        aria-expanded={isOpen}
        onClick={handleToggle}
      >
        <BellIcon />

        {unreadCount > 0 ? (
          <span className="absolute -right-1.5 -top-1.5 grid min-h-5 min-w-5 place-items-center rounded-full bg-red-500 px-1 text-[10px] font-black leading-none text-white ring-2 ring-white">
            {badgeText}
          </span>
        ) : null}
      </button>

      {isOpen ? (
        <div className="absolute right-0 top-[calc(100%+0.75rem)] z-[80] w-[min(24rem,calc(100vw-2rem))] overflow-hidden rounded-2xl border border-vextro-border bg-white shadow-2xl shadow-slate-900/10">
          <div className="flex items-center justify-between gap-4 border-b border-vextro-border px-4 py-3.5">
            <div>
              <h2 className="text-sm font-black text-vextro-ink">
                Notifications
              </h2>

              <p className="mt-0.5 text-[11px] font-medium text-vextro-muted">
                {unreadCount > 0
                  ? `${unreadCount} unread`
                  : "You're all caught up"}
              </p>
            </div>

            {unreadCount > 0 ? (
              <button
                type="button"
                className="rounded-lg px-2.5 py-1.5 text-[11px] font-bold text-vextro-primary transition hover:bg-blue-50"
                onClick={handleMarkAllRead}
              >
                Mark all read
              </button>
            ) : null}
          </div>

          <div className="max-h-96 overflow-y-auto">
            {isLoading ? (
              <div className="px-4 py-8 text-center text-sm font-medium text-vextro-muted">
                Loading notifications...
              </div>
            ) : null}

            {!isLoading && errorMessage ? (
              <div className="px-4 py-6 text-center">
                <p className="text-sm font-semibold text-red-600">
                  {errorMessage}
                </p>

                <button
                  type="button"
                  className="mt-3 rounded-lg bg-vextro-primary px-3 py-2 text-xs font-bold text-white"
                  onClick={loadNotifications}
                >
                  Try again
                </button>
              </div>
            ) : null}

            {!isLoading &&
            !errorMessage &&
            notifications.length === 0 ? (
              <div className="px-6 py-10 text-center">
                <div className="mx-auto grid size-11 place-items-center rounded-2xl bg-slate-100 text-vextro-muted">
                  <BellIcon />
                </div>

                <p className="mt-3 text-sm font-bold text-vextro-ink">
                  No notifications yet
                </p>

                <p className="mt-1 text-xs leading-5 text-vextro-muted">
                  Price alerts will appear here when
                  your target price is reached.
                </p>
              </div>
            ) : null}

            {!isLoading &&
            !errorMessage &&
            notifications.map((notification) => (
              <button
                key={notification.id}
                type="button"
                className={`flex w-full gap-3 border-b border-vextro-border px-4 py-4 text-left transition last:border-b-0 hover:bg-slate-50 ${
                  notification.is_read
                    ? "bg-white"
                    : "bg-blue-50/60"
                }`}
                onClick={() =>
                  handleNotificationClick(
                    notification,
                  )
                }
              >
                <span
                  className={`mt-1.5 size-2 shrink-0 rounded-full ${
                    notification.is_read
                      ? "bg-slate-300"
                      : "bg-vextro-primary"
                  }`}
                />

                <span className="min-w-0 flex-1">
                  <span className="block text-xs font-black text-vextro-ink">
                    {notification.title}
                  </span>

                  <span className="mt-1 block text-xs leading-5 text-vextro-muted">
                    {notification.message}
                  </span>

                  <span className="mt-2 block text-[10px] font-semibold text-slate-400">
                    {formatNotificationTime(
                      notification.created_at,
                    )}
                  </span>
                </span>
              </button>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}


export default NotificationBell;
