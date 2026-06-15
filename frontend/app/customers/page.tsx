"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import {
  Search,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  X,
  User,
  ShoppingBag,
  Send,
  Loader2,
  Trash2,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";

export default function CustomersPage() {
  const [customers, setCustomers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [churnRisk, setChurnRisk] = useState("all");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  // Selected customer details
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [details, setDetails] = useState<any | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);

  // Delete state
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmAll, setConfirmAll] = useState(false);
  const [removingAll, setRemovingAll] = useState(false);

  const limit = 15;

  const handleDeleteCustomer = async (e: React.MouseEvent, cust: any) => {
    e.stopPropagation();
    if (!window.confirm(`Delete ${cust.first_name} ${cust.last_name || ""}? This also removes their orders and message history.`)) return;
    setDeletingId(cust.id);
    try {
      await api.customers.remove(cust.id);
      setCustomers((prev) => prev.filter((c) => c.id !== cust.id));
      setTotal((t) => Math.max(0, t - 1));
      if (selectedId === cust.id) {
        setSelectedId(null);
        setDetails(null);
      }
      toast.success("Customer deleted.");
    } catch (err: any) {
      toast.error(err.message ?? "Could not delete customer.");
    } finally {
      setDeletingId(null);
    }
  };

  const handleRemoveAll = async () => {
    setRemovingAll(true);
    try {
      const res = await api.customers.removeAll();
      setCustomers([]);
      setTotal(0);
      setSelectedId(null);
      setDetails(null);
      setConfirmAll(false);
      toast.success(`Removed ${res.count ?? "all"} customers and their data.`);
    } catch (err: any) {
      toast.error(err.message ?? "Could not remove data.");
    } finally {
      setRemovingAll(false);
    }
  };

  useEffect(() => {
    async function loadCustomers() {
      setLoading(true);
      try {
        const params: any = {
          page,
          limit,
          search: search || undefined,
          churn_risk: churnRisk === "all" ? undefined : churnRisk,
        };
        const res = await api.customers.list(params);
        // The backend returns { data, total, page, limit }
        const rows = Array.isArray(res?.data) ? res.data : [];
        setCustomers(rows);
        setTotal(typeof res?.total === "number" ? res.total : rows.length);
      } catch (err) {
        console.error("Error loading customers", err);
        // Fallback mockup list
        const mockList = [
          { id: "c1", first_name: "Priya", last_name: "Sharma", email: "priya@gmail.com", phone: "+919876543210", city: "Mumbai", score: { rfm_score: 84, churn_risk: "low" } },
          { id: "c2", first_name: "Rahul", last_name: "Verma", email: "rahul@yahoo.com", phone: "+919812345678", city: "Delhi", score: { rfm_score: 38, churn_risk: "high" } },
          { id: "c3", first_name: "Ananya", last_name: "Iyer", email: "ananya@outlook.com", phone: "+918887776665", city: "Bangalore", score: { rfm_score: 15, churn_risk: "critical" } },
          { id: "c4", first_name: "Amit", last_name: "Patel", email: "amit.patel@gmail.com", phone: "+919998887776", city: "Ahmedabad", score: { rfm_score: 52, churn_risk: "medium" } },
        ];
        setCustomers(mockList);
        setTotal(mockList.length);
      } finally {
        setLoading(false);
      }
    }
    loadCustomers();
  }, [page, search, churnRisk]);

  // Handle row click
  const handleSelectCustomer = async (id: string) => {
    setSelectedId(id);
    setDetailsLoading(true);
    try {
      const detailData = await api.customers.get(id);
      setDetails(detailData);
    } catch (err) {
      console.error("Error loading customer profile details", err);
      // Fallback mockup profile details
      setDetails({
        id,
        first_name: "Ananya",
        last_name: "Iyer",
        email: "ananya@outlook.com",
        phone: "+918887776665",
        city: "Bangalore",
        score: {
          rfm_score: 15,
          churn_risk: "critical",
          recency_days: 98,
          frequency: 1,
          monetary: 1250,
          top_category: "haircare",
          last_product: "Argan Oil Shampoo",
        },
        ai_summary: "Frequent buyer of haircare who has not ordered in 98 days. High probability of churn due to promotional inactivity; suggest sending a WhatsApp coupon code.",
        orders: [
          { id: "o1", order_date: "2026-03-06T10:00:00Z", amount: 1250, status: "completed", items_count: 1 }
        ],
        campaigns: [
          { name: "Haircare Spring Launch", sent_at: "2026-02-15T00:00:00Z", status: "opened" }
        ]
      });
    } finally {
      setDetailsLoading(false);
    }
  };

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto relative min-h-screen">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">
            Customers
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Explore profiles, RFM scores, and generate instant AI summaries.
          </p>
        </div>
        <button
          onClick={() => setConfirmAll(true)}
          disabled={total === 0}
          className="shrink-0 flex items-center gap-2 px-4 py-2 rounded-lg border border-red-900/50 bg-red-950/20 text-red-400 hover:bg-red-950/40 text-sm font-semibold transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <Trash2 className="w-4 h-4" />
          Remove all data
        </button>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
        {/* Search */}
        <div className="w-full md:w-80 relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by name, email, phone..."
            className="w-full pl-10 pr-4 py-2 rounded-lg border border-slate-800 bg-slate-950 text-slate-200 text-sm focus:outline-none focus:border-purple-500 transition-colors"
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
          />
        </div>

        {/* Churn Risk Tab Bar */}
        <div className="flex bg-slate-950 border border-slate-800 p-1 rounded-lg w-full md:w-auto overflow-x-auto">
          {["all", "low", "medium", "high", "critical"].map((risk) => (
            <button
              key={risk}
              className={cn(
                "px-4 py-1.5 rounded-md text-xs font-semibold uppercase tracking-wider transition-all",
                churnRisk === risk
                  ? "bg-slate-800 text-white"
                  : "text-slate-500 hover:text-slate-300"
              )}
              onClick={() => {
                setChurnRisk(risk);
                setPage(1);
              }}
            >
              {risk}
            </button>
          ))}
        </div>
      </div>

      {/* Customers Table */}
      <div className="border border-slate-800 bg-slate-900/10 rounded-xl overflow-hidden backdrop-blur-sm">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="bg-slate-900/50 border-b border-slate-800 text-slate-400 text-xs uppercase tracking-wider font-semibold">
              <tr>
                <th className="px-6 py-4">Name</th>
                <th className="px-6 py-4">Location</th>
                <th className="px-6 py-4">RFM Score</th>
                <th className="px-6 py-4">Risk Level</th>
                <th className="px-6 py-4">Contact</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80">
              {loading ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-slate-500">
                    <div className="flex items-center justify-center gap-2">
                      <Loader2 className="w-4 h-4 animate-spin text-purple-400" />
                      Loading customers...
                    </div>
                  </td>
                </tr>
              ) : customers.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-center py-12 text-slate-500">
                    No customers match the current criteria.
                  </td>
                </tr>
              ) : (
                customers.map((cust) => (
                  <tr
                    key={cust.id}
                    className="hover:bg-slate-900/30 cursor-pointer transition-colors"
                    onClick={() => handleSelectCustomer(cust.id)}
                  >
                    <td className="px-6 py-4 font-medium text-slate-200">
                      {cust.first_name} {cust.last_name || ""}
                    </td>
                    <td className="px-6 py-4 text-slate-400">{cust.city || "—"}</td>
                    <td className="px-6 py-4 text-slate-300 font-semibold">
                      {cust.score?.rfm_score ?? "—"}
                    </td>
                    <td className="px-6 py-4">
                      {cust.score?.churn_risk === "low" && (
                        <span className="px-2 py-0.5 rounded bg-teal-950 text-teal-400 text-xs font-semibold uppercase tracking-wider border border-teal-900/50">
                          Low
                        </span>
                      )}
                      {cust.score?.churn_risk === "medium" && (
                        <span className="px-2 py-0.5 rounded bg-yellow-950 text-yellow-400 text-xs font-semibold uppercase tracking-wider border border-yellow-900/50">
                          Medium
                        </span>
                      )}
                      {cust.score?.churn_risk === "high" && (
                        <span className="px-2 py-0.5 rounded bg-amber-950 text-amber-400 text-xs font-semibold uppercase tracking-wider border border-amber-900/50">
                          High
                        </span>
                      )}
                      {cust.score?.churn_risk === "critical" && (
                        <span className="px-2 py-0.5 rounded bg-red-950 text-red-400 text-xs font-semibold uppercase tracking-wider border border-red-900/50">
                          Critical
                        </span>
                      )}
                      {!cust.score?.churn_risk && (
                        <span className="text-slate-500">—</span>
                      )}
                    </td>
                    <td className="px-6 py-4 text-slate-500 text-xs">
                      {cust.phone || cust.email}
                    </td>
                    <td className="px-6 py-4 text-right">
                      <button
                        title="Delete customer"
                        onClick={(e) => handleDeleteCustomer(e, cust)}
                        disabled={deletingId === cust.id}
                        className="p-1.5 rounded-md text-slate-500 hover:text-red-400 hover:bg-red-950/30 transition-colors disabled:opacity-50"
                      >
                        {deletingId === cust.id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Trash2 className="w-4 h-4" />
                        )}
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Footer */}
        <div className="p-4 border-t border-slate-800 bg-slate-900/20 flex items-center justify-between">
          <span className="text-xs text-slate-500">
            Showing page {page}
          </span>
          <div className="flex gap-2">
            <button
              className="p-1.5 rounded bg-slate-950 border border-slate-800 text-slate-400 hover:text-white disabled:opacity-50 disabled:hover:text-slate-400"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              className="p-1.5 rounded bg-slate-950 border border-slate-800 text-slate-400 hover:text-white disabled:opacity-50 disabled:hover:text-slate-400"
              onClick={() => setPage((p) => p + 1)}
              disabled={customers.length < limit}
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Slide-out Customer Detail Panel Drawer */}
      {selectedId && (
        <div className="fixed inset-y-0 right-0 w-full md:w-1/2 bg-slate-950/80 backdrop-blur-md border-l border-slate-800 z-50 shadow-2xl flex flex-col h-screen">
          {/* Drawer Header */}
          <div className="h-16 flex items-center justify-between px-6 border-b border-slate-800 bg-slate-900/20">
            <div className="flex items-center gap-2">
              <User className="w-5 h-5 text-purple-400" />
              <span className="font-bold text-slate-200">Customer Profile</span>
            </div>
            <button
              className="p-1.5 rounded hover:bg-slate-900 text-slate-400 hover:text-white"
              onClick={() => {
                setSelectedId(null);
                setDetails(null);
              }}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Drawer Content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-6">
            {detailsLoading ? (
              <div className="flex flex-col items-center justify-center h-64 gap-2">
                <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
                <span className="text-slate-400 text-sm">Assembling profile timeline...</span>
              </div>
            ) : details ? (
              <>
                {/* Profile Overview */}
                <div className="p-4 rounded-xl border border-slate-800 bg-slate-900/10 flex gap-4 items-center">
                  <div className="w-12 h-12 rounded-full bg-purple-900/30 flex items-center justify-center font-bold text-lg text-purple-400 border border-purple-800/50">
                    {details.first_name[0]}
                  </div>
                  <div>
                    <h3 className="font-bold text-white text-lg">
                      {details.first_name} {details.last_name || ""}
                    </h3>
                    <p className="text-xs text-slate-500">
                      {details.city || "Unknown Location"} • {details.phone || details.email}
                    </p>
                  </div>
                </div>

                {/* AI summary 360 */}
                {details.ai_summary && (
                  <div className="p-5 rounded-xl border border-purple-900/30 bg-purple-950/10 space-y-2 relative overflow-hidden">
                    <div className="flex gap-2 items-center text-purple-400 font-bold text-xs uppercase tracking-wider">
                      <Sparkles className="w-4 h-4 text-purple-400 animate-pulse" />
                      AI 360 Summary
                    </div>
                    <p className="text-slate-200 text-sm leading-relaxed font-medium">
                      {details.ai_summary}
                    </p>
                  </div>
                )}

                {/* RFM Score Detail Grid */}
                <div className="grid grid-cols-3 gap-4">
                  <div className="p-4 rounded-lg border border-slate-800 bg-slate-900/40 text-center">
                    <span className="text-xs text-slate-500 block uppercase tracking-wider">
                      Recency
                    </span>
                    <span className="text-lg font-bold text-white">
                      {details.score?.recency_days ?? "—"} d
                    </span>
                  </div>
                  <div className="p-4 rounded-lg border border-slate-800 bg-slate-900/40 text-center">
                    <span className="text-xs text-slate-500 block uppercase tracking-wider">
                      Frequency
                    </span>
                    <span className="text-lg font-bold text-white">
                      {details.score?.frequency ?? "—"} orders
                    </span>
                  </div>
                  <div className="p-4 rounded-lg border border-slate-800 bg-slate-900/40 text-center">
                    <span className="text-xs text-slate-500 block uppercase tracking-wider">
                      Monetary
                    </span>
                    <span className="text-lg font-bold text-teal-400">
                      ₹{details.score?.monetary?.toLocaleString() ?? "0"}
                    </span>
                  </div>
                </div>

                {/* Order History */}
                <div className="space-y-3">
                  <h4 className="font-semibold text-slate-300 text-sm flex items-center gap-2">
                    <ShoppingBag className="w-4 h-4 text-slate-400" />
                    Order History ({details.orders?.length ?? 0})
                  </h4>
                  {details.orders && details.orders.length > 0 ? (
                    <div className="space-y-2">
                      {details.orders.map((ord: any) => (
                        <div
                          key={ord.id}
                          className="p-3 rounded-lg border border-slate-800/80 bg-slate-900/10 flex justify-between items-center text-xs"
                        >
                          <div>
                            <span className="text-slate-300 block font-semibold">
                              ₹{ord.amount.toLocaleString()}
                            </span>
                            <span className="text-slate-500">
                              {new Date(ord.order_date).toLocaleDateString()}
                            </span>
                          </div>
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 capitalize">
                            {ord.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 text-center py-4">No order history available.</p>
                  )}
                </div>

                {/* Campaign History */}
                <div className="space-y-3">
                  <h4 className="font-semibold text-slate-300 text-sm flex items-center gap-2">
                    <Send className="w-4 h-4 text-slate-400" />
                    Campaign Touchpoints ({details.campaigns?.length ?? 0})
                  </h4>
                  {details.campaigns && details.campaigns.length > 0 ? (
                    <div className="space-y-2">
                      {details.campaigns.map((camp: any, idx: number) => (
                        <div
                          key={idx}
                          className="p-3 rounded-lg border border-slate-800/80 bg-slate-900/10 flex justify-between items-center text-xs"
                        >
                          <div>
                            <span className="text-slate-300 block font-semibold">
                              {camp.name}
                            </span>
                            <span className="text-slate-500">
                              {camp.sent_at ? new Date(camp.sent_at).toLocaleDateString() : "Pending"}
                            </span>
                          </div>
                          <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-400 capitalize">
                            {camp.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-xs text-slate-500 text-center py-4">No campaign touchpoints recorded.</p>
                  )}
                </div>
              </>
            ) : (
              <div className="text-center text-slate-500 py-12">Failed to load profile.</div>
            )}
          </div>
        </div>
      )}

      {/* Remove-all confirmation modal */}
      {confirmAll && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="w-full max-w-md rounded-2xl border border-red-900/40 bg-slate-900 p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-3">
              <div className="w-10 h-10 rounded-full bg-red-950/50 border border-red-900/50 flex items-center justify-center">
                <AlertTriangle className="w-5 h-5 text-red-400" />
              </div>
              <h3 className="text-lg font-bold text-white">Remove all customer data?</h3>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">
              This permanently deletes <span className="text-red-300 font-semibold">all {total} customers</span> in
              your organization, along with their orders, RFM scores, and message history.
              Segments and campaigns are kept. <span className="text-slate-300">This cannot be undone.</span>
            </p>
            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setConfirmAll(false)}
                disabled={removingAll}
                className="flex-1 py-2.5 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 text-sm font-semibold transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleRemoveAll}
                disabled={removingAll}
                className="flex-1 py-2.5 rounded-lg bg-red-600 hover:bg-red-500 text-white text-sm font-semibold flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
              >
                {removingAll ? <Loader2 className="w-4 h-4 animate-spin" /> : <Trash2 className="w-4 h-4" />}
                Delete everything
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
