import { useEffect, useRef, useState } from "react";

/**
 * Polling hook: runs `fn` immediately and then every `ms`.
 * Pauses while a refresh is already in flight (avoids pile-up).
 */
export function usePolling(fn, ms = 10000, deps = []) {
  const busy = useRef(false);

  useEffect(() => {
    let interval;
    let cancelled = false;

    const run = async () => {
      if (busy.current) return;
      busy.current = true;
      try {
        await fn();
      } finally {
        busy.current = false;
      }
    };

    run();
    interval = setInterval(() => {
      if (!cancelled) run();
    }, ms);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}

/** Relative time from an ISO-ish timestamp string. */
export function timeAgo(stamp) {
  if (!stamp) return "";
  const then = new Date(stamp).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "agora";
  if (min < 60) return `${min}m`;
  const hours = Math.floor(min / 60);
  if (hours < 24) return `${hours}h`;
  return `${Math.floor(hours / 24)}d`;
}

/** Clock string for the topbar. */
export function useClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);
  return now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}
