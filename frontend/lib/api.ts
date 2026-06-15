/**
 * Typed API client — all fetch wrappers for the CRM backend.
 *
 * Usage:
 *   import { api } from "@/lib/api";
 *   const customers = await api.customers.list({ page: 1, limit: 50 });
 */

const BASE_URL = process.env.NEXT_PUBLIC_CRM_API_URL ?? "http://localhost:8000";

/** Resolve the multi-tenant scope header from the stored session. */
export function orgHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  try {
    const s = JSON.parse(localStorage.getItem("orbit_session") || "null");
    if (!s) return {};
    if (s.role === "admin") return { "X-Org-Id": "ALL" };
    if (s.org_uuid) return { "X-Org-Id": s.org_uuid };
  } catch {
    /* ignore */
  }
  return {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}/api/v1${path}`, {
    headers: { "Content-Type": "application/json", ...orgHeader(), ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error?.detail ?? `API error ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── Customers ─────────────────────────────────────────────────────────────────
export const customers = {
  list: (params?: {
    page?: number;
    limit?: number;
    search?: string;
    churn_risk?: string;
    sort_by?: string;
    sort_dir?: string;
  }) => {
    const qs = new URLSearchParams(
      Object.entries(params ?? {}).filter(([, v]) => v != null) as [string, string][]
    ).toString();
    return request<any>(`/customers${qs ? "?" + qs : ""}`);
  },
  get: (id: string) => request<any>(`/customers/${id}`),
  semanticSearch: (query: string, limit = 12) =>
    request<any>("/customers/semantic-search", {
      method: "POST",
      body: JSON.stringify({ query, limit }),
    }),
  similar: (id: string) => request<any>(`/customers/${id}/similar`),
  create: (body: any) =>
    request<any>("/customers", { method: "POST", body: JSON.stringify(body) }),
  remove: (id: string) => request<any>(`/customers/${id}`, { method: "DELETE" }),
  removeAll: () => request<any>("/customers", { method: "DELETE" }),
  import: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE_URL}/api/v1/customers/import`, {
      method: "POST",
      body: fd,
      headers: orgHeader(),
    }).then((r) => r.json());
  },
};

// ── Orders ────────────────────────────────────────────────────────────────────
export const orders = {
  create: (body: any) =>
    request<any>("/orders", { method: "POST", body: JSON.stringify(body) }),
  createBulk: (body: { orders: any[] }) =>
    request<any>("/orders/bulk", { method: "POST", body: JSON.stringify(body) }),
};

// ── Segments ──────────────────────────────────────────────────────────────────
export const segments = {
  list: () => request<any>("/segments"),
  create: (body: any) =>
    request<any>("/segments", { method: "POST", body: JSON.stringify(body) }),
  nl2segment: (query: string) =>
    request<any>("/segments/nl2segment", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),
  refresh: (id: string) => request<any>(`/segments/${id}/refresh`, { method: "POST" }),
  fromSemantic: (name: string, query: string, customer_ids: string[]) =>
    request<any>("/segments/from-semantic", {
      method: "POST",
      body: JSON.stringify({ name, query, customer_ids }),
    }),
};

// ── Campaigns ─────────────────────────────────────────────────────────────────
export const campaigns = {
  list: (params?: { status?: string; page?: number; limit?: number }) => {
    const qs = new URLSearchParams(
      Object.entries(params ?? {}).filter(([, v]) => v != null) as [string, string][]
    ).toString();
    return request<any>(`/campaigns${qs ? "?" + qs : ""}`);
  },
  create: (body: any) =>
    request<any>("/campaigns", { method: "POST", body: JSON.stringify(body) }),
  launch: (id: string) =>
    request<any>(`/campaigns/${id}/launch`, { method: "POST" }),
  stats: (id: string) => request<any>(`/campaigns/${id}/stats`),
  analyze: (id: string) => request<any>(`/campaigns/${id}/analyze`, { method: "POST" }),
};

// ── Analytics ─────────────────────────────────────────────────────────────────
export const analytics = {
  overview: () => request<any>("/analytics/overview"),
  campaigns: () => request<any>("/analytics/campaigns"),
  channels: () => request<any>("/analytics/channels"),
  rawData: () => request<any>("/analytics/raw-data"),
};

// ── Auth ──────────────────────────────────────────────────────────────────────
export const auth = {
  orgSignup: (body: any) =>
    request<any>("/auth/org/signup", { method: "POST", body: JSON.stringify(body) }),
  orgLogin: (org_id: string, password: string) =>
    request<any>("/auth/org/login", {
      method: "POST",
      body: JSON.stringify({ org_id, password }),
    }),
  adminLogin: (username: string, password: string) =>
    request<any>("/auth/admin/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
};

// ── AI-assisted imports ───────────────────────────────────────────────────────
export const imports = {
  analyze: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return fetch(`${BASE_URL}/api/v1/imports/analyze`, {
      method: "POST",
      body: fd,
      headers: orgHeader(),
    }).then(async (r) => {
      if (!r.ok) throw new Error((await r.json().catch(() => ({})))?.detail ?? `API error ${r.status}`);
      return r.json();
    });
  },
  run: (file: File, analysis: any) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("analysis", JSON.stringify(analysis));
    return fetch(`${BASE_URL}/api/v1/imports/run`, {
      method: "POST",
      body: fd,
      headers: orgHeader(),
    }).then(async (r) => {
      if (!r.ok) throw new Error((await r.json().catch(() => ({})))?.detail ?? `API error ${r.status}`);
      return r.json();
    });
  },
};

// ── Campaign Feedback ───────────────────────────────────────────────────────
export const feedback = {
  submit: (body: { campaign_id: string; rating: number; business_impact?: string; comments?: string }) =>
    request<any>("/feedback", { method: "POST", body: JSON.stringify(body) }),
  forCampaign: (campaignId: string) => request<any>(`/campaigns/${campaignId}/feedback`),
  preferences: () => request<any>("/org/preferences"),
};

// ── Marketing Strategist ────────────────────────────────────────────────────
export const strategist = {
  analysis: () => request<any>("/strategist/analysis"),
  weeklyReport: () => request<any>("/strategist/weekly-report"),
};

// ── PDF Reports ─────────────────────────────────────────────────────────────
export const reports = {
  /** Fetch a PDF (with org scope header) and trigger a browser download. */
  download: async (reportType: string) => {
    const res = await fetch(`${BASE_URL}/api/v1/reports/${reportType}.pdf`, {
      headers: orgHeader(),
    });
    if (!res.ok) throw new Error((await res.json().catch(() => ({})))?.detail ?? `Report failed (${res.status})`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `orbit_${reportType}_report.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};

// ── Channels (which are configured for real sending) ────────────────────────
export const channels = {
  status: () => request<{ email: boolean; sms: boolean; whatsapp: boolean; rcs: boolean }>("/channels/status"),
};

export const api = {
  customers, orders, segments, campaigns, analytics, auth, imports, feedback, strategist, reports, channels,
};
