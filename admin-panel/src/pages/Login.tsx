import { useState } from "react";
import { api } from "../api";

export function Login({ onLogin }: { onLogin: (key: string) => void }) {
  const [key, setKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.listKeys(key);
      onLogin(key);
    } catch {
      setError("Invalid admin API key.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex items-center justify-center min-h-screen bg-gray-50">
      <form
        onSubmit={handleSubmit}
        className="bg-white p-8 rounded shadow-md w-96"
      >
        <h1 className="text-xl font-bold mb-4">SciAgent Admin</h1>
        <label className="block mb-2 text-sm font-medium">API Key</label>
        <input
          type="password"
          value={key}
          onChange={(e) => setKey(e.target.value)}
          className="w-full border rounded px-3 py-2 mb-4"
          placeholder="agt_admin_..."
          required
        />
        {error && <p className="text-red-600 text-sm mb-4">{error}</p>}
        <button
          type="submit"
          disabled={loading || key.length === 0}
          className="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Checking..." : "Login"}
        </button>
      </form>
    </div>
  );
}
