export type Turn = { role: "user" | "assistant"; text: string };

// Base URL for the API. In dev this is empty so Vite proxies "/api" to the
// backend; in prod set VITE_API_URL to the API origin (e.g. https://api.example.com).
const API_BASE = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export function apiUrl(path: string): string {
  return `${API_BASE}/api${path}`;
}

/** WebSocket URL for a given /api path (handles http->ws, https->wss). */
export function wsUrl(path: string): string {
  const base =
    API_BASE ||
    (typeof window !== "undefined" ? window.location.origin : "");
  const url = new URL(`/api${path}`, base);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

let authToken: string | null =
  typeof localStorage !== "undefined" ? localStorage.getItem("lc_token") : null;

export function setAuthToken(token: string | null) {
  authToken = token;
  if (typeof localStorage !== "undefined") {
    if (token) localStorage.setItem("lc_token", token);
    else localStorage.removeItem("lc_token");
  }
}

function authHeaders(): Record<string, string> {
  return authToken ? { Authorization: `Bearer ${authToken}` } : {};
}

export class ApiError extends Error {
  status: number;
  detail: any;
  constructor(status: number, detail: any, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function errorMessage(status: number, detail: any): string {
  // FastAPI's `detail` can be a string OR a structured object (e.g. the 402
  // paywall returns { message, entitlement }). Extract a human message.
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    if (typeof detail.message === "string") return detail.message;
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg;
  }
  return `Request failed (${status})`;
}

async function post(path: string, body: unknown) {
  const r = await fetch(apiUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    const detail = payload?.detail ?? payload;
    throw new ApiError(r.status, detail, errorMessage(r.status, detail));
  }
  return r.json();
}

async function get(path: string) {
  const r = await fetch(apiUrl(path), { headers: authHeaders() });
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    const detail = payload?.detail ?? payload;
    throw new ApiError(r.status, detail, errorMessage(r.status, detail));
  }
  return r.json();
}

async function del(path: string) {
  const r = await fetch(apiUrl(path), {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!r.ok) {
    const payload = await r.json().catch(() => ({}));
    const detail = payload?.detail ?? payload;
    throw new ApiError(r.status, detail, errorMessage(r.status, detail));
  }
  return r.json();
}

export const api = {
  health: () => get("/health"),
  config: () => get("/config"),
  personas: () => get("/personas"),
  focuses: () => get("/interview/focuses"),
  tracks: () => get("/catalog/tracks"),
  companies: () => get("/catalog/companies"),
  difficulties: () => get("/catalog/difficulties"),
  designTopics: () => get("/catalog/design-topics"),
  hintTiers: () => get("/catalog/hint-tiers"),
  login: (username: string) => post("/login", { username }),
  // Real auth (email + password -> JWT)
  register: (email: string, password: string, username?: string) =>
    post("/auth/register", { email, password, username }),
  authLogin: (email: string, password: string) =>
    post("/auth/login", { email, password }),
  me: () => get("/auth/me"),
  startSession: (payload: any) => post("/sessions", payload),
  getSession: (id: string) => get(`/sessions/${id}`),
  requestHint: (id: string, payload: any) =>
    post(`/sessions/${id}/hint`, payload),
  realtimeSession: (payload: any) => post("/realtime/session", payload),
  chat: (payload: any) => post("/chat", payload),
  saveConversation: (payload: any) => post("/conversations", payload),
  gradeInterview: (payload: any) => post("/interview/grade", payload),
  coaching: (payload: any) => post("/interview/coaching", payload),
  history: (username: string) => get(`/history/${username}`),
  stats: () => get("/stats"),
  replay: (reportId: number) => get(`/replay/${reportId}`),
  leaderboard: (track?: string) =>
    get(`/leaderboard${track ? `?track=${track}` : ""}`),
  challenge: () => get("/challenge"),
  companyPacks: () => get("/company-packs"),
  learningPaths: () => get("/learning-paths"),
  reviewQueue: () => get("/review-queue"),
  getResume: () => get("/resume"),
  clearResume: () => del("/resume"),
  uploadResume: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const r = await fetch(apiUrl("/resume/upload"), {
      method: "POST",
      headers: { ...authHeaders() },
      body: fd,
    });
    if (!r.ok) {
      const payload = await r.json().catch(() => ({}));
      const detail = payload?.detail ?? payload;
      throw new ApiError(r.status, detail, errorMessage(r.status, detail));
    }
    return r.json();
  },
  // Coding round
  codingLanguages: () => get("/sessions/coding/languages"),
  getProblem: (id: string, payload: any = {}) =>
    post(`/sessions/${id}/problem`, payload),
  runCode: (id: string, payload: any) => post(`/sessions/${id}/run`, payload),
  submitCode: (id: string, payload: any) => post(`/sessions/${id}/submit`, payload),
  // Design whiteboard
  submitDiagram: (id: string, payload: any) =>
    post(`/sessions/${id}/diagram`, payload),
  // Billing
  plans: () => get("/billing/plans"),
  entitlement: () => get("/billing/me"),
  createOrder: (packId: string, provider?: string) =>
    post("/billing/order", { pack_id: packId, provider }),
  devGrant: (packId: string) => post("/billing/dev-grant", { pack_id: packId }),
};
