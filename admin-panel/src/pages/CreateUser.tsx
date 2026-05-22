import { useState } from "react";
import { api } from "../api";

export function CreateUser({
  apiKey,
  onCreated,
}: {
  apiKey: string;
  onCreated: () => void;
}) {
  const [slug, setSlug] = useState("");
  const [email, setEmail] = useState("");
  const [budget, setBudget] = useState("2.00");
  const [error, setError] = useState<string | null>(null);
  const [createdKey, setCreatedKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const resp = await api.createKey(apiKey, {
        slug,
        email,
        budget_usd: parseFloat(budget),
      });
      setCreatedKey(resp.key);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create user");
    } finally {
      setLoading(false);
    }
  }

  if (createdKey !== null) {
    return (
      <div className="bg-white p-6 rounded shadow max-w-md">
        <h2 className="text-xl font-bold mb-4 text-green-700">User Created</h2>
        <p className="mb-2">
          API key for <strong>{slug}</strong>:
        </p>
        <code className="block bg-gray-100 p-3 rounded break-all mb-4">
          {createdKey}
        </code>
        <p className="text-sm text-gray-500 mb-4">
          Copy this key now — it cannot be shown again.
        </p>
        <button
          onClick={onCreated}
          className="bg-blue-600 text-white px-4 py-2 rounded"
        >
          Done
        </button>
      </div>
    );
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Create User</h1>
      <form
        onSubmit={handleSubmit}
        className="bg-white p-6 rounded shadow max-w-md space-y-4"
      >
        <div>
          <label className="block text-sm font-medium mb-1">Slug</label>
          <input
            type="text"
            value={slug}
            onChange={(e) =>
              setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9_-]/g, ""))
            }
            className="w-full border rounded px-3 py-2"
            placeholder="alice"
            required
            maxLength={32}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border rounded px-3 py-2"
            placeholder="alice@example.com"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Budget (USD)</label>
          <input
            type="number"
            value={budget}
            onChange={(e) => setBudget(e.target.value)}
            className="w-full border rounded px-3 py-2"
            step="0.50"
            min="0"
          />
        </div>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        <button
          type="submit"
          disabled={loading || slug.length === 0 || email.length === 0}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Creating..." : "Create User"}
        </button>
      </form>
    </div>
  );
}
