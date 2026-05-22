import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

export function Users({ apiKey }: { apiKey: string }) {
  const queryClient = useQueryClient();
  const keys = useQuery({
    queryKey: ["keys"],
    queryFn: () => api.listKeys(apiKey),
  });
  const usage = useQuery({
    queryKey: ["usage"],
    queryFn: () => api.getUsage(apiKey),
  });

  const revoke = useMutation({
    mutationFn: (slug: string) => api.revokeKey(apiKey, slug),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["keys"] });
    },
  });

  if (keys.isLoading) return <p>Loading...</p>;
  if (keys.isError) return <p className="text-red-600">Failed to load users.</p>;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Users</h1>
      <table className="w-full bg-white rounded shadow">
        <thead className="bg-gray-50">
          <tr>
            <th className="text-left p-3">Slug</th>
            <th className="text-left p-3">Email</th>
            <th className="text-left p-3">Key</th>
            <th className="text-right p-3">Budget</th>
            <th className="text-right p-3">Spend</th>
            <th className="text-right p-3">Requests</th>
            <th className="text-left p-3">Admin</th>
            <th className="p-3"></th>
          </tr>
        </thead>
        <tbody>
          {keys.data?.map((u) => {
            const usg = usage.data?.[u.slug];
            return (
              <tr key={u.slug} className="border-t">
                <td className="p-3 font-mono">{u.slug}</td>
                <td className="p-3">{u.email}</td>
                <td className="p-3 font-mono text-gray-400">{u.key_suffix}</td>
                <td className="p-3 text-right">${u.budget_usd.toFixed(2)}</td>
                <td className="p-3 text-right">
                  ${usg?.spend_usd.toFixed(2) ?? "0.00"}
                </td>
                <td className="p-3 text-right">{usg?.requests ?? 0}</td>
                <td className="p-3">{u.is_admin ? "Yes" : "No"}</td>
                <td className="p-3">
                  <button
                    onClick={() => {
                      if (confirm(`Revoke ${u.slug}?`)) revoke.mutate(u.slug);
                    }}
                    className="text-red-600 hover:underline text-sm"
                    disabled={revoke.isPending}
                  >
                    Revoke
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
