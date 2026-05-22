import { useQuery } from "@tanstack/react-query";
import { api } from "../api";

export function Dashboard({ apiKey }: { apiKey: string }) {
  const keys = useQuery({
    queryKey: ["keys"],
    queryFn: () => api.listKeys(apiKey),
  });
  const usage = useQuery({
    queryKey: ["usage"],
    queryFn: () => api.getUsage(apiKey),
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api.getHealth(apiKey),
  });

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">Dashboard</h1>
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-white p-4 rounded shadow">
          <p className="text-sm text-gray-500">Active Users</p>
          <p className="text-3xl font-bold">{keys.data?.length ?? "—"}</p>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <p className="text-sm text-gray-500">Total Spend</p>
          <p className="text-3xl font-bold">
            {usage.data
              ? `$${Object.values(usage.data)
                  .reduce((s, u) => s + u.spend_usd, 0)
                  .toFixed(2)}`
              : "—"}
          </p>
        </div>
        <div className="bg-white p-4 rounded shadow">
          <p className="text-sm text-gray-500">Backend</p>
          <p className="text-3xl font-bold">
            {health.data?.ok
              ? "Healthy"
              : health.isError
                ? "Error"
                : "—"}
          </p>
        </div>
      </div>
    </div>
  );
}
