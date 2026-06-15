"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  Building2,
  ShieldCheck,
  Loader2,
  Copy,
  CheckCircle,
  ArrowRight,
  Globe,
  MapPin,
  Users,
  Banknote,
  Lock,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import { setSession } from "@/lib/auth";

type Tab = "organization" | "admin";
type OrgMode = "signin" | "signup";

const inputCls =
  "w-full px-4 py-2.5 rounded-lg border border-slate-800 bg-slate-950 text-slate-200 text-sm focus:outline-none focus:border-purple-500 placeholder:text-slate-600";
const labelCls = "text-xs font-semibold text-slate-500 uppercase tracking-wider block mb-1";

export default function LoginPage() {
  const router = useRouter();
  const [tab, setTab] = useState<Tab>("organization");
  const [orgMode, setOrgMode] = useState<OrgMode>("signin");
  const [busy, setBusy] = useState(false);

  // Org sign-in
  const [orgId, setOrgId] = useState("");
  const [orgPassword, setOrgPassword] = useState("");

  // Org sign-up
  const [companyName, setCompanyName] = useState("");
  const [customerSize, setCustomerSize] = useState("1k-10k");
  const [turnover, setTurnover] = useState("");
  const [city, setCity] = useState("");
  const [country, setCountry] = useState("");
  const [website, setWebsite] = useState("");
  const [signupPassword, setSignupPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [generatedOrgId, setGeneratedOrgId] = useState<string | null>(null);

  // Admin
  const [adminUser, setAdminUser] = useState("");
  const [adminPass, setAdminPass] = useState("");

  const handleOrgSignin = async () => {
    if (!orgId.trim() || !orgPassword) return toast.error("Enter your Org ID and password.");
    setBusy(true);
    try {
      const res = await api.auth.orgLogin(orgId.trim(), orgPassword);
      setSession(res);
      toast.success(`Welcome back, ${res.company_name}!`);
      router.push("/welcome");
    } catch (e: any) {
      toast.error(e.message ?? "Login failed.");
    } finally {
      setBusy(false);
    }
  };

  const handleOrgSignup = async () => {
    if (!companyName.trim()) return toast.error("Company name is required.");
    if (signupPassword.length < 6) return toast.error("Password must be at least 6 characters.");
    if (signupPassword !== confirmPassword) return toast.error("Passwords do not match.");
    setBusy(true);
    try {
      const res = await api.auth.orgSignup({
        company_name: companyName.trim(),
        customer_size: customerSize,
        turnover: turnover || null,
        city: city || null,
        country: country || null,
        website: website || null,
        password: signupPassword,
      });
      setGeneratedOrgId(res.org_id);
      toast.success("Organization registered!");
    } catch (e: any) {
      toast.error(e.message ?? "Signup failed.");
    } finally {
      setBusy(false);
    }
  };

  const handleAdminLogin = async () => {
    setBusy(true);
    try {
      const res = await api.auth.adminLogin(adminUser, adminPass);
      setSession(res);
      toast.success("Admin authenticated.");
      router.push("/welcome");
    } catch (e: any) {
      toast.error(e.message ?? "Invalid admin credentials.");
    } finally {
      setBusy(false);
    }
  };

  const copyOrgId = () => {
    if (generatedOrgId) {
      navigator.clipboard.writeText(generatedOrgId);
      toast.success("Org ID copied!");
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
      {/* Ambient glow */}
      <div className="absolute top-[-20%] left-[10%] w-[500px] h-[500px] bg-purple-700/20 rounded-full blur-[150px] pointer-events-none" />
      <div className="absolute bottom-[-20%] right-[10%] w-[500px] h-[500px] bg-indigo-700/20 rounded-full blur-[150px] pointer-events-none" />

      <div className="w-full max-w-md relative">
        {/* Brand */}
        <div className="flex flex-col items-center mb-8">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center shadow-[0_0_40px_rgba(168,85,247,0.5)] mb-4">
            <Sparkles className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
            Orbit
          </h1>
          <p className="text-sm text-slate-500 mt-1">Your brand. Your shoppers. One AI that connects them.</p>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/40 backdrop-blur-xl p-6 shadow-2xl">
          {/* Role tabs */}
          <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-slate-950 border border-slate-800 mb-6">
            {[
              { id: "organization" as Tab, label: "Organization", icon: Building2 },
              { id: "admin" as Tab, label: "Admin", icon: ShieldCheck },
            ].map((t) => {
              const Icon = t.icon;
              return (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  className={cn(
                    "flex items-center justify-center gap-2 py-2.5 rounded-lg text-sm font-semibold transition-all",
                    tab === t.id
                      ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg"
                      : "text-slate-400 hover:text-white"
                  )}
                >
                  <Icon className="w-4 h-4" />
                  {t.label}
                </button>
              );
            })}
          </div>

          {/* ── Organization ── */}
          {tab === "organization" && (
            <>
              {/* signin / signup switch */}
              <div className="flex gap-4 mb-5 border-b border-slate-800">
                {(["signin", "signup"] as OrgMode[]).map((m) => (
                  <button
                    key={m}
                    onClick={() => {
                      setOrgMode(m);
                      setGeneratedOrgId(null);
                    }}
                    className={cn(
                      "pb-2 text-sm font-semibold border-b-2 transition-all",
                      orgMode === m
                        ? "border-purple-500 text-purple-400"
                        : "border-transparent text-slate-500 hover:text-slate-300"
                    )}
                  >
                    {m === "signin" ? "Sign In" : "Sign Up"}
                  </button>
                ))}
              </div>

              {orgMode === "signin" && (
                <div className="space-y-4">
                  <div>
                    <label className={labelCls}>Org ID</label>
                    <input
                      className={cn(inputCls, "font-mono tracking-wider uppercase")}
                      placeholder="ORB-XXXXXX"
                      value={orgId}
                      onChange={(e) => setOrgId(e.target.value.toUpperCase())}
                    />
                  </div>
                  <div>
                    <label className={labelCls}>Password</label>
                    <input
                      type="password"
                      className={inputCls}
                      placeholder="••••••••"
                      value={orgPassword}
                      onChange={(e) => setOrgPassword(e.target.value)}
                      onKeyDown={(e) => e.key === "Enter" && handleOrgSignin()}
                    />
                  </div>
                  <button
                    onClick={handleOrgSignin}
                    disabled={busy}
                    className="w-full py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:opacity-90 text-white rounded-lg text-sm font-semibold shadow-lg flex items-center justify-center gap-2 transition-opacity disabled:opacity-50"
                  >
                    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
                    Sign In
                  </button>
                </div>
              )}

              {orgMode === "signup" && !generatedOrgId && (
                <div className="space-y-3">
                  <div>
                    <label className={labelCls}>Company Name *</label>
                    <div className="relative">
                      <Building2 className="w-4 h-4 text-slate-600 absolute left-3 top-1/2 -translate-y-1/2" />
                      <input
                        className={cn(inputCls, "pl-9")}
                        placeholder="Acme Beauty Pvt Ltd"
                        value={companyName}
                        onChange={(e) => setCompanyName(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={labelCls}>Customer Size</label>
                      <div className="relative">
                        <Users className="w-4 h-4 text-slate-600 absolute left-3 top-1/2 -translate-y-1/2" />
                        <select
                          className={cn(inputCls, "pl-9 appearance-none")}
                          value={customerSize}
                          onChange={(e) => setCustomerSize(e.target.value)}
                        >
                          <option value="<1k">Under 1,000</option>
                          <option value="1k-10k">1k – 10k</option>
                          <option value="10k-100k">10k – 100k</option>
                          <option value="100k+">100k+</option>
                        </select>
                      </div>
                    </div>
                    <div>
                      <label className={labelCls}>Annual Turnover</label>
                      <div className="relative">
                        <Banknote className="w-4 h-4 text-slate-600 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                          className={cn(inputCls, "pl-9")}
                          placeholder="₹5 Cr"
                          value={turnover}
                          onChange={(e) => setTurnover(e.target.value)}
                        />
                      </div>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={labelCls}>City</label>
                      <div className="relative">
                        <MapPin className="w-4 h-4 text-slate-600 absolute left-3 top-1/2 -translate-y-1/2" />
                        <input
                          className={cn(inputCls, "pl-9")}
                          placeholder="Mumbai"
                          value={city}
                          onChange={(e) => setCity(e.target.value)}
                        />
                      </div>
                    </div>
                    <div>
                      <label className={labelCls}>Country</label>
                      <input
                        className={inputCls}
                        placeholder="India"
                        value={country}
                        onChange={(e) => setCountry(e.target.value)}
                      />
                    </div>
                  </div>
                  <div>
                    <label className={labelCls}>Website</label>
                    <div className="relative">
                      <Globe className="w-4 h-4 text-slate-600 absolute left-3 top-1/2 -translate-y-1/2" />
                      <input
                        className={cn(inputCls, "pl-9")}
                        placeholder="https://acmebeauty.in"
                        value={website}
                        onChange={(e) => setWebsite(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className={labelCls}>Set Password *</label>
                      <input
                        type="password"
                        className={inputCls}
                        placeholder="Min 6 characters"
                        value={signupPassword}
                        onChange={(e) => setSignupPassword(e.target.value)}
                      />
                    </div>
                    <div>
                      <label className={labelCls}>Confirm *</label>
                      <input
                        type="password"
                        className={inputCls}
                        placeholder="Repeat password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                      />
                    </div>
                  </div>
                  <button
                    onClick={handleOrgSignup}
                    disabled={busy}
                    className="w-full py-2.5 mt-1 bg-gradient-to-r from-purple-600 to-indigo-600 hover:opacity-90 text-white rounded-lg text-sm font-semibold shadow-lg flex items-center justify-center gap-2 transition-opacity disabled:opacity-50"
                  >
                    {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                    Create Organization
                  </button>
                </div>
              )}

              {/* Post-signup: show generated org id */}
              {orgMode === "signup" && generatedOrgId && (
                <div className="space-y-4 text-center py-4">
                  <CheckCircle className="w-12 h-12 text-teal-400 mx-auto" />
                  <h3 className="text-white font-bold text-lg">Organization Created!</h3>
                  <p className="text-slate-400 text-sm">
                    This is your <span className="text-purple-400 font-semibold">Org ID</span> — you&apos;ll use
                    it to sign in. Save it somewhere safe.
                  </p>
                  <div className="flex items-center justify-center gap-2">
                    <code className="text-2xl font-mono font-bold text-purple-300 bg-slate-950 border border-purple-900/40 px-4 py-2 rounded-lg tracking-widest">
                      {generatedOrgId}
                    </code>
                    <button
                      onClick={copyOrgId}
                      className="p-2.5 rounded-lg border border-slate-700 hover:border-purple-500 text-slate-400 hover:text-purple-400 transition-colors"
                    >
                      <Copy className="w-4 h-4" />
                    </button>
                  </div>
                  <button
                    onClick={() => {
                      setOrgMode("signin");
                      setOrgId(generatedOrgId);
                      setGeneratedOrgId(null);
                    }}
                    className="w-full py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:opacity-90 text-white rounded-lg text-sm font-semibold shadow-lg flex items-center justify-center gap-2"
                  >
                    Continue to Sign In <ArrowRight className="w-4 h-4" />
                  </button>
                </div>
              )}
            </>
          )}

          {/* ── Admin ── */}
          {tab === "admin" && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 p-3 rounded-lg bg-amber-950/20 border border-amber-900/30 text-amber-400 text-xs">
                <Lock className="w-4 h-4 shrink-0" />
                Platform administrator access. Organization data tools and global settings.
              </div>
              <div>
                <label className={labelCls}>Username</label>
                <input
                  className={inputCls}
                  placeholder="admin"
                  value={adminUser}
                  onChange={(e) => setAdminUser(e.target.value)}
                />
              </div>
              <div>
                <label className={labelCls}>Password</label>
                <input
                  type="password"
                  className={inputCls}
                  placeholder="••••••"
                  value={adminPass}
                  onChange={(e) => setAdminPass(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAdminLogin()}
                />
              </div>
              <button
                onClick={handleAdminLogin}
                disabled={busy}
                className="w-full py-2.5 bg-gradient-to-r from-amber-600 to-orange-600 hover:opacity-90 text-white rounded-lg text-sm font-semibold shadow-lg flex items-center justify-center gap-2 transition-opacity disabled:opacity-50"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />}
                Admin Sign In
              </button>
            </div>
          )}
        </div>

        <p className="text-center text-xs text-slate-600 mt-6">
          Orbit — AI-Native Mini CRM · Built for D2C brands
        </p>
      </div>
    </div>
  );
}
