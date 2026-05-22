import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { Login } from "./pages/Login";
import { Dashboard } from "./pages/Dashboard";
import { Users } from "./pages/Users";
import { CreateUser } from "./pages/CreateUser";
import { Health } from "./pages/Health";
import { Messages } from "./pages/Messages";

const queryClient = new QueryClient();

type Page = "dashboard" | "users" | "create-user" | "health" | "messages";

export default function App() {
  const [apiKey, setApiKey] = useState<string | null>(
    () => sessionStorage.getItem("agt-admin-key"),
  );
  const [page, setPage] = useState<Page>("dashboard");

  if (apiKey === null) {
    return (
      <Login
        onLogin={(key) => {
          sessionStorage.setItem("agt-admin-key", key);
          setApiKey(key);
        }}
      />
    );
  }

  const nav = (
    <nav className="flex gap-4 p-4 bg-gray-100 border-b">
      <button
        onClick={() => setPage("dashboard")}
        className={page === "dashboard" ? "font-bold" : ""}
      >
        Dashboard
      </button>
      <button
        onClick={() => setPage("users")}
        className={page === "users" ? "font-bold" : ""}
      >
        Users
      </button>
      <button
        onClick={() => setPage("create-user")}
        className={page === "create-user" ? "font-bold" : ""}
      >
        Create User
      </button>
      <button
        onClick={() => setPage("health")}
        className={page === "health" ? "font-bold" : ""}
      >
        Health
      </button>
      <button
        onClick={() => setPage("messages")}
        className={page === "messages" ? "font-bold" : ""}
      >
        Messages
      </button>
      <button
        onClick={() => {
          sessionStorage.removeItem("agt-admin-key");
          setApiKey(null);
        }}
        className="ml-auto text-red-600"
      >
        Logout
      </button>
    </nav>
  );

  return (
    <QueryClientProvider client={queryClient}>
      {nav}
      <main className="p-6 max-w-5xl mx-auto">
        {page === "dashboard" && <Dashboard apiKey={apiKey} />}
        {page === "users" && <Users apiKey={apiKey} />}
        {page === "create-user" && (
          <CreateUser apiKey={apiKey} onCreated={() => setPage("users")} />
        )}
        {page === "health" && <Health apiKey={apiKey} />}
        {page === "messages" && <Messages apiKey={apiKey} />}
      </main>
    </QueryClientProvider>
  );
}
