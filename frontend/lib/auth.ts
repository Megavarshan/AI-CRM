/**
 * Client-side session management (demo-grade).
 *
 * The backend authenticates (org signup/login, admin login) and the session
 * object is kept in localStorage. App pages redirect to /login when absent.
 */

export type Session = {
  role: "organization" | "admin";
  org_id?: string;
  username?: string;
  company_name: string;
  city?: string | null;
  country?: string | null;
  website?: string | null;
  logged_in_at: string;
};

const KEY = "orbit_session";

export function getSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function setSession(s: Omit<Session, "logged_in_at">) {
  localStorage.setItem(
    KEY,
    JSON.stringify({ ...s, logged_in_at: new Date().toISOString() })
  );
}

export function clearSession() {
  localStorage.removeItem(KEY);
}
