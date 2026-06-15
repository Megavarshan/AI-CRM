"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { subscribeToCampaign } from "@/lib/supabase";
import {
  Send,
  Plus,
  X,
  Play,
  CheckCircle2,
  Sparkles,
  BarChart3,
  Clock,
  AlertTriangle,
  Loader2,
  IndianRupee,
  Activity,
  FileText,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export default function CampaignsPage() {
  const [campaigns, setCampaigns] = useState<any[]>([]);
  const [segments, setSegments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Campaign Wizard Modal
  const [wizardOpen, setWizardOpen] = useState(false);
  const [wizardStep, setWizardStep] = useState(1);
  const [newCampName, setNewCampName] = useState("");
  const [newCampChannel, setNewCampChannel] = useState("email");
  const [ctaUrl, setCtaUrl] = useState("");
  const [selectedSegmentId, setSelectedSegmentId] = useState("");
  const [messageTemplate, setMessageTemplate] = useState("");
  const [personalized, setPersonalized] = useState(true);
  const [creating, setCreating] = useState(false);
  const [channelStatus, setChannelStatus] = useState<Record<string, boolean>>({ email: false, sms: false, whatsapp: false, rcs: false });

  useEffect(() => {
    api.channels.status().then(setChannelStatus).catch(() => {});
  }, []);

  // Live Stats Panel
  const [selectedCampId, setSelectedCampId] = useState<string | null>(null);
  const [stats, setStats] = useState<any | null>(null);
  const [statsLoading, setStatsLoading] = useState(false);

  useEffect(() => {
    async function loadInitialData() {
      try {
        const campData = await api.campaigns.list();
        setCampaigns(campData);
        const segData = await api.segments.list();
        setSegments(segData);
      } catch (err) {
        console.error("Error loading initial data", err);
        // Fallbacks
        setCampaigns([
          { id: "c1", name: "Summer Churn Winback", status: "running", channel: "whatsapp", total_sent: 500, total_delivered: 485, total_opened: 350, total_clicked: 140, total_failed: 2, created_at: "2026-06-11T12:00:00Z" },
          { id: "c2", name: "High Value Lapsed Launch", status: "completed", channel: "email", total_sent: 250, total_delivered: 245, total_opened: 120, total_clicked: 40, total_failed: 1, ai_postmortem: "Campaign concluded with strong open rates of 49.0% on email. High monetary conversion observed in cosmetics categories. Recommendation: Increase discount for non-responders in next iteration.", created_at: "2026-06-08T09:30:00Z" },
          { id: "c3", name: "RCS New Arrivals Blast", status: "draft", channel: "rcs", total_sent: 0, total_delivered: 0, total_opened: 0, total_clicked: 0, total_failed: 0, created_at: "2026-06-12T15:00:00Z" }
        ]);
        setSegments([
          { id: "s1", name: "High Value Churn Risk", customer_count: 84 },
          { id: "s2", name: "Mumbai Haircare Buyers", customer_count: 128 }
        ]);
      } finally {
        setLoading(false);
      }
    }
    loadInitialData();
  }, []);

  // Realtime subscription logic
  useEffect(() => {
    if (!selectedCampId) return;
    const campId = selectedCampId;

    // Load initial stats
    async function loadStats() {
      setStatsLoading(true);
      try {
        const data = await api.campaigns.stats(campId);
        setStats(data);
      } catch (err) {
        console.error("Error fetching stats", err);
        // Mock fallback stats based on campaigns state
        const camp = campaigns.find((c) => c.id === selectedCampId);
        if (camp) {
          const sent = camp.total_sent || 100;
          const del = camp.total_delivered || 95;
          const op = camp.total_opened || 60;
          const cl = camp.total_clicked || 25;
          const fa = camp.total_failed || 0;
          setStats({
            campaign_id: selectedCampId,
            name: camp.name,
            status: camp.status,
            total_sent: sent,
            total_delivered: del,
            total_opened: op,
            total_clicked: cl,
            total_failed: fa,
            delivery_rate: roundRate(del, sent),
            open_rate: roundRate(op, del),
            click_rate: roundRate(cl, op),
            ai_postmortem: camp.ai_postmortem
          });
        }
      } finally {
        setStatsLoading(false);
      }
    }
    loadStats();

    // Subscribe to realtime updates
    const unsubscribe = subscribeToCampaign(selectedCampId, (payload) => {
      const updatedCamp = payload.new;
      setStats((prev: any) => {
        if (!prev) return null;
        const sent = updatedCamp.total_sent;
        const del = updatedCamp.total_delivered;
        const op = updatedCamp.total_opened;
        const cl = updatedCamp.total_clicked;
        const fa = updatedCamp.total_failed;
        return {
          ...prev,
          status: updatedCamp.status,
          total_sent: sent,
          total_delivered: del,
          total_opened: op,
          total_clicked: cl,
          total_failed: fa,
          delivery_rate: roundRate(del, sent),
          open_rate: roundRate(op, del),
          click_rate: roundRate(cl, op),
          ai_postmortem: updatedCamp.ai_postmortem
        };
      });

      // Update in main list
      setCampaigns((prevList) =>
        prevList.map((c) => (c.id === selectedCampId ? { ...c, ...updatedCamp } : c))
      );
    });

    return () => unsubscribe();
  }, [selectedCampId, campaigns]);

  const roundRate = (num: number, den: number) => {
    return den > 0 ? Math.round((num / den) * 1000) / 10 : 0;
  };

  const handleCreateCampaign = async () => {
    if (!newCampName.trim() || !selectedSegmentId || !messageTemplate.trim()) {
      toast.error("Please fill all required wizard fields.");
      return;
    }
    setCreating(true);
    try {
      const payload = {
        name: newCampName,
        segment_id: selectedSegmentId,
        channel: newCampChannel,
        message_template: messageTemplate,
        personalized: personalized,
        cta_url: ctaUrl || undefined,
      };
      const created = await api.campaigns.create(payload);
      setCampaigns([created, ...campaigns]);
      toast.success("Campaign created as Draft!");
      
      // Close wizard
      setWizardOpen(false);
      setWizardStep(1);
      setNewCampName("");
      setSelectedSegmentId("");
      setMessageTemplate("");
    } catch (err) {
      console.error("Error creating campaign", err);
      toast.error("Failed to create campaign.");
    } finally {
      setCreating(false);
    }
  };

  const handleLaunchCampaign = async (id: string) => {
    try {
      toast.loading("Initiating campaign launch...", { id: "launch" });
      const res = await api.campaigns.launch(id);
      setCampaigns(campaigns.map((c) => (c.id === id ? { ...c, status: "running" } : c)));
      toast.success("Campaign successfully launched!", { id: "launch" });
      setSelectedCampId(id);
    } catch (err) {
      console.error("Error launching campaign", err);
      toast.error("Launch failed. Verification check: segment might be empty.", { id: "launch" });
    }
  };

  return (
    <div className="p-8 space-y-8 max-w-7xl mx-auto min-h-screen relative">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
            Campaigns
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Build cohort engagement templates, track deliveries, and read postmortems.
          </p>
        </div>
        <button
          onClick={() => setWizardOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-medium rounded-lg text-sm shadow-lg hover:opacity-90 transition-opacity"
        >
          <Plus className="w-4 h-4" />
          Create Campaign
        </button>
      </div>

      {/* Campaigns list Table */}
      <div className="border border-slate-800 bg-slate-900/10 rounded-xl overflow-hidden backdrop-blur-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900/50 border-b border-slate-800 text-slate-400 text-xs uppercase tracking-wider font-semibold">
              <tr>
                <th className="px-6 py-4">Campaign Name</th>
                <th className="px-6 py-4">Channel</th>
                <th className="px-6 py-4">Created Date</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {loading ? (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-slate-500">
                    <div className="flex items-center justify-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                      Loading campaigns...
                    </div>
                  </td>
                </tr>
              ) : campaigns.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-12 text-slate-500">
                    No campaigns created yet. Click "Create Campaign" to get started.
                  </td>
                </tr>
              ) : (
                campaigns.map((camp) => (
                  <tr
                    key={camp.id}
                    className="hover:bg-slate-900/30 cursor-pointer transition-colors"
                    onClick={() => setSelectedCampId(camp.id)}
                  >
                    <td className="px-6 py-4 font-semibold text-slate-200">
                      {camp.name}
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-xs bg-slate-800 text-slate-400 px-2.5 py-1 rounded-full uppercase tracking-wider font-medium">
                        {camp.channel}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-slate-400 text-xs">
                      {new Date(camp.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-6 py-4">
                      {camp.status === "draft" && (
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 text-xs font-semibold border border-slate-700">
                          Draft
                        </span>
                      )}
                      {camp.status === "running" && (
                        <span className="px-2 py-0.5 rounded bg-blue-950 text-blue-400 text-xs font-semibold border border-blue-900/50 flex items-center gap-1.5 w-fit">
                          <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-ping" />
                          Running
                        </span>
                      )}
                      {camp.status === "completed" && (
                        <span className="px-2 py-0.5 rounded bg-teal-950 text-teal-400 text-xs font-semibold border border-teal-900/50">
                          Completed
                        </span>
                      )}
                      {camp.status === "failed" && (
                        <span className="px-2 py-0.5 rounded bg-red-950 text-red-400 text-xs font-semibold border border-red-900/50">
                          Failed
                        </span>
                      )}
                    </td>
                    <td className="px-6 py-4" onClick={(e) => e.stopPropagation()}>
                      {camp.status === "draft" && (
                        <button
                          onClick={() => handleLaunchCampaign(camp.id)}
                          className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white font-semibold rounded text-xs transition-colors flex items-center gap-1"
                        >
                          <Play className="w-3 h-3 fill-current" />
                          Launch
                        </button>
                      )}
                      {camp.status !== "draft" && (
                        <button
                          onClick={() => setSelectedCampId(camp.id)}
                          className="text-xs text-purple-400 hover:text-purple-300 font-semibold"
                        >
                          Track stats
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Campaign Wizard Modal (Step-by-step) */}
      {wizardOpen && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
          <div className="bg-slate-950 border border-slate-800 rounded-2xl w-full max-w-lg overflow-hidden shadow-2xl animate-scaleIn">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-800 flex justify-between items-center bg-slate-900/20">
              <span className="font-bold text-white text-lg flex items-center gap-2">
                <Send className="w-5 h-5 text-purple-400" />
                Campaign Creation Wizard
              </span>
              <button
                onClick={() => setWizardOpen(false)}
                className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-900"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Steps Progress */}
            <div className="px-6 py-3 bg-slate-900/40 border-b border-slate-850 flex gap-2">
              {[1, 2, 3].map((step) => (
                <div
                  key={step}
                  className={cn(
                    "h-1 flex-1 rounded-full",
                    wizardStep >= step ? "bg-purple-500" : "bg-slate-800"
                  )}
                />
              ))}
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-4">
              {wizardStep === 1 && (
                <div className="space-y-4">
                  <h3 className="font-semibold text-slate-200 text-sm">Step 1: Campaign details</h3>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-500 block uppercase tracking-wider">
                      Campaign Name
                    </label>
                    <input
                      type="text"
                      placeholder="e.g. Festival Winback"
                      className="w-full px-4 py-2.5 rounded-lg border border-slate-800 bg-slate-950 text-slate-200 text-sm focus:outline-none focus:border-purple-500"
                      value={newCampName}
                      onChange={(e) => setNewCampName(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-500 block uppercase tracking-wider">
                      Delivery Channel
                    </label>
                    <select
                      className="w-full px-4 py-2.5 rounded-lg border border-slate-800 bg-slate-950 text-slate-200 text-sm focus:outline-none focus:border-purple-500"
                      value={newCampChannel}
                      onChange={(e) => setNewCampChannel(e.target.value)}
                    >
                      {[
                        { id: "email", label: "Email" },
                        { id: "whatsapp", label: "WhatsApp" },
                        { id: "sms", label: "SMS" },
                        { id: "rcs", label: "RCS" },
                      ].map((ch) => (
                        <option key={ch.id} value={ch.id} disabled={!channelStatus[ch.id]}>
                          {ch.label} {channelStatus[ch.id] ? "— live" : "— not configured"}
                        </option>
                      ))}
                    </select>
                    {!channelStatus[newCampChannel] && (
                      <p className="text-xs text-amber-400/80">
                        This channel isn&apos;t connected yet. Add credentials in channel/.env
                        (SMTP for email, Twilio for SMS/WhatsApp) to send on it.
                      </p>
                    )}
                  </div>
                  {newCampChannel === "email" && (
                    <div className="space-y-2">
                      <label className="text-xs font-semibold text-slate-500 block uppercase tracking-wider">
                        Call-to-action link (optional)
                      </label>
                      <input
                        type="url"
                        placeholder="https://yourbrand.com/sale  (defaults to your org website)"
                        className="w-full px-4 py-2.5 rounded-lg border border-slate-800 bg-slate-950 text-slate-200 text-sm focus:outline-none focus:border-purple-500 placeholder:text-slate-600"
                        value={ctaUrl}
                        onChange={(e) => setCtaUrl(e.target.value)}
                      />
                      <p className="text-xs text-slate-500">
                        The email&apos;s button links here — clicks are tracked through Orbit.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {wizardStep === 2 && (
                <div className="space-y-4">
                  <h3 className="font-semibold text-slate-200 text-sm">Step 2: Target segment</h3>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-500 block uppercase tracking-wider">
                      Select saved segment
                    </label>
                    <select
                      className="w-full px-4 py-2.5 rounded-lg border border-slate-800 bg-slate-950 text-slate-200 text-sm focus:outline-none focus:border-purple-500"
                      value={selectedSegmentId}
                      onChange={(e) => setSelectedSegmentId(e.target.value)}
                    >
                      <option value="">-- Choose Segment --</option>
                      {segments.map((seg) => (
                        <option key={seg.id} value={seg.id}>
                          {seg.name} ({seg.customer_count} customers)
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              )}

              {wizardStep === 3 && (
                <div className="space-y-4">
                  <h3 className="font-semibold text-slate-200 text-sm">Step 3: Message templates</h3>
                  <div className="space-y-2">
                    <label className="text-xs font-semibold text-slate-500 block uppercase tracking-wider">
                      Base Template Body
                    </label>
                    <textarea
                      placeholder="Hey {first_name}, grabbed your {last_product} yet? Use discount in {city}!"
                      rows={4}
                      className="w-full p-4 rounded-lg border border-slate-800 bg-slate-950 text-slate-200 text-sm focus:outline-none focus:border-purple-500 placeholder:text-slate-650"
                      value={messageTemplate}
                      onChange={(e) => setMessageTemplate(e.target.value)}
                    />
                  </div>
                  <label className="flex items-center gap-2 p-3 rounded-lg border border-purple-900/30 bg-purple-950/10 cursor-pointer">
                    <input
                      type="checkbox"
                      className="accent-purple-500 w-4 h-4"
                      checked={personalized}
                      onChange={(e) => setPersonalized(e.target.checked)}
                    />
                    <div>
                      <span className="text-xs font-bold text-purple-300 block">
                        Enable AI Personalization
                      </span>
                      <span className="text-[10px] text-slate-400 block">
                        Generates a unique customized draft context per client using LLM.
                      </span>
                    </div>
                  </label>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-800 bg-slate-900/20 flex justify-between items-center">
              <button
                className="px-4 py-2 border border-slate-800 rounded-lg text-slate-400 hover:text-white text-sm font-semibold disabled:opacity-50"
                onClick={() => setWizardStep((s) => Math.max(1, s - 1))}
                disabled={wizardStep === 1}
              >
                Back
              </button>
              {wizardStep < 3 ? (
                <button
                  className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white rounded-lg text-sm font-semibold"
                  onClick={() => setWizardStep((s) => Math.min(3, s + 1))}
                >
                  Continue
                </button>
              ) : (
                <button
                  className="px-4 py-2 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg text-sm font-bold shadow-lg hover:opacity-90 transition-opacity flex items-center gap-1"
                  onClick={handleCreateCampaign}
                  disabled={creating}
                >
                  {creating && <Loader2 className="w-4 h-4 animate-spin" />}
                  Finish & Save Draft
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Side Stats Panel (Live Tracker) */}
      {selectedCampId && (
        <div className="fixed inset-y-0 right-0 w-full md:w-1/2 bg-slate-950/85 backdrop-blur-md border-l border-slate-800 z-50 shadow-2xl flex flex-col h-screen">
          <div className="h-16 flex items-center justify-between px-6 border-b border-slate-800 bg-slate-900/20">
            <div className="flex items-center gap-2 text-slate-200">
              <Activity className="w-5 h-5 text-purple-400" />
              <span className="font-bold">Live Campaign Tracker</span>
            </div>
            <button
              onClick={() => setSelectedCampId(null)}
              className="text-slate-400 hover:text-white p-1 rounded hover:bg-slate-900"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {statsLoading ? (
              <div className="flex flex-col items-center justify-center h-64 gap-2">
                <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
                <span className="text-slate-400 text-sm">Polling campaign metrics...</span>
              </div>
            ) : stats ? (
              <>
                {/* Overview info */}
                <div>
                  <h3 className="text-xl font-bold text-white">{stats.name}</h3>
                  <span className="text-xs text-slate-500">
                    ID: {stats.campaign_id}
                  </span>
                </div>

                {/* Progress Grid */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  <div className="p-3 bg-slate-900/40 border border-slate-800 rounded-lg text-center">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Sent</span>
                    <span className="text-lg font-bold text-white">{stats.total_sent}</span>
                  </div>
                  <div className="p-3 bg-slate-900/40 border border-slate-800 rounded-lg text-center">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Delivered</span>
                    <span className="text-lg font-bold text-blue-400">{stats.total_delivered}</span>
                  </div>
                  <div className="p-3 bg-slate-900/40 border border-slate-800 rounded-lg text-center">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Opened</span>
                    <span className="text-lg font-bold text-purple-400">{stats.total_opened}</span>
                  </div>
                  <div className="p-3 bg-slate-900/40 border border-slate-800 rounded-lg text-center">
                    <span className="text-[10px] text-slate-500 uppercase tracking-wider block">Failed</span>
                    <span className="text-lg font-bold text-red-500">{stats.total_failed}</span>
                  </div>
                </div>

                {/* Rate Metrics */}
                <div className="space-y-4 pt-4 border-t border-slate-805">
                  <h4 className="font-semibold text-slate-300 text-sm">Conversion Funnel</h4>
                  <div className="space-y-3">
                    <div>
                      <div className="flex justify-between text-xs font-semibold text-slate-400 mb-1">
                        <span>Delivery Rate</span>
                        <span>{stats.delivery_rate}%</span>
                      </div>
                      <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-blue-500 h-full" style={{ width: `${stats.delivery_rate}%` }} />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-xs font-semibold text-slate-400 mb-1">
                        <span>Open Rate</span>
                        <span>{stats.open_rate}%</span>
                      </div>
                      <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-purple-500 h-full" style={{ width: `${stats.open_rate}%` }} />
                      </div>
                    </div>

                    <div>
                      <div className="flex justify-between text-xs font-semibold text-slate-400 mb-1">
                        <span>Click Rate</span>
                        <span>{stats.click_rate}%</span>
                      </div>
                      <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                        <div className="bg-teal-500 h-full" style={{ width: `${stats.click_rate}%` }} />
                      </div>
                    </div>
                  </div>
                </div>

                {/* AI Analyst Postmortem */}
                {stats.ai_postmortem && (
                  <div className="p-5 rounded-xl border border-purple-900/30 bg-purple-950/15 space-y-3 relative overflow-hidden">
                    <div className="flex gap-2 items-center text-purple-400 font-bold text-xs uppercase tracking-wider">
                      <Sparkles className="w-4 h-4 text-purple-400 animate-pulse" />
                      AI Analyst Postmortem
                    </div>
                    <p className="text-slate-200 text-sm leading-relaxed font-medium">
                      {stats.ai_postmortem}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center text-slate-500 py-12">No stats available.</div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
