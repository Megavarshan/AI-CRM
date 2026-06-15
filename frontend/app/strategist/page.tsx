"use client";

import { useEffect, useState } from "react";
import {
  Brain,
  Loader2,
  TrendingUp,
  Target,
  AlertTriangle,
  Lightbulb,
  IndianRupee,
  Sparkles,
  FileText,
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const POTENTIAL_COLOR: Record<string, string> = {
  high: "text-teal-400 bg-teal-950/30 border-teal-900/40",
  medium: "text-amber-400 bg-amber-950/30 border-amber-900/40",
  low: "text-slate-400 bg-slate-900/30 border-slate-800",
};

export default function StrategistPage() {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState<string | null>(null);
  const [reportLoading, setReportLoading] = useState(false);

  useEffect(() => {
    api.strategist
      .analysis()
      .then(setData)
      .catch((e) => toast.error(`Strategist failed: ${e.message}`))
      .finally(() => setLoading(false));
  }, []);

  const loadReport = async () => {
    setReportLoading(true);
    try {
      const res = await api.strategist.weeklyReport();
      setReport(res.narrative);
    } catch (e: any) {
      toast.error(e.message);
    } finally {
      setReportLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
        <span className="text-sm">The Strategist is analysing your brand...</span>
      </div>
    );
  }

  if (!data) return null;
  const { signals, forecast, strategy } = data;

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto min-h-screen">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
          <Brain className="w-7 h-7 text-purple-400" />
          Marketing Strategist
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Proactive AI strategy — opportunities, recommendations, and revenue forecasts.
        </p>
      </div>

      {/* Headline */}
      <div className="rounded-2xl border border-purple-900/40 bg-gradient-to-br from-purple-950/30 to-indigo-950/10 p-6">
        <div className="flex items-center gap-2 text-purple-300 text-xs font-semibold uppercase tracking-wider mb-2">
          <Sparkles className="w-4 h-4" /> Biggest Opportunity
        </div>
        <p className="text-xl font-bold text-white leading-snug">{strategy.headline}</p>
      </div>

      {/* Forecast */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: "Dormant High-Value", value: forecast.target_customers, icon: Target },
          { label: "Est. Reactivations", value: forecast.expected_reactivations, icon: TrendingUp },
          { label: "Projected Revenue", value: `₹${Math.round(forecast.projected_revenue).toLocaleString("en-IN")}`, icon: IndianRupee },
          { label: "Best Channel", value: forecast.recommended_channel, icon: Sparkles },
        ].map((c) => {
          const Icon = c.icon;
          return (
            <div key={c.label} className="rounded-xl border border-slate-800 bg-slate-900/20 p-5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">{c.label}</span>
                <Icon className="w-4 h-4 text-purple-400" />
              </div>
              <div className="text-xl font-extrabold text-white mt-2 capitalize">{c.value}</div>
            </div>
          );
        })}
      </div>

      {/* Opportunities */}
      {strategy.opportunities?.length > 0 && (
        <div className="space-y-3">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <Target className="w-4 h-4 text-purple-400" /> Opportunities
          </h2>
          <div className="grid md:grid-cols-2 gap-4">
            {strategy.opportunities.map((o: any, i: number) => (
              <div key={i} className="rounded-xl border border-slate-800 bg-slate-900/20 p-5">
                <div className="flex items-start justify-between gap-2">
                  <h3 className="font-bold text-white text-sm">{o.title}</h3>
                  <span className={`text-[10px] px-2 py-0.5 rounded-full border uppercase font-semibold ${POTENTIAL_COLOR[o.potential] ?? POTENTIAL_COLOR.low}`}>
                    {o.potential}
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-2 leading-relaxed">{o.why}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recommended campaign */}
      {strategy.recommended_campaign?.audience && (
        <div className="rounded-xl border border-indigo-900/40 bg-indigo-950/10 p-6 space-y-3">
          <h2 className="text-sm font-semibold text-indigo-300 uppercase tracking-wider flex items-center gap-2">
            <Lightbulb className="w-4 h-4" /> Recommended Campaign
          </h2>
          <div className="grid md:grid-cols-2 gap-3 text-sm">
            {Object.entries(strategy.recommended_campaign).map(([k, v]) => (
              <div key={k} className="flex gap-2">
                <span className="text-slate-500 capitalize min-w-[110px]">{k.replace(/_/g, " ")}:</span>
                <span className="text-slate-200">{v as string}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Risks + Recommendations */}
      <div className="grid md:grid-cols-2 gap-4">
        {strategy.risks?.length > 0 && (
          <div className="rounded-xl border border-amber-900/30 bg-amber-950/10 p-5">
            <h3 className="text-amber-400 text-sm font-semibold flex items-center gap-2 mb-3">
              <AlertTriangle className="w-4 h-4" /> Risks
            </h3>
            <ul className="space-y-2">
              {strategy.risks.map((r: string, i: number) => (
                <li key={i} className="text-xs text-slate-300 flex gap-2">
                  <span className="text-amber-500">•</span> {r}
                </li>
              ))}
            </ul>
          </div>
        )}
        {strategy.recommendations?.length > 0 && (
          <div className="rounded-xl border border-teal-900/30 bg-teal-950/10 p-5">
            <h3 className="text-teal-400 text-sm font-semibold flex items-center gap-2 mb-3">
              <Lightbulb className="w-4 h-4" /> Recommendations
            </h3>
            <ul className="space-y-2">
              {strategy.recommendations.map((r: string, i: number) => (
                <li key={i} className="text-xs text-slate-300 flex gap-2">
                  <span className="text-teal-500 font-bold">{i + 1}.</span> {r}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* Weekly report */}
      <div className="rounded-xl border border-slate-800 bg-slate-900/20 p-6">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-2">
            <FileText className="w-4 h-4 text-purple-400" /> Weekly Strategic Report
          </h2>
          {!report && (
            <button
              onClick={loadReport}
              disabled={reportLoading}
              className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:opacity-90 text-white rounded-lg text-xs font-semibold flex items-center gap-2"
            >
              {reportLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
              Generate
            </button>
          )}
        </div>
        {report && (
          <p className="text-sm text-slate-300 leading-relaxed mt-4 whitespace-pre-line">{report}</p>
        )}
      </div>
    </div>
  );
}
