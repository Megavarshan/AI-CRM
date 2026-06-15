"use client";

import { useEffect, useState } from "react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { Database, Loader2, IndianRupee, ShoppingBag, Users, Receipt } from "lucide-react";
import { api } from "@/lib/api";
import { toast } from "sonner";

const PURPLES = ["#a855f7", "#818cf8", "#e879f9", "#38bdf8", "#2dd4bf", "#fbbf24"];
const CHURN_COLORS: Record<string, string> = {
  low: "#2dd4bf",
  medium: "#fbbf24",
  high: "#fb923c",
  critical: "#f87171",
};

const tooltipStyle = {
  backgroundColor: "#0f172a",
  border: "1px solid #334155",
  borderRadius: "8px",
  fontSize: "12px",
};

function ChartCard({ title, subtitle, children }: { title: string; subtitle?: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/20 p-5">
      <h3 className="font-bold text-white text-sm">{title}</h3>
      {subtitle && <p className="text-xs text-slate-500 mb-3">{subtitle}</p>}
      <div className="h-64 mt-3">{children}</div>
    </div>
  );
}

export default function DataExplorerPage() {
  const [data, setData] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.analytics
      .rawData()
      .then(setData)
      .catch((e) => toast.error(`Failed to load data: ${e.message}`))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center gap-3 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
        <span className="text-sm">Crunching your raw data...</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen flex items-center justify-center text-slate-500 text-sm">
        No data available. Import customers and orders first.
      </div>
    );
  }

  const s = data.summary;
  const summaryCards = [
    { label: "Total Customers", value: s.total_customers.toLocaleString("en-IN"), icon: Users, color: "text-purple-400" },
    { label: "Total Orders", value: s.total_orders.toLocaleString("en-IN"), icon: ShoppingBag, color: "text-indigo-400" },
    { label: "Total Revenue", value: `₹${Math.round(s.total_revenue).toLocaleString("en-IN")}`, icon: IndianRupee, color: "text-teal-400" },
    { label: "Avg Order Value", value: `₹${Math.round(s.avg_order_value).toLocaleString("en-IN")}`, icon: Receipt, color: "text-fuchsia-400" },
  ];

  return (
    <div className="p-8 space-y-6 max-w-7xl mx-auto min-h-screen">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
          <Database className="w-7 h-7 text-purple-400" />
          Data Explorer
        </h1>
        <p className="text-slate-400 text-sm mt-1">
          Visual exploration of your raw customer and order data.
        </p>
      </div>

      {/* Summary cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {summaryCards.map((c) => {
          const Icon = c.icon;
          return (
            <div key={c.label} className="rounded-xl border border-slate-800 bg-slate-900/20 p-5">
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">{c.label}</span>
                <Icon className={`w-4 h-4 ${c.color}`} />
              </div>
              <div className="text-2xl font-extrabold text-white mt-2">{c.value}</div>
            </div>
          );
        })}
      </div>

      {/* Revenue + orders over time */}
      <ChartCard title="Orders & Revenue Over Time" subtitle="Completed orders by month">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data.monthly}>
            <defs>
              <linearGradient id="rev" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#a855f7" stopOpacity={0.5} />
                <stop offset="95%" stopColor="#a855f7" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="month" stroke="#64748b" fontSize={11} />
            <YAxis yAxisId="rev" stroke="#64748b" fontSize={11} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
            <YAxis yAxisId="ord" orientation="right" stroke="#64748b" fontSize={11} />
            <Tooltip contentStyle={tooltipStyle} />
            <Legend wrapperStyle={{ fontSize: "12px" }} />
            <Area yAxisId="rev" type="monotone" dataKey="revenue" stroke="#a855f7" fill="url(#rev)" name="Revenue (₹)" />
            <Area yAxisId="ord" type="monotone" dataKey="orders" stroke="#818cf8" fill="transparent" name="Orders" />
          </AreaChart>
        </ResponsiveContainer>
      </ChartCard>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Category revenue */}
        <ChartCard title="Revenue by Category" subtitle="Completed orders only">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.categories}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="category" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="revenue" name="Revenue (₹)" radius={[6, 6, 0, 0]}>
                {data.categories.map((_: any, i: number) => (
                  <Cell key={i} fill={PURPLES[i % PURPLES.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Top cities */}
        <ChartCard title="Customers by City" subtitle="Top 10 cities">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.cities} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis type="number" stroke="#64748b" fontSize={11} />
              <YAxis type="category" dataKey="city" stroke="#64748b" fontSize={11} width={80} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="customers" name="Customers" fill="#818cf8" radius={[0, 6, 6, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Channel preference */}
        <ChartCard title="Channel Preference" subtitle="How customers want to hear from you">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data.channels}
                dataKey="customers"
                nameKey="channel"
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={4}
              >
                {data.channels.map((_: any, i: number) => (
                  <Cell key={i} fill={PURPLES[i % PURPLES.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Spend distribution */}
        <ChartCard title="Customer Spend Distribution" subtitle="Lifetime spend buckets (₹)">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.spend_distribution}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="bucket" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="customers" name="Customers" fill="#e879f9" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Churn risk */}
        <ChartCard title="Churn Risk Split" subtitle="From the RFM scoring engine">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={data.churn}
                dataKey="customers"
                nameKey="risk"
                cx="50%"
                cy="50%"
                innerRadius={55}
                outerRadius={85}
                paddingAngle={4}
              >
                {data.churn.map((entry: any, i: number) => (
                  <Cell key={i} fill={CHURN_COLORS[entry.risk] ?? PURPLES[i]} />
                ))}
              </Pie>
              <Tooltip contentStyle={tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: "12px" }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        {/* Order status */}
        <ChartCard title="Order Status" subtitle="Completed vs returned vs cancelled">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data.order_status}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="status" stroke="#64748b" fontSize={11} />
              <YAxis stroke="#64748b" fontSize={11} />
              <Tooltip contentStyle={tooltipStyle} />
              <Bar dataKey="orders" name="Orders" fill="#2dd4bf" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </div>
  );
}
