"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Activity,
  ArrowLeft,
  Loader2,
  Sparkles,
  Star,
  CheckCircle,
  ThumbsUp,
} from "lucide-react";
import { api } from "@/lib/api";
import { subscribeToCampaign } from "@/lib/supabase";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

/**
 * Live campaign detail / tracker page.
 *
 * Loads stats once from the CRM API, then subscribes to Supabase Realtime
 * for live updates to the delivery funnel. Linked from the dashboard and
 * campaigns list.
 */
export default function CampaignDetailPage() {
  const params = useParams();
  const campaignId = String(params?.id ?? "");

  const [stats, setStats] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);

  const runAnalysis = async () => {
    setAnalyzing(true);
    try {
      const res = await api.campaigns.analyze(campaignId);
      setStats((prev: any) => ({ ...(prev ?? {}), ai_postmortem: res.ai_postmortem }));
      toast.success("AI analysis generated from live engagement.");
    } catch (e: any) {
      toast.error(e.message ?? "Could not generate analysis.");
    } finally {
      setAnalyzing(false);
    }
  };

  const roundRate = (num: number, den: number) =>
    den > 0 ? Math.round((num / den) * 1000) / 10 : 0;

  useEffect(() => {
    if (!campaignId) return;

    async function loadStats() {
      setLoading(true);
      try {
        const data = await api.campaigns.stats(campaignId);
        setStats(data);
        setError(null);
      } catch (err) {
        console.error("Error fetching campaign stats", err);
        setError("Could not load campaign stats. Is the CRM API running?");
      } finally {
        setLoading(false);
      }
    }
    loadStats();

    const unsubscribe = subscribeToCampaign(campaignId, (payload) => {
      const c = payload.new;
      setStats((prev: any) => ({
        ...(prev ?? {}),
        status: c.status,
        total_sent: c.total_sent,
        total_delivered: c.total_delivered,
        total_opened: c.total_opened,
        total_clicked: c.total_clicked,
        total_failed: c.total_failed,
        delivery_rate: roundRate(c.total_delivered, c.total_sent),
        open_rate: roundRate(c.total_opened, c.total_delivered),
        click_rate: roundRate(c.total_clicked, c.total_opened),
        ai_postmortem: c.ai_postmortem,
      }));
    });

    return () => unsubscribe();
  }, [campaignId]);

  return (
    <div className="p-8 space-y-8 max-w-5xl mx-auto">
      <Link
        href="/campaigns"
        className="inline-flex items-center gap-2 text-sm text-slate-400 hover:text-white transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to campaigns
      </Link>

      <div className="flex items-center gap-2 text-slate-200">
        <Activity className="w-5 h-5 text-purple-400" />
        <h1 className="text-2xl font-bold">Live Campaign Tracker</h1>
      </div>

      {loading ? (
        <div className="flex flex-col items-center justify-center h-64 gap-2">
          <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
          <span className="text-slate-400 text-sm">Loading campaign metrics...</span>
        </div>
      ) : error ? (
        <div className="text-center text-slate-500 py-12">{error}</div>
      ) : stats ? (
        <>
          <div>
            <h2 className="text-xl font-bold text-white">{stats.name}</h2>
            <span className="text-xs text-slate-500">ID: {stats.campaign_id}</span>
            <span className="ml-3 text-xs px-2 py-0.5 rounded bg-slate-800 text-slate-300 capitalize">
              {stats.status}
            </span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <Metric label="Sent" value={stats.total_sent} className="text-white" />
            <Metric label="Delivered" value={stats.total_delivered} className="text-blue-400" />
            <Metric label="Opened" value={stats.total_opened} className="text-purple-400" />
            <Metric label="Failed" value={stats.total_failed} className="text-red-500" />
          </div>

          <div className="space-y-4 pt-2">
            <h3 className="font-semibold text-slate-300 text-sm">Conversion Funnel</h3>
            <Bar label="Delivery Rate" pct={stats.delivery_rate} color="bg-blue-500" />
            <Bar label="Open Rate" pct={stats.open_rate} color="bg-purple-500" />
            <Bar label="Click Rate" pct={stats.click_rate} color="bg-teal-500" />
          </div>

          {/* AI analysis — generated on demand from LIVE engagement, since real
              email opens/clicks accrue over time after delivery. */}
          {stats.status === "completed" && (
            <div className="p-5 rounded-xl border border-purple-900/30 bg-purple-950/15 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex gap-2 items-center text-purple-400 font-bold text-xs uppercase tracking-wider">
                  <Sparkles className="w-4 h-4 animate-pulse" />
                  AI Analyst Post-mortem
                </div>
                <button
                  onClick={runAnalysis}
                  disabled={analyzing}
                  className="text-xs px-3 py-1.5 rounded-lg border border-purple-800 text-purple-300 hover:bg-purple-950/40 flex items-center gap-1.5 disabled:opacity-50"
                >
                  {analyzing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />}
                  {stats.ai_postmortem ? "Refresh analysis" : "Generate analysis"}
                </button>
              </div>
              {stats.ai_postmortem ? (
                <p className="text-slate-200 text-sm leading-relaxed font-medium">{stats.ai_postmortem}</p>
              ) : (
                <p className="text-slate-500 text-sm">
                  Delivery is complete. Generate the AI analysis once engagement (opens &amp; clicks) has
                  accumulated — it reads your live numbers, so run it after recipients have had time to react.
                </p>
              )}
            </div>
          )}

          {stats.status === "completed" && (
            <FeedbackWidget campaignId={campaignId} />
          )}
        </>
      ) : (
        <div className="text-center text-slate-500 py-12">No stats available.</div>
      )}
    </div>
  );
}

function Metric({ label, value, className }: { label: string; value: number; className?: string }) {
  return (
    <div className="p-3 bg-slate-900/40 border border-slate-800 rounded-lg text-center">
      <span className="text-[10px] text-slate-500 uppercase tracking-wider block">{label}</span>
      <span className={`text-lg font-bold ${className ?? "text-white"}`}>{value ?? 0}</span>
    </div>
  );
}

const IMPACT_OPTIONS = [
  { id: "high_sales", label: "Drove strong sales" },
  { id: "some_sales", label: "Some sales" },
  { id: "no_impact", label: "No clear impact" },
  { id: "negative", label: "Negative response" },
];

function FeedbackWidget({ campaignId }: { campaignId: string }) {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [impact, setImpact] = useState<string>("");
  const [comments, setComments] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const [learned, setLearned] = useState<any | null>(null);

  // Load existing feedback to avoid duplicate prompts
  useEffect(() => {
    api.feedback.forCampaign(campaignId).then((fb) => {
      if (Array.isArray(fb) && fb.length > 0) setDone(true);
    }).catch(() => {});
  }, [campaignId]);

  const submit = async () => {
    if (rating === 0) return toast.error("Please give a star rating.");
    setSubmitting(true);
    try {
      const res = await api.feedback.submit({
        campaign_id: campaignId,
        rating,
        business_impact: impact || undefined,
        comments: comments || undefined,
      });
      setLearned(res.updated_preferences);
      setDone(true);
      toast.success("Feedback saved — the AI will adapt to it.");
    } catch (e: any) {
      toast.error(e.message ?? "Could not submit feedback.");
    } finally {
      setSubmitting(false);
    }
  };

  if (done) {
    return (
      <div className="p-5 rounded-xl border border-teal-900/30 bg-teal-950/10 space-y-2">
        <div className="flex items-center gap-2 text-teal-400 text-sm font-semibold">
          <CheckCircle className="w-4 h-4" /> Feedback recorded
        </div>
        <p className="text-xs text-slate-400">
          Thanks! Orbit&apos;s AI now learns this brand&apos;s preferences and adapts future campaigns.
        </p>
        {learned?.has_feedback && learned.best_channels?.[0] && (
          <p className="text-xs text-slate-500">
            Learned so far: best channel <span className="text-purple-300">{learned.best_channels[0].channel}</span>,
            discount sensitivity <span className="text-purple-300">{learned.discount_sensitivity}</span>,
            avg rating <span className="text-purple-300">{learned.avg_rating}/5</span>.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="p-5 rounded-xl border border-indigo-900/30 bg-indigo-950/10 space-y-4">
      <div className="flex items-center gap-2 text-indigo-300 font-bold text-xs uppercase tracking-wider">
        <ThumbsUp className="w-4 h-4" /> Rate this campaign — teach the AI
      </div>

      <div className="flex items-center gap-1">
        {[1, 2, 3, 4, 5].map((n) => (
          <button
            key={n}
            onMouseEnter={() => setHover(n)}
            onMouseLeave={() => setHover(0)}
            onClick={() => setRating(n)}
          >
            <Star
              className={cn(
                "w-7 h-7 transition-colors",
                (hover || rating) >= n ? "text-amber-400 fill-amber-400" : "text-slate-600"
              )}
            />
          </button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2">
        {IMPACT_OPTIONS.map((o) => (
          <button
            key={o.id}
            onClick={() => setImpact(o.id)}
            className={cn(
              "px-3 py-1.5 rounded-full text-xs font-medium border transition-colors",
              impact === o.id
                ? "bg-purple-600 text-white border-purple-500"
                : "border-slate-700 text-slate-400 hover:text-white"
            )}
          >
            {o.label}
          </button>
        ))}
      </div>

      <textarea
        value={comments}
        onChange={(e) => setComments(e.target.value)}
        placeholder="What worked or didn't? (e.g. 'the 20% offer drove orders', 'tone was too pushy')"
        rows={2}
        className="w-full px-3 py-2 rounded-lg border border-slate-800 bg-slate-950 text-slate-200 text-sm focus:outline-none focus:border-purple-500 placeholder:text-slate-600"
      />

      <button
        onClick={submit}
        disabled={submitting}
        className="w-full py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:opacity-90 text-white rounded-lg text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-50"
      >
        {submitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <ThumbsUp className="w-4 h-4" />}
        Submit Feedback
      </button>
    </div>
  );
}

function Bar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div>
      <div className="flex justify-between text-xs font-semibold text-slate-400 mb-1">
        <span>{label}</span>
        <span>{pct ?? 0}%</span>
      </div>
      <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
        <div className={`${color} h-full`} style={{ width: `${Math.min(pct ?? 0, 100)}%` }} />
      </div>
    </div>
  );
}
