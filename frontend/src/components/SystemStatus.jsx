import { useEffect, useState } from "react";

import { getPlatforms } from "../services/catalogService";

function extractPlatforms(responseData) {
  if (Array.isArray(responseData)) {
    return responseData;
  }

  if (Array.isArray(responseData?.items)) {
    return responseData.items;
  }

  return [];
}

function SystemStatus() {
  const [status, setStatus] = useState("checking");
  const [platformCount, setPlatformCount] = useState(0);

  useEffect(() => {
    let isMounted = true;

    async function checkBackendConnection() {
      try {
        const responseData = await getPlatforms();
        const platforms = extractPlatforms(responseData);

        if (!isMounted) {
          return;
        }

        setPlatformCount(platforms.length);
        setStatus("connected");
      } catch {
        if (!isMounted) {
          return;
        }

        setPlatformCount(0);
        setStatus("offline");
      }
    }

    checkBackendConnection();

    return () => {
      isMounted = false;
    };
  }, []);

  if (status === "checking") {
    return (
      <div
        className="inline-flex items-center gap-3 rounded-full border border-slate-200 bg-white/80 px-4 py-2 text-xs font-bold text-vextro-muted shadow-sm backdrop-blur"
        role="status"
      >
        <span className="size-2.5 animate-pulse rounded-full bg-amber-400" />
        Checking VEXTRO API...
      </div>
    );
  }

  if (status === "offline") {
    return (
      <div
        className="inline-flex items-center gap-3 rounded-full border border-red-200 bg-red-50 px-4 py-2 text-xs font-bold text-red-700"
        role="alert"
      >
        <span className="size-2.5 rounded-full bg-red-500" />
        Backend connection unavailable
      </div>
    );
  }

  return (
    <div
      className="inline-flex items-center gap-3 rounded-full border border-emerald-200 bg-emerald-50 px-4 py-2 text-xs font-bold text-emerald-700"
      role="status"
    >
      <span className="relative flex size-2.5">
        <span className="absolute inline-flex size-full animate-ping rounded-full bg-emerald-400 opacity-70" />
        <span className="relative inline-flex size-2.5 rounded-full bg-emerald-500" />
      </span>

      Backend connected · {platformCount} marketplace
      {platformCount === 1 ? "" : "s"} available
    </div>
  );
}

export default SystemStatus;