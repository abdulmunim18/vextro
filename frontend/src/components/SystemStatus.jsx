import { useEffect, useState } from "react";

import { getPlatforms } from "../services/catalogService";
import { getApiErrorMessage } from "../utils/apiError";

function SystemStatus() {
  const [status, setStatus] = useState("checking");
  const [message, setMessage] = useState(
    "Connecting to VEXTRO backend...",
  );

  useEffect(() => {
    let isMounted = true;

    async function checkBackendConnection() {
      try {
        const platformData = await getPlatforms();

        if (!isMounted) {
          return;
        }

        const platforms = Array.isArray(platformData)
          ? platformData
          : platformData?.items || [];

        setStatus("connected");

        setMessage(
          `Backend connected · ${platforms.length} marketplace${
            platforms.length === 1 ? "" : "s"
          } available`,
        );
      } catch (error) {
        if (!isMounted) {
          return;
        }

        setStatus("error");

        setMessage(
          getApiErrorMessage(
            error,
            "VEXTRO backend is currently unavailable.",
          ),
        );
      }
    }

    checkBackendConnection();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className={`system-status system-status-${status}`}>
      <span className="system-status-dot" />
      <span>{message}</span>
    </div>
  );
}

export default SystemStatus;