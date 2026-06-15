"use client";

import { useState } from "react";
import { FileText, Download, Loader2, Users, Send, Activity, Briefcase } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const REPORTS = [
  {
    type: "customer",
    title: "Customer Analytics Report",
    desc: "Growth trends, churn distribution, geographic breakdown, and segmentation analysis.",
    icon: Users,
    accent: "from-purple-600/20 to-purple-600/5 border-purple-800/30",
    color: "text-purple-400",
  },
  {
    type: "campaign",
    title: "Campaign Performance Report",
    desc: "Campaign summary, delivery metrics, open & click-through rates, conversion funnel.",
    icon: Send,
    accent: "from-indigo-600/20 to-indigo-600/5 border-indigo-800/30",
    color: "text-indigo-400",
  },
  {
    type: "engagement",
    title: "Engagement Intelligence Report",
    desc: "Engagement trends, best-performing channels, and behavioural insights.",
    icon: Activity,
    accent: "from-teal-600/20 to-teal-600/5 border-teal-800/30",
    color: "text-teal-400",
  },
  {
    type: "executive",
    title: "Executive Business Report",
    desc: "Everything combined: customer, campaign & engagement analytics, revenue impact, and strategic recommendations.",
    icon: Briefcase,
    accent: "from-fuchsia-600/20 to-fuchsia-600/5 border-fuchsia-800/30",
    color: "text-fuchsia-400",
  },
];

export default function ReportsPage() {
  const [busy, setBusy] = useState<string | null>(null);

  const download = async (type: string) => {
    setBusy(type);
    try {
      await api.reports.download(type);
      toast.success("Report downloaded.");
    } catch (e: any) {
      toast.error(e.message ?? "Download failed.");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto min-h-screen">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
          <FileText className="w-7 h-7 text-purple-400" />
          Business Reports
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Download executive PDF reports with charts, KPIs, AI analysis, and strategic recommendations.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-5">
        {REPORTS.map((r) => {
          const Icon = r.icon;
          return (
            <div key={r.type} className={`rounded-2xl border bg-gradient-to-b p-6 ${r.accent} flex flex-col`}>
              <div className="w-11 h-11 rounded-xl bg-slate-950/80 border border-slate-800 flex items-center justify-center mb-4">
                <Icon className={`w-5 h-5 ${r.color}`} />
              </div>
              <h3 className="font-bold text-white mb-2">{r.title}</h3>
              <p className="text-sm text-slate-400 leading-relaxed flex-1">{r.desc}</p>
              <button
                onClick={() => download(r.type)}
                disabled={busy !== null}
                className="mt-5 w-full py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:opacity-90 text-white rounded-lg text-sm font-semibold shadow-lg flex items-center justify-center gap-2 transition-opacity disabled:opacity-50"
              >
                {busy === r.type ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Generating PDF...
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4" /> Download PDF
                  </>
                )}
              </button>
            </div>
          );
        })}
      </div>

      <p className="text-xs text-slate-600 text-center pt-2">
        Reports are generated live from your current data and include an AI-written business analysis section.
      </p>
    </div>
  );
}
