/**
 * ZAP-10: Offline / error mode support.
 *
 * Caches the last successful StatusResponse in sessionStorage so that
 * the user can see previous results when the backend is temporarily unavailable.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { StatusResponse } from "../../shared/contracts";

const CACHE_KEY = "agt:last-results";

function readCache(): StatusResponse | null {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY);
    if (raw === null) return null;
    return JSON.parse(raw) as StatusResponse;
  } catch {
    return null;
  }
}

function writeCache(snapshot: StatusResponse): void {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify(snapshot));
  } catch {
    // Storage quota exceeded or unavailable — silently ignore.
  }
}

export interface OfflineCacheState {
  /** Whether the last backend call failed with a connectivity error. */
  isOffline: boolean;
  /** The last successful response from a status check, if any. */
  cachedSnapshot: StatusResponse | null;
  /** Clear the offline flag and cached snapshot. */
  clear(): void;
}

/**
 * Call this hook once per controller mount to manage offline caching.
 *
 * Pass the latest live snapshot whenever the status response changes.
 * When the backend is unavailable (isOffline=true), the UI can fall back
 * to cachedSnapshot and show an "offline — showing last known results" banner.
 */
export function useOfflineCache(
  liveSnapshot: StatusResponse | null,
  lastError: string | null,
): OfflineCacheState {
  const [cachedSnapshot, setCachedSnapshot] = useState<StatusResponse | null>(readCache);
  const prevErrorRef = useRef<string | null>(null);
  const [isOffline, setIsOffline] = useState(false);

  // Persist live snapshots on success.
  useEffect(() => {
    if (liveSnapshot !== null && liveSnapshot.state !== null) {
      writeCache(liveSnapshot);
      setCachedSnapshot(liveSnapshot);
      setIsOffline(false);
    }
  }, [liveSnapshot]);

  // Detect connectivity errors.
  useEffect(() => {
    if (lastError !== null && lastError !== prevErrorRef.current) {
      const isConnectivity =
        lastError.includes("fetch") ||
        lastError.includes("network") ||
        lastError.includes("Failed to fetch") ||
        lastError.includes("NetworkError") ||
        lastError.includes("ECONNREFUSED");
      if (isConnectivity) {
        setIsOffline(true);
      }
    }
    prevErrorRef.current = lastError;
  }, [lastError]);

  const clear = useCallback(() => {
    setIsOffline(false);
    setCachedSnapshot(null);
    try {
      sessionStorage.removeItem(CACHE_KEY);
    } catch {
      // Ignore.
    }
  }, []);

  return { cachedSnapshot, clear, isOffline };
}
