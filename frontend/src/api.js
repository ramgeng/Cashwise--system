// All calls to the FastAPI backend. Errors come back as readable messages.
// The sign-in token and the chosen business are kept in this browser so a refresh keeps you signed in.

const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { v == null ? localStorage.removeItem(k) : localStorage.setItem(k, v); } catch { /* ignore */ } },
};

let token = store.get("cashwise-token");
let businessId = store.get("cashwise-business");
const listeners = new Set();

export const session = {
  get token() { return token; },
  get businessId() { return businessId ? Number(businessId) : null; },
  signIn(t) { token = t; store.set("cashwise-token", t); },
  useBusiness(id) { businessId = id == null ? null : String(id); store.set("cashwise-business", businessId); },
  signOut() { token = null; businessId = null; store.set("cashwise-token", null); store.set("cashwise-business", null); },
  onExpired(fn) { listeners.add(fn); return () => listeners.delete(fn); },
};

export class ApiError extends Error {
  constructor(message, status, body) { super(message); this.status = status; this.code = body?.code; this.errors = body?.errors || []; }
}

async function request(path, { method = "GET", json, form } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  if (businessId) headers["X-Business-Id"] = businessId;
  let body;
  if (json !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(json); }
  if (form) body = form;

  let res;
  try {
    res = await fetch(`/api${path}`, { method, headers, body });
  } catch {
    throw new ApiError("Can't reach the backend. Start it with: uvicorn app.main:app --reload", 0);
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && token) { session.signOut(); listeners.forEach((fn) => fn()); }
    throw new ApiError(data.detail || `Request failed (${res.status})`, res.status, data);
  }
  return data;
}

const post = (path, json) => request(path, { method: "POST", json });

export const api = {
  health: () => request("/health"),
  providers: () => request("/auth/providers"),

  // account
  login: (email, password) => post("/auth/login", { email, password }),
  register: (payload) => post("/auth/register", payload),
  me: () => request("/auth/me"),
  businesses: () => request("/businesses"),
  addBusiness: (payload) => post("/businesses", payload),

  // current business
  business: () => request("/business"),
  updateBusiness: (payload) => request("/business", { method: "PUT", json: payload }),
  deleteBusiness: () => request("/business", { method: "DELETE" }),
  forecast: () => request("/forecast"),
  actions: () => request("/actions"),
  position: () => request("/position"),
  alerts: () => request("/alerts"),
  customers: () => request("/customers"),
  bills: () => request("/bills"),
  timeline: () => request("/timeline"),
  memories: (q) => request(`/memories?q=${encodeURIComponent(q)}`),
  scenario: (changes) => post("/scenario", { changes }),
  ask: (question, memory) => post("/ask", { question, memory }),
  feedback: (payload) => post("/feedback", payload),
  outcome: (text) => post("/outcome", { text }),

  // reports
  reports: () => request("/reports"),
  makeReport: (payload) => post("/reports", payload),
  report: (id) => request(`/reports/${id}`),
  deleteReport: (id) => request(`/reports/${id}`, { method: "DELETE" }),
  printed: (id) => post(`/reports/${id}/printed`),
  emailReport: (id, payload) => post(`/reports/${id}/email`, payload),
  shareReport: (id, days) => post(`/reports/${id}/share`, { days }),
  shares: () => request("/shares"),
  revokeShare: (token) => request(`/shares/${encodeURIComponent(token)}`, { method: "DELETE" }),
  recipients: () => request("/reports-settings/recipients"),
  setRecipients: (emails) => request("/reports-settings/recipients", { method: "PUT", json: { emails } }),
  schedules: () => request("/schedules"),
  addSchedule: (payload) => post("/schedules", payload),
  editSchedule: (id, payload) => request(`/schedules/${id}`, { method: "PUT", json: payload }),
  deleteSchedule: (id) => request(`/schedules/${id}`, { method: "DELETE" }),
  runSchedule: (id) => post(`/schedules/${id}/run`),
  audit: (category) => request(`/audit${category ? `?category=${category}` : ""}`),
  publicReport: (token) => request(`/public/reports/${encodeURIComponent(token)}`),

  // data
  dataTypes: () => request("/data/types"),
  upload: (kind, file, mode) => {
    const form = new FormData();
    form.append("file", file);
    form.append("mode", mode);
    return request(`/data/upload/${kind}`, { method: "POST", form });
  },
  clearData: (kind) => request(`/data/${kind}`, { method: "DELETE" }),
  loadDemo: () => post("/data/demo"),
  syncMemory: () => post("/data/sync-memory"),
  templateUrl: (kind) => `/api/data/templates/${kind}`,
};
