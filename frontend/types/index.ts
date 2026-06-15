/**
 * Shared TypeScript types matching the Pydantic models from the CRM backend.
 */

// ── Customer ──────────────────────────────────────────────────────────────────

export interface CustomerScore {
  recency_days: number | null;
  frequency: number | null;
  monetary: number | null;
  rfm_score: number | null;
  churn_risk: "low" | "medium" | "high" | "critical" | null;
  top_category: string | null;
  last_product: string | null;
  scored_at: string | null;
}

export interface Customer {
  id: string;
  external_id: string | null;
  first_name: string;
  last_name: string | null;
  phone: string | null;
  email: string | null;
  city: string | null;
  channel_pref: "whatsapp" | "sms" | "email" | "rcs";
  created_at: string;
  updated_at: string;
  score: CustomerScore | null;
}

// ── Order ─────────────────────────────────────────────────────────────────────

export interface Order {
  id: string;
  customer_id: string;
  order_date: string;
  amount: number;
  category: string | null;
  product_name: string | null;
  status: "completed" | "returned" | "cancelled";
  created_at: string;
}

// ── Segment ───────────────────────────────────────────────────────────────────

export interface FilterCondition {
  field: string;
  op: string;
  value: unknown;
}

export interface FilterSpec {
  operator: "AND" | "OR";
  conditions: (FilterCondition | FilterSpec)[];
}

export interface Segment {
  id: string;
  name: string;
  description: string | null;
  filter_spec: FilterSpec;
  nl_query: string | null;
  customer_count: number;
  created_at: string;
  updated_at: string;
}

// ── Campaign ──────────────────────────────────────────────────────────────────

export type CampaignStatus = "draft" | "scheduled" | "running" | "completed" | "failed";

export interface Campaign {
  id: string;
  name: string;
  segment_id: string;
  channel: "whatsapp" | "sms" | "email" | "rcs";
  message_template: string;
  personalized: boolean;
  status: CampaignStatus;
  scheduled_at: string | null;
  launched_at: string | null;
  completed_at: string | null;
  created_by: string;
  total_sent: number;
  total_delivered: number;
  total_opened: number;
  total_clicked: number;
  total_failed: number;
  ai_postmortem: string | null;
  created_at: string;
  updated_at: string;
}

export interface CampaignStats {
  campaign_id: string;
  name: string;
  status: CampaignStatus;
  total_sent: number;
  total_delivered: number;
  total_opened: number;
  total_clicked: number;
  total_failed: number;
  delivery_rate: number;
  open_rate: number;
  click_rate: number;
  channel_breakdown: Record<string, Record<string, number>>;
  ai_postmortem: string | null;
}

// ── Copilot ───────────────────────────────────────────────────────────────────

export type CopilotEventType = "text" | "tool_call" | "tool_result" | "done";

export interface CopilotEvent {
  type: CopilotEventType;
  content?: string;
  name?: string;
  args?: Record<string, unknown>;
  result?: unknown;
}
