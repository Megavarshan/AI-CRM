"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  Sparkles,
  Layers,
  RefreshCw,
  Plus,
  Play,
  CheckCircle,
  HelpCircle,
  Loader2,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export default function SegmentsPage() {
  const [segments, setSegments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // NL to Segment fields
  const [nlQuery, setNlQuery] = useState("");
  const [translating, setTranslating] = useState(false);
  const [segmentName, setSegmentName] = useState("");
  const [translatedSpec, setTranslatedSpec] = useState<any | null>(null);
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const [previewCustomers, setPreviewCustomers] = useState<any[]>([]);
  
  // Refresh loading states
  const [refreshingId, setRefreshingId] = useState<string | null>(null);

  useEffect(() => {
    async function loadSegments() {
      try {
        const data = await api.segments.list();
        setSegments(data);
      } catch (err) {
        console.error("Error fetching segments", err);
        // Mock fallback segments
        setSegments([
          {
            id: "s1",
            name: "High Value Churn Risk",
            description: "AI generated from query: spent over ₹5000 and churn risk is critical",
            customer_count: 84,
            filter_spec: {
              and: [
                { field: "monetary", operator: "gte", value: 5000 },
                { field: "churn_risk", operator: "eq", value: "critical" },
              ],
            },
            created_at: "2026-06-10T12:00:00Z",
          },
          {
            id: "s2",
            name: "Mumbai Haircare Buyers",
            description: "AI generated from query: city is Mumbai and bought haircare category",
            customer_count: 128,
            filter_spec: {
              and: [
                { field: "city", operator: "eq", value: "Mumbai" },
                { field: "top_category", operator: "eq", value: "haircare" },
              ],
            },
            created_at: "2026-06-08T09:30:00Z",
          },
        ]);
      } finally {
        setLoading(false);
      }
    }
    loadSegments();
  }, []);

  const handleTranslateAndPreview = async () => {
    if (!nlQuery.trim()) {
      toast.error("Please enter a natural language prompt first.");
      return;
    }
    setTranslating(true);
    setTranslatedSpec(null);
    setPreviewCount(null);
    setPreviewCustomers([]);

    try {
      const result = await api.segments.nl2segment(nlQuery);
      setTranslatedSpec(result.filter_spec);
      setPreviewCount(result.customer_count);
      setPreviewCustomers(result.preview || []);
      toast.success("AI parsed query successfully!");
    } catch (err) {
      console.error("NL translation failed", err);
      // Mock result fallback
      setTranslatedSpec({
        and: [
          { field: "monetary", operator: "gte", value: 5000 },
          { field: "recency_days", operator: "gte", value: 60 },
        ],
      });
      setPreviewCount(147);
      setPreviewCustomers([
        { first_name: "Priya", last_name: "Sharma", city: "Mumbai" },
        { first_name: "Amit", last_name: "Patel", city: "Ahmedabad" },
        { first_name: "Rahul", last_name: "Verma", city: "Delhi" },
      ]);
      toast.info("Using mockup translation. Start your AI engine keys to test Groq parsing.");
    } finally {
      setTranslating(false);
    }
  };

  const handleSaveSegment = async () => {
    if (!segmentName.trim() || !translatedSpec) {
      toast.error("Please provide a name for the segment.");
      return;
    }

    try {
      const payload = {
        name: segmentName,
        description: `AI generated from query: ${nlQuery}`,
        filter_spec: translatedSpec,
        nl_query: nlQuery,
        customer_count: previewCount ?? 0,
      };
      const newSeg = await api.segments.create(payload);
      setSegments([newSeg, ...segments]);
      toast.success("Segment saved successfully!");
      
      // Reset NL query builder
      setSegmentName("");
      setNlQuery("");
      setTranslatedSpec(null);
      setPreviewCount(null);
      setPreviewCustomers([]);
    } catch (err) {
      console.error("Error saving segment", err);
      toast.error("Failed to save segment. Database offline.");
    }
  };

  const handleRefreshCount = async (id: string) => {
    setRefreshingId(id);
    try {
      const updated = await api.segments.refresh(id);
      setSegments(segments.map((s) => (s.id === id ? { ...s, customer_count: updated.customer_count } : s)));
      toast.success("Cohort count refreshed!");
    } catch (err) {
      console.error("Error refreshing segment count", err);
      toast.error("Failed to refresh segment.");
    } finally {
      setRefreshingId(null);
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
          Segment Builder
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Target cohorts in plain English. No complex SQL queries needed.
        </p>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Columns: NL Query Interface */}
        <div className="lg:col-span-2 space-y-6">
          <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/10 backdrop-blur-sm space-y-4">
            <h3 className="font-bold text-white text-lg flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-purple-400 animate-pulse" />
              NL2Segment Builder
            </h3>
            <p className="text-slate-400 text-sm">
              Describe your target audience. You can filter by monetary value, recency, category, location, or churn risk.
            </p>

            {/* Query Input Box */}
            <div className="space-y-2">
              <textarea
                placeholder="Example: customers from Mumbai who spent more than ₹5000 and have low or medium churn risk..."
                rows={3}
                className="w-full p-4 rounded-lg border border-slate-800 bg-slate-950 text-slate-200 text-sm focus:outline-none focus:border-purple-500 transition-colors placeholder:text-slate-600"
                value={nlQuery}
                onChange={(e) => setNlQuery(e.target.value)}
              />
              <div className="flex justify-between items-center">
                <span className="text-xs text-slate-500 flex items-center gap-1">
                  <HelpCircle className="w-3.5 h-3.5" />
                  Supports: monetary, city, recency_days, churn_risk...
                </span>
                <button
                  onClick={handleTranslateAndPreview}
                  disabled={translating}
                  className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-semibold rounded-lg text-sm shadow-lg hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
                >
                  {translating ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Parsing Cohorts...
                    </>
                  ) : (
                    <>
                      <Play className="w-3.5 h-3.5 fill-current" />
                      Translate & Preview
                    </>
                  )}
                </button>
              </div>
            </div>

            {/* Translation Output Preview */}
            {translatedSpec && (
              <div className="p-5 rounded-lg border border-purple-900/30 bg-purple-950/10 space-y-4 animate-fadeIn">
                <div className="flex justify-between items-center">
                  <h4 className="font-bold text-sm text-purple-300 flex items-center gap-1.5">
                    <CheckCircle className="w-4 h-4 text-teal-400" />
                    Audience Matches: {previewCount} customers
                  </h4>
                </div>

                {/* Filter Specs */}
                <div className="p-3 bg-slate-950/80 rounded border border-slate-800 text-xs font-mono text-purple-400 overflow-x-auto">
                  {JSON.stringify(translatedSpec, null, 2)}
                </div>

                {/* Preview Cohort list */}
                {previewCustomers.length > 0 && (
                  <div className="space-y-2">
                    <span className="text-xs text-slate-500 font-semibold block">Sample Recipients:</span>
                    <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                      {previewCustomers.map((cust, idx) => (
                        <div key={idx} className="p-2 rounded bg-slate-900/50 border border-slate-800 text-xs text-slate-300">
                          {cust.first_name} {cust.last_name || ""} ({cust.city || "India"})
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Save Segment Prompt */}
                <div className="pt-2 border-t border-slate-800 flex flex-col sm:flex-row gap-3">
                  <input
                    type="text"
                    placeholder="Enter segment name (e.g. VIP Mumbai Lapsed)"
                    className="flex-1 px-3 py-2 rounded border border-slate-800 bg-slate-950 text-slate-200 text-xs focus:outline-none focus:border-purple-500"
                    value={segmentName}
                    onChange={(e) => setSegmentName(e.target.value)}
                  />
                  <button
                    onClick={handleSaveSegment}
                    className="px-4 py-2 bg-teal-600 hover:bg-teal-500 text-white font-semibold rounded text-xs transition-colors flex items-center gap-1.5"
                  >
                    <Plus className="w-3.5 h-3.5" />
                    Save Audience Segment
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Saved Segment Lists */}
        <div className="space-y-6">
          <div className="p-6 rounded-xl border border-slate-800 bg-slate-900/20">
            <h3 className="font-bold text-white text-lg mb-4 flex items-center gap-2">
              <Layers className="w-5 h-5 text-blue-400" />
              Saved Segments
            </h3>

            <div className="space-y-4">
              {loading ? (
                <div className="text-center py-6 text-slate-500 text-xs flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-blue-400" />
                  Loading segments...
                </div>
              ) : segments.length === 0 ? (
                <p className="text-slate-500 text-xs text-center py-6">No saved segments found.</p>
              ) : (
                segments.map((seg) => (
                  <div
                    key={seg.id}
                    className="p-4 rounded-lg bg-slate-900/40 border border-slate-800/80 hover:border-slate-700 transition-all space-y-3 relative group"
                  >
                    <div>
                      <span className="font-semibold text-slate-200 text-sm block">
                        {seg.name}
                      </span>
                      <span className="text-xs text-slate-500 block mt-1 line-clamp-2">
                        {seg.description}
                      </span>
                    </div>

                    <div className="flex justify-between items-center pt-2 border-t border-slate-800/50">
                      <span className="text-xs text-slate-400 font-semibold">
                        {seg.customer_count} customers
                      </span>
                      <button
                        onClick={() => handleRefreshCount(seg.id)}
                        disabled={refreshingId === seg.id}
                        className="p-1 rounded bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white disabled:opacity-50 transition-colors"
                      >
                        <RefreshCw
                          className={cn(
                            "w-3.5 h-3.5",
                            refreshingId === seg.id && "animate-spin"
                          )}
                        />
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
