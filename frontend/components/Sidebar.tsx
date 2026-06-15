"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  LayoutDashboard,
  Users,
  Layers,
  Send,
  MessageSquareCode,
  BarChart3,
  Settings,
  Sparkles,
  Database,
  Brain,
  FileText,
  ScanSearch,
  LogOut,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { getSession, clearSession, type Session } from "@/lib/auth";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/smart-search", label: "Smart Search", icon: ScanSearch, highlight: true },
  { href: "/segments", label: "Segments", icon: Layers },
  { href: "/campaigns", label: "Campaigns", icon: Send },
  { href: "/copilot", label: "AI Copilot", icon: MessageSquareCode, highlight: true },
  { href: "/strategist", label: "Strategist", icon: Brain, highlight: true },
  { href: "/data", label: "Data Explorer", icon: Database },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    setSession(getSession());
  }, [pathname]);

  return (
    <aside className="w-64 border-r border-border bg-card flex flex-col justify-between h-screen sticky top-0">
      <div className="flex flex-col">
        {/* Logo/Header */}
        <div className="h-16 flex items-center px-6 gap-2 border-b border-border bg-background/50">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center shadow-[0_0_15px_rgba(168,85,247,0.4)]">
            <Sparkles className="w-4 h-4 text-white animate-pulse" />
          </div>
          <div>
            <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
              Orbit
            </span>
            <span className="text-xs block text-purple-400 font-medium -mt-1 tracking-wider">
              AI ENGINE
            </span>
          </div>
        </div>

        {/* Nav Links */}
        <nav className="p-4 space-y-1">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            const isActive = pathname.startsWith(item.href);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group relative",
                  isActive
                    ? "bg-purple-950/40 text-purple-300 border border-purple-900/30"
                    : "text-slate-400 hover:text-white hover:bg-slate-900/50"
                )}
              >
                <Icon
                  className={cn(
                    "w-4 h-4 transition-transform duration-200 group-hover:scale-110",
                    isActive ? "text-purple-400" : "text-slate-400 group-hover:text-white",
                    item.highlight && "text-purple-400"
                  )}
                />
                <span className="flex-1">{item.label}</span>
                {item.highlight && (
                  <span className="text-[10px] bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider animate-bounce">
                    AI
                  </span>
                )}
                {/* Active Indicator Bar */}
                {isActive && (
                  <div className="absolute left-0 top-1/4 w-1 h-1/2 bg-purple-500 rounded-r-md shadow-[0_0_10px_rgba(168,85,247,0.8)]" />
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer Profile */}
      <div className="p-4 border-t border-border bg-background/30 flex items-center gap-3">
        <div className="w-9 h-9 rounded-full bg-slate-800 flex items-center justify-center font-bold text-sm text-slate-300 border border-slate-700 shrink-0">
          {(session?.company_name ?? "O").charAt(0).toUpperCase()}
        </div>
        <div className="overflow-hidden flex-1">
          <span className="block text-sm font-semibold text-slate-200 truncate">
            {session?.company_name ?? "Orbit User"}
          </span>
          <span className="block text-xs text-slate-500 truncate font-mono">
            {session?.role === "admin" ? "Platform Admin" : session?.org_id ?? ""}
          </span>
        </div>
        <button
          title="Log out"
          onClick={() => {
            clearSession();
            router.replace("/login");
          }}
          className="p-2 rounded-lg text-slate-500 hover:text-white hover:bg-slate-800 transition-colors shrink-0"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </aside>
  );
}
