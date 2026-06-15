"use client";

import { useState } from "react";
import {
  ScanSearch,
  Loader2,
  Sparkles,
  Users2,
  Save,
  MapPin,
  Star,
} from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

const CHURN_COLOR: Record<string, string> = {
  low: "text-teal-400 bg-teal-950/30 border-teal-900/40",
  medium: "text-amber-400 bg-amber-950/30 border-amber-900/40",
  high: "text-orange-400 bg-orange-950/30 border-orange-900/40",
  critical: "text-red-400 bg-red-950/30 border-red-900/40",
};

const EXAMPLES = [
  "price-sensitive skincare lovers who lapsed",
  "loyal high-value fragrance buyers in metro cities",
  "one-time makeup buyers worth winning back",
  "eco-conscious customers who prefer WhatsApp",
];

function simColor(s: number) {
  if (s >= 0.65) return "text-teal-400";
  if (s >= 0.5) return "text-purple-400";
  return "text-slate-400";
}

export default function SmartSearchPage() {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [results, setResults] = useState<any[] | null>(null);
  const [lastQuery, setLastQuery] = useState("");
  const [saving, setSaving] = useState(false);

  const runSearch = async (q?: string) => {
    const term = (q ?? query).trim();
    if (term.length < 2) return toast.error("Enter a description to search.");
    setQuery(term);
    setLoading(true);
    setResults(null);
    try {
      const res = await api.customers.semanticSearch(term, 12);
      setResults(res.results);
      setLastQuery(term);
      if (res.results.length === 0) toast.message("No semantic matches found.");
    } catch (e: any) {
      toast.error(e.message ?? "Search failed.");
    } finally {
      setLoading(false);
    }
  };

  const saveAsSegment = async () => {
    if (!results || results.length === 0) return;
    setSaving(true);
    try {
      await api.segments.fromSemantic(
        `AI: ${lastQuery}`.slice(0, 60),
        lastQuery,
        results.map((r) => r.id)
      );
      toast.success("Saved as a segment — you can launch a campaign on it.");
    } catch (e: any) {
      toast.error(e.message ?? "Could not save segment.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-5xl mx-auto min-h-screen">
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
          <ScanSearch className="w-7 h-7 text-purple-400" />
          Smart Search
          <span className="text-[10px] bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-semibold px-2 py-0.5 rounded-full uppercase tracking-wider">
            RAG
          </span>
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Find customers by <span className="text-slate-200">meaning</span>, not filters. Vector search
          over AI-embedded customer profiles — describe who you want in plain English.
        </p>
      </div>

      {/* Search box */}
      <div className="rounded-2xl border border-purple-900/40 bg-gradient-to-br from-purple-950/20 to-indigo-950/10 p-5 space-y-3">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Sparkles className="w-4 h-4 text-purple-400 absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runSearch()}
              placeholder="Describe the customers you're looking for..."
              className="w-full pl-9 pr-4 py-3 rounded-xl border border-slate-800 bg-slate-950 text-slate-200 text-sm focus:outline-none focus:border-purple-500 placeholder:text-slate-600"
            />
          </div>
          <button
            onClick={() => runSearch()}
            disabled={loading}
            className="px-6 bg-gradient-to-r from-purple-600 to-indigo-600 hover:opacity-90 text-white rounded-xl text-sm font-semibold flex items-center gap-2 disabled:opacity-50"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <ScanSearch className="w-4 h-4" />}
            Search
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => runSearch(ex)}
              className="text-xs px-3 py-1.5 rounded-full border border-slate-800 text-slate-400 hover:text-white hover:border-purple-700 transition-colors"
            >
              {ex}
            </button>
          ))}
        </div>
      </div>

      {/* Results */}
      {loading && (
        <div className="flex flex-col items-center justify-center gap-3 text-slate-400 py-12">
          <Loader2 className="w-7 h-7 animate-spin text-purple-400" />
          <span className="text-sm">Embedding your query &amp; searching the vector store...</span>
        </div>
      )}

      {results && !loading && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <Users2 className="w-4 h-4 text-purple-400" />
              {results.length} semantic matches for &ldquo;{lastQuery}&rdquo;
            </h2>
            {results.length > 0 && (
              <button
                onClick={saveAsSegment}
                disabled={saving}
                className="text-xs px-3 py-2 rounded-lg border border-purple-800 text-purple-300 hover:bg-purple-950/40 flex items-center gap-1.5 disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                Save as segment
              </button>
            )}
          </div>

          <div className="grid md:grid-cols-2 gap-3">
            {results.map((r) => (
              <div key={r.id} className="rounded-xl border border-slate-800 bg-slate-900/20 p-4 space-y-2">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="font-bold text-white text-sm">
                      {r.first_name} {r.last_name}
                    </h3>
                    <div className="flex items-center gap-2 text-xs text-slate-500 mt-0.5">
                      <MapPin className="w-3 h-3" /> {r.city ?? "—"} · {r.channel_pref}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={cn("text-lg font-bold flex items-center gap-1", simColor(r.similarity))}>
                      <Star className="w-3.5 h-3.5 fill-current" />
                      {(r.similarity * 100).toFixed(0)}%
                    </div>
                    <span className="text-[10px] text-slate-600 uppercase tracking-wider">match</span>
                  </div>
                </div>
                {r.score?.churn_risk && (
                  <div className="flex items-center gap-2 text-xs">
                    <span className={cn("px-2 py-0.5 rounded-full border capitalize", CHURN_COLOR[r.score.churn_risk])}>
                      {r.score.churn_risk} churn
                    </span>
                    <span className="text-slate-500">
                      ₹{Math.round(r.score.monetary ?? 0).toLocaleString("en-IN")} · {r.score.frequency ?? 0} orders
                    </span>
                  </div>
                )}
                <p className="text-xs text-slate-400 leading-relaxed border-l-2 border-purple-900/40 pl-2 mt-1">
                  {r.why}
                </p>
              </div>
            ))}
          </div>
        </div>
      )}

      {!results && !loading && (
        <div className="text-center text-slate-600 text-sm py-12">
          Try a description above — Smart Search understands intent, value, loyalty, and category
          affinity, even when those words aren&apos;t in your data.
        </div>
      )}
    </div>
  );
}
