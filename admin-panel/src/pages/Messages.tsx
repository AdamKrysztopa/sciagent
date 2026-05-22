import { useState } from "react";

type MessageType = "info" | "warning" | "critical";
type Channel = "banner" | "email" | "both";

export function Messages({ apiKey }: { apiKey: string }) {
  const [text, setText] = useState("");
  const [type, setType] = useState<MessageType>("info");
  const [recipients, setRecipients] = useState<"all" | string>("all");
  const [channel, setChannel] = useState<Channel>("banner");
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSent(null);
    try {
      const resp = await fetch("/admin/messages", {
        method: "POST",
        headers: {
          "X-AGT-API-Key": apiKey,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          type,
          text,
          recipients: recipients === "all" ? "all" : recipients.split(",").map((s) => s.trim()).filter(Boolean),
          channel,
        }),
      });
      if (!resp.ok) {
        const body = await resp.json().catch(() => ({})) as { detail?: string };
        throw new Error(body.detail ?? `HTTP ${resp.status}`);
      }
      const data = await resp.json() as { id: string };
      setSent(data.id);
      setText("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <h1 className="text-2xl font-bold mb-4">Send Message</h1>
      <form
        onSubmit={handleSubmit}
        className="bg-white p-6 rounded shadow max-w-lg space-y-4"
      >
        <div>
          <label className="block text-sm font-medium mb-1">Type</label>
          <select
            value={type}
            onChange={(e) => setType(e.target.value as MessageType)}
            className="w-full border rounded px-3 py-2"
          >
            <option value="info">Info</option>
            <option value="warning">Warning</option>
            <option value="critical">Critical</option>
          </select>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Message</label>
          <textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            className="w-full border rounded px-3 py-2 h-28 resize-none"
            placeholder="Your message to users..."
            required
            maxLength={2000}
          />
          <p className="text-xs text-gray-400 text-right">{text.length}/2000</p>
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Recipients</label>
          <input
            type="text"
            value={recipients}
            onChange={(e) => setRecipients(e.target.value)}
            className="w-full border rounded px-3 py-2"
            placeholder={`"all" or comma-separated slugs: alice, bob`}
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Channel</label>
          <select
            value={channel}
            onChange={(e) => setChannel(e.target.value as Channel)}
            className="w-full border rounded px-3 py-2"
          >
            <option value="banner">Banner only</option>
            <option value="email">Email only</option>
            <option value="both">Banner + Email</option>
          </select>
        </div>
        {error && <p className="text-red-600 text-sm">{error}</p>}
        {sent && (
          <p className="text-green-600 text-sm">
            Message sent (id: {sent})
          </p>
        )}
        <button
          type="submit"
          disabled={loading || text.trim().length === 0}
          className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Sending..." : "Send Message"}
        </button>
      </form>
    </div>
  );
}
