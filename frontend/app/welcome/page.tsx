"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Sparkles,
  ArrowRight,
  BrainCircuit,
  MessagesSquare,
  Target,
  Activity,
  Bot,
  FileSearch,
  LogOut,
} from "lucide-react";
import { getSession, clearSession, type Session } from "@/lib/auth";

const FEATURES = [
  {
    icon: Target,
    title: "Segments in Plain English",
    desc: "Type “high spenders who went quiet for 60 days” — our AI turns it into a live audience instantly. No SQL, no filters to learn.",
    accent: "from-purple-600/20 to-purple-600/5 border-purple-800/30",
    iconColor: "text-purple-400",
  },
  {
    icon: MessagesSquare,
    title: "1:1 Personalized Messaging",
    desc: "Every customer gets a unique message referencing their name, last product, and habits — written by AI at send time, across WhatsApp, SMS, Email & RCS.",
    accent: "from-indigo-600/20 to-indigo-600/5 border-indigo-800/30",
    iconColor: "text-indigo-400",
  },
  {
    icon: BrainCircuit,
    title: "Churn Prediction Built-In",
    desc: "Every customer is scored on Recency, Frequency & Monetary value automatically. Know who’s about to leave before they do.",
    accent: "from-fuchsia-600/20 to-fuchsia-600/5 border-fuchsia-800/30",
    iconColor: "text-fuchsia-400",
  },
  {
    icon: Bot,
    title: "An AI Copilot That Acts",
    desc: "Describe your goal in chat — the Copilot finds the audience, writes the copy, builds the campaign, and launches it with your confirmation.",
    accent: "from-violet-600/20 to-violet-600/5 border-violet-800/30",
    iconColor: "text-violet-400",
  },
  {
    icon: Activity,
    title: "Live Delivery Tracking",
    desc: "Watch every message move from sent → delivered → opened → clicked in real time, with an AI-written post-mortem when the campaign completes.",
    accent: "from-teal-600/20 to-teal-600/5 border-teal-800/30",
    iconColor: "text-teal-400",
  },
  {
    icon: FileSearch,
    title: "Upload Any Data Format",
    desc: "Our import agent reads your CSV — whatever the column names — maps it to our schema with AI, and visualizes your raw data instantly.",
    accent: "from-sky-600/20 to-sky-600/5 border-sky-800/30",
    iconColor: "text-sky-400",
  },
];

export default function WelcomePage() {
  const router = useRouter();
  const [session, setSessionState] = useState<Session | null>(null);

  useEffect(() => {
    const s = getSession();
    if (!s) {
      router.replace("/login");
      return;
    }
    setSessionState(s);
  }, [router]);

  if (!session) return null;

  return (
    <div className="min-h-screen relative overflow-hidden">
      {/* Ambient glows */}
      <div className="absolute top-[-15%] left-[20%] w-[600px] h-[600px] bg-purple-700/15 rounded-full blur-[160px] pointer-events-none" />
      <div className="absolute bottom-[-25%] right-[5%] w-[500px] h-[500px] bg-indigo-700/15 rounded-full blur-[160px] pointer-events-none" />

      {/* Top bar */}
      <div className="relative flex items-center justify-between px-8 py-5 max-w-6xl mx-auto">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center shadow-[0_0_15px_rgba(168,85,247,0.4)]">
            <Sparkles className="w-4 h-4 text-white" />
          </div>
          <span className="font-bold text-lg tracking-tight text-white">Orbit</span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-sm text-slate-400">
            Signed in as <span className="text-purple-300 font-semibold">{session.company_name}</span>
            {session.org_id && (
              <code className="ml-2 text-xs bg-slate-900 border border-slate-800 px-2 py-0.5 rounded font-mono text-slate-400">
                {session.org_id}
              </code>
            )}
          </span>
          <button
            onClick={() => {
              clearSession();
              router.replace("/login");
            }}
            className="flex items-center gap-1.5 text-xs text-slate-500 hover:text-white transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" /> Log out
          </button>
        </div>
      </div>

      {/* Hero */}
      <div className="relative max-w-6xl mx-auto px-8 pt-14 pb-10 text-center">
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-purple-800/40 bg-purple-950/30 text-purple-300 text-xs font-semibold tracking-wide uppercase mb-6">
          <Sparkles className="w-3.5 h-3.5" /> AI-Native CRM for D2C Brands
        </div>
        <h1 className="text-5xl md:text-6xl font-extrabold tracking-tight leading-tight">
          <span className="bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
            Welcome to{" "}
          </span>
          <span className="bg-gradient-to-r from-purple-400 via-fuchsia-400 to-indigo-400 bg-clip-text text-transparent">
            Orbit
          </span>
        </h1>
        <p className="text-lg text-slate-400 max-w-2xl mx-auto mt-6 leading-relaxed">
          Your brand. Your shoppers. One AI that connects them. Orbit decides{" "}
          <span className="text-slate-200 font-medium">who to talk to</span>,{" "}
          <span className="text-slate-200 font-medium">what to say</span>, and{" "}
          <span className="text-slate-200 font-medium">how well it worked</span> — so your team can
          focus on the brand, not the busywork.
        </p>

        <button
          onClick={() => router.push("/dashboard")}
          className="group mt-10 inline-flex items-center gap-3 px-8 py-4 rounded-2xl bg-gradient-to-r from-purple-600 to-indigo-600 hover:shadow-[0_0_40px_rgba(168,85,247,0.45)] text-white text-base font-bold shadow-xl transition-all duration-300"
        >
          Enter Your Dashboard
          <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
        </button>
      </div>

      {/* Feature grid */}
      <div className="relative max-w-6xl mx-auto px-8 pb-20">
        <h2 className="text-center text-sm font-semibold text-slate-500 uppercase tracking-[0.2em] mb-8">
          What makes Orbit special
        </h2>
        <div className="grid md:grid-cols-3 gap-5">
          {FEATURES.map((f) => {
            const Icon = f.icon;
            return (
              <div
                key={f.title}
                className={`rounded-2xl border bg-gradient-to-b p-6 ${f.accent} hover:translate-y-[-3px] transition-transform duration-300`}
              >
                <div className="w-10 h-10 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-center mb-4">
                  <Icon className={`w-5 h-5 ${f.iconColor}`} />
                </div>
                <h3 className="font-bold text-white mb-2">{f.title}</h3>
                <p className="text-sm text-slate-400 leading-relaxed">{f.desc}</p>
              </div>
            );
          })}
        </div>

        {/* Bottom stats strip */}
        <div className="mt-12 grid grid-cols-2 md:grid-cols-4 gap-4 rounded-2xl border border-slate-800 bg-slate-900/30 p-6">
          {[
            { v: "4", l: "Messaging Channels" },
            { v: "< 15 min", l: "Data to First Campaign" },
            { v: "100%", l: "Messages Personalized" },
            { v: "0", l: "SQL Queries Needed" },
          ].map((s) => (
            <div key={s.l} className="text-center">
              <div className="text-2xl font-extrabold bg-gradient-to-r from-purple-400 to-indigo-400 bg-clip-text text-transparent">
                {s.v}
              </div>
              <div className="text-xs text-slate-500 mt-1">{s.l}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
