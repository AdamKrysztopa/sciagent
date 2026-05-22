import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function Health({ apiKey }: { apiKey: string }) {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth(apiKey),
    refetchInterval: 30_000,
  });

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Service Health</h1>
      <div className="bg-white p-6 rounded shadow max-w-md">
        {health.isLoading && <p>Checking...</p>}
        {health.isError && <p className="text-red-600">Backend unreachable</p>}
        {health.data && (
          <div className="space-y-2">
            <div className="flex justify-between">
              <span>Status</span>
              <span
                className={
                  health.data.ok
                    ? "text-green-600 font-bold"
                    : "text-red-600 font-bold"
                }
              >
                {health.data.ok ? "Healthy" : "Unhealthy"}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Provider</span>
              <span>{health.data.provider}</span>
            </div>
            <div className="flex justify-between">
              <span>Fallback</span>
              <span>{health.data.fallback_provider ?? "none"}</span>
            </div>
            <div className="flex justify-between">
              <span>Preflight</span>
              <span>
                {health.data.preflight.ok
                  ? "OK"
                  : health.data.preflight.message}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
