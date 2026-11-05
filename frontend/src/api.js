// All calls to the FastAPI backend. Errors come back as readable messages.
async function request(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.detail || `Request failed (${res.status})`);
  return body;
}

export const api = {
  business: () => request("/business"),
  forecast: () => request("/forecast"),
  customers: () => request("/customers"),
  bills: () => request("/bills"),
  memories: (q) => request(`/memories?q=${encodeURIComponent(q)}`),
  ask: (question, memory) =>
    request("/ask", { method: "POST", body: JSON.stringify({ question, memory }) }),
  feedback: (payload) => request("/feedback", { method: "POST", body: JSON.stringify(payload) }),
  outcome: (text) => request("/outcome", { method: "POST", body: JSON.stringify({ text }) }),
};
