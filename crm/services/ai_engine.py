"""
AI Engine — all LLM interactions for the CRM service.

Features implemented here:
  1. NL2Segment      — NL query → structured filter_spec JSON
  2. Personalization — per-customer message generation (batch of 20)
  3. Copilot Agent   — agentic loop with tool calling (SSE streaming)
  4. Customer 360    — 2-sentence AI summary per customer profile
  5. Post-mortem     — campaign analyst writeup after completion
"""

from __future__ import annotations

import json
import logging
import re
from typing import AsyncGenerator

from config import settings

logger = logging.getLogger(__name__)

# Lazy Groq client — avoids crash at import time when GROQ_API_KEY is None
_groq_client = None

def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        if not settings.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Please add it to your .env file."
            )
        from groq import Groq
        _groq_client = Groq(api_key=settings.GROQ_API_KEY)
    return _groq_client

MODEL = settings.GROQ_MODEL


# ── 1. NL2Segment ─────────────────────────────────────────────────────────────

NL2SEGMENT_SYSTEM_PROMPT = """
You are a CRM query translator. Convert natural language customer segment descriptions into a structured JSON filter spec.

The filter spec format is:
{
  "operator": "AND" | "OR",
  "conditions": [
    { "field": "<field_name>", "op": "<operator>", "value": <value> }
  ]
}

Available fields: monetary (float, INR), recency_days (int), frequency (int),
churn_risk ('low'|'medium'|'high'|'critical'), top_category (string),
city (string), channel_pref (string), rfm_score (float 0-100)

Available operators: eq, neq, gt, gte, lt, lte, in, not_in, contains

Rules:
- "haven't bought in X days" → recency_days gte X
- "spent over ₹X" or "high value" → monetary gte X
- "loyal customers" → frequency gte 5
- "at risk" or "churning" → churn_risk in ['high','critical']
- Nested AND/OR is allowed using a 'conditions' array with its own 'operator'
- Return ONLY valid JSON. No explanation. No markdown. No preamble.
"""


def nl_to_segment(query: str) -> dict:
    """Translate a natural language query to a filter_spec dict."""
    response = _get_groq_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": NL2SEGMENT_SYSTEM_PROMPT},
            {"role": "user", "content": query},
        ],
        temperature=0,
        max_tokens=500,
    )
    raw = response.choices[0].message.content.strip()
    # Strip markdown code fences if the LLM wraps its output
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ── 2. Per-Customer Message Personalization ───────────────────────────────────

PERSONALIZATION_SYSTEM_PROMPT = """
You are a CRM message writer for a D2C brand. Generate personalized WhatsApp/SMS messages.

Rules:
- Always use the customer's first name
- Reference their specific last product or top category
- Mention time since last order if it adds context
- Create gentle urgency without being pushy
- Warm, conversational tone — like a helpful friend, not a brand announcement
- Under 160 characters for SMS, under 300 for WhatsApp
- Maximum 1 emoji, at end of sentence only
- No hashtags. No "Dear Customer". No corporate speak.

Good examples:
- "Hey Priya, your Rose Serum is almost done, isn't it? 😊 Grab a refill today — 15% off just for you."
- "Rahul, your last order was 3 weeks ago. Your cart misses you. Here's ₹100 to come back."

Return ONLY a JSON array of message strings, one per customer, in the same order as the input.
No explanation. No markdown.
"""


def generate_personalized_messages(
    customers: list[dict],
    campaign_brief: str,
    channel: str,
    org_id: str | None = None,
) -> list[str]:
    """
    Generate unique personalized messages for a list of customers.

    Parameters
    ----------
    customers      : list of dicts with keys: first_name, last_product,
                     top_category, recency_days, city
    campaign_brief : short description of the campaign goal
    channel        : whatsapp | sms | email | rcs

    Returns
    -------
    list[str] — one message per customer, same order as input
    """
    batch_size = 20
    all_messages: list[str] = []

    # Inject the org's learned preferences (Human-in-the-Loop feedback).
    from services.org_learning import preference_snippet
    learned = preference_snippet(org_id)
    system_prompt = PERSONALIZATION_SYSTEM_PROMPT + (f"\n\n{learned}" if learned else "")

    for i in range(0, len(customers), batch_size):
        batch = customers[i : i + batch_size]
        contexts = [
            {
                "name": c["first_name"],
                "last_product": c.get("last_product") or c.get("top_category", "your last order"),
                "days_ago": c["recency_days"],
                "top_category": c.get("top_category", ""),
                "city": c.get("city", ""),
            }
            for c in batch
        ]
        user_prompt = (
            f"Campaign goal: {campaign_brief}\nChannel: {channel}\n\n"
            f"Generate one personalized message per customer:\n{json.dumps(contexts, indent=2)}"
        )
        response = _get_groq_client().chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            max_tokens=2000,
        )
        batch_messages = json.loads(response.choices[0].message.content.strip())
        all_messages.extend(batch_messages)

    return all_messages


# ── 3. Agentic Copilot ────────────────────────────────────────────────────────

COPILOT_SYSTEM_PROMPT = """
You are Orbit Copilot, an AI campaign manager for a D2C brand.
Your job is to help marketers plan and execute re-engagement campaigns.

Workflow:
1. Understand the marketer's goal
2. Use get_segments to find or create an appropriate audience
3. Use draft_message to write the message
4. Use create_campaign to set it up
5. ALWAYS ask for explicit confirmation before calling launch_campaign
6. After launch, use get_campaign_stats to report progress

Be concise. Show your reasoning. Ask for confirmation at key steps.
When calling tools, explain what you're doing and why.
"""

COPILOT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_segments",
            "description": "List all saved segments with customer counts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "churn_risk_filter": {
                        "type": "string",
                        "enum": ["low", "medium", "high", "critical", "any"],
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "semantic_customer_search",
            "description": (
                "Retrieve real customers by the SEMANTIC MEANING of a description, using vector "
                "search over customer profiles. Use this to ground recommendations in actual "
                "customers when the ask is about intent/affinity that structured filters can't "
                "express (e.g. 'eco-conscious gift buyers', 'price-sensitive skincare lovers')."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Natural-language description of the customers to find"},
                    "limit": {"type": "integer", "description": "How many to retrieve (default 6)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_segment_from_nl",
            "description": "Create a new customer segment from a natural language description.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "nl_query": {"type": "string"},
                },
                "required": ["name", "nl_query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "draft_message",
            "description": "Draft a campaign message template for a given goal and channel.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_goal": {"type": "string"},
                    "channel": {"type": "string", "enum": ["whatsapp", "sms", "email", "rcs"]},
                    "tone": {"type": "string", "enum": ["warm", "urgent", "celebratory", "informational"]},
                },
                "required": ["campaign_goal", "channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_campaign",
            "description": "Create a campaign with a segment, channel, and message template.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "segment_id": {"type": "string"},
                    "channel": {"type": "string"},
                    "message_template": {"type": "string"},
                    "personalized": {"type": "boolean"},
                },
                "required": ["name", "segment_id", "channel", "message_template"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launch_campaign",
            "description": "Launch a campaign. ALWAYS ask for user confirmation before calling this.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                    "confirm": {"type": "boolean"},
                },
                "required": ["campaign_id", "confirm"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_campaign_stats",
            "description": "Get live delivery stats for a running or completed campaign.",
            "parameters": {
                "type": "object",
                "properties": {
                    "campaign_id": {"type": "string"},
                },
                "required": ["campaign_id"],
            },
        },
    },
]


async def execute_tool(name: str, args: dict, org_id: str | None = None) -> dict:
    """Execute a tool call requested by the copilot agent (org-scoped)."""
    from config import supabase

    def scoped(q):
        return q.eq("org_id", org_id) if org_id else q

    try:
        if name == "get_segments":
            # Fetch saved segments
            res = scoped(supabase.table("segments").select("*")).order("created_at", desc=True).execute()
            return {"segments": res.data or []}

        elif name == "semantic_customer_search":
            # RAG retrieval over the customer vector store (grounds the agent)
            from services.semantic import retrieve_context
            ctx = retrieve_context(args["query"], org_id, k=int(args.get("limit", 6)))
            return {"query": args["query"], "retrieved_customers": ctx, "count": len(ctx)}

        elif name == "create_segment_from_nl":
            # Create a segment using natural language translation
            seg_name = args["name"]
            nl_query = args["nl_query"]

            # Translate NL -> filter spec
            filter_spec = nl_to_segment(nl_query)

            # Execute filter spec to calculate initial count (org-scoped)
            from services.segment_executor import execute_filter_spec
            customer_count, _ = execute_filter_spec(filter_spec, org_id)

            payload = {
                "name": seg_name,
                "description": f"AI generated from query: {nl_query}",
                "filter_spec": filter_spec,
                "nl_query": nl_query,
                "customer_count": customer_count,
                "org_id": org_id,
            }
            res = supabase.table("segments").insert(payload).execute()
            if res.data:
                return {"success": True, "segment": res.data[0]}
            return {"error": "Failed to create segment."}

        elif name == "draft_message":
            # Draft message template based on campaign goal and channel
            goal = args["campaign_goal"]
            channel = args["channel"]
            tone = args.get("tone", "warm")

            from services.org_learning import preference_snippet
            learned = preference_snippet(org_id)
            prompt = f"""
You are a creative CRM copywriter. Write a campaign message template.
Goal: {goal}
Channel: {channel}
Tone: {tone}
{learned}

Rules:
- Keep it short: WhatsApp under 250 chars, SMS under 160 chars, Email under 500 chars.
- Use placeholders: {{first_name}}, {{city}}, {{last_product}}, {{top_category}} (when relevant).
- Maximum 1 emoji.
- Under 160 characters if SMS.
- No corporate speak. Make it sound native and personal.

Return ONLY the message template. Do not include quotes or labels.
"""
            import asyncio
            response = await asyncio.to_thread(
                _get_groq_client().chat.completions.create,
                model=MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=200,
            )
            template = response.choices[0].message.content.strip()
            return {"channel": channel, "message_template": template}

        elif name == "create_campaign":
            # Create campaign record in draft status
            payload = {
                "name": args["name"],
                "segment_id": args["segment_id"],
                "channel": args["channel"],
                "message_template": args["message_template"],
                "personalized": args.get("personalized", True),
                "status": "draft",
                "org_id": org_id,
            }
            res = supabase.table("campaigns").insert(payload).execute()
            if res.data:
                return {"success": True, "campaign": res.data[0]}
            return {"error": "Failed to create campaign."}

        elif name == "launch_campaign":
            # Launch a campaign (requires confirm: true)
            campaign_id = args["campaign_id"]
            confirm = args.get("confirm", False)
            if not confirm:
                return {"error": "User confirmation required before launching campaigns."}

            res = scoped(supabase.table("campaigns").select("*").eq("id", campaign_id)).execute()
            if not res.data:
                return {"error": f"Campaign '{campaign_id}' not found."}

            campaign = res.data[0]
            if campaign["status"] != "draft":
                return {"error": f"Campaign is in '{campaign['status']}' state. Only drafts can be launched."}

            # Mark as running
            supabase.table("campaigns").update({
                "status": "running",
                "launched_at": "now()",
            }).eq("id", campaign_id).execute()

            # Enqueue Celery launch task
            from tasks.campaigns import launch_campaign_task
            launch_campaign_task.delay(campaign_id)

            return {"success": True, "message": "Campaign launch successfully scheduled."}

        elif name == "get_campaign_stats":
            # Fetch campaign stats
            campaign_id = args["campaign_id"]
            res = scoped(supabase.table("campaigns").select("*").eq("id", campaign_id)).execute()
            if not res.data:
                return {"error": f"Campaign '{campaign_id}' not found."}

            campaign = res.data[0]
            sent = campaign.get("total_sent", 0)
            delivered = campaign.get("total_delivered", 0)
            opened = campaign.get("total_opened", 0)
            clicked = campaign.get("total_clicked", 0)
            failed = campaign.get("total_failed", 0)

            delivery_rate = round((delivered / sent) * 100, 1) if sent > 0 else 0.0
            open_rate = round((opened / delivered) * 100, 1) if delivered > 0 else 0.0
            click_rate = round((clicked / opened) * 100, 1) if opened > 0 else 0.0

            return {
                "campaign_id": campaign["id"],
                "name": campaign["name"],
                "status": campaign["status"],
                "total_sent": sent,
                "total_delivered": delivered,
                "total_opened": opened,
                "total_clicked": clicked,
                "total_failed": failed,
                "delivery_rate": delivery_rate,
                "open_rate": open_rate,
                "click_rate": click_rate,
            }

        else:
            return {"error": f"Unknown tool name: {name}"}

    except Exception as e:
        logger.error(f"Error executing tool {name} with args {args}: {e}")
        return {"error": f"Internal tool execution error: {e}"}


def _copilot_completion(conversation: list[dict]):
    """
    Call Groq with tools, retrying on the intermittent `tool_use_failed` 400
    that Llama-3.3-70B sometimes returns when it emits malformed tool-call
    syntax. The generation is stochastic, so a retry usually succeeds.
    """
    client = _get_groq_client()
    last_exc = None
    for attempt in range(3):
        try:
            return client.chat.completions.create(
                model=MODEL,
                messages=conversation,
                tools=COPILOT_TOOLS,
                tool_choice="auto",
                temperature=0.1,
                max_tokens=1000,
                stream=False,
            )
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "tool_use_failed" in msg or "Failed to call a function" in msg:
                last_exc = exc
                logger.warning(f"Copilot tool-call malformed (attempt {attempt + 1}/3), retrying.")
                continue
            raise
    raise last_exc  # type: ignore[misc]


async def copilot_chat(messages: list[dict], org_id: str | None = None) -> AsyncGenerator[dict, None]:
    """
    Run the agentic copilot loop and yield SSE-style event dicts.

    Yields dicts: {"type": "text"|"tool_call"|"tool_result"|"done", ...}
    """
    import asyncio
    conversation = [{"role": "system", "content": COPILOT_SYSTEM_PROMPT}] + messages

    while True:
        response = await asyncio.to_thread(_copilot_completion, conversation)

        message = response.choices[0].message

        if message.content:
            yield {"type": "text", "content": message.content}

        if not message.tool_calls:
            yield {"type": "done"}
            break

        for tool_call in message.tool_calls:
            tool_name = tool_call.function.name
            tool_args = json.loads(tool_call.function.arguments)

            yield {"type": "tool_call", "name": tool_name, "args": tool_args}

            # Run the tool and yield result (scoped to the caller's org)
            result = await execute_tool(tool_name, tool_args, org_id)

            yield {"type": "tool_result", "name": tool_name, "result": result}

            conversation.append(message)
            conversation.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                }
            )



def generate_email_subject(campaign_name: str, message_template: str, brand: str = "") -> str:
    """Generate one compelling, non-spammy email subject line for a campaign."""
    prompt = (
        "Write ONE email subject line (under 60 characters) for this campaign. "
        "Make it specific and inviting, not spammy, no ALL CAPS, no excessive punctuation, "
        "at most one emoji. Return ONLY the subject line, no quotes.\n\n"
        f"Brand: {brand or 'the brand'}\nCampaign: {campaign_name}\nMessage gist: {message_template}"
    )
    try:
        resp = _get_groq_client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=40,
        )
        subject = resp.choices[0].message.content.strip().strip('"').splitlines()[0]
        return subject[:120] or campaign_name
    except Exception as e:  # noqa: BLE001
        logger.warning("Subject generation failed: %s", e)
        return campaign_name


# ── 3b. Import Header-Mapping Agent ──────────────────────────────────────────

IMPORT_MAPPING_SYSTEM_PROMPT = """
You are a data-ingestion agent for a CRM. Companies upload CSV files with arbitrary
column names and value formats. Your job: look at the headers and sample rows, then
produce a JSON mapping onto the CRM's canonical schema.

CANONICAL SCHEMAS:

entity_type "customers" fields:
  external_id   — the company's own customer ID (any unique id/code column)
  first_name    — first/given name. If only a single full-name column exists, map it here.
  last_name     — last/family name
  phone         — phone number (any format)
  email         — email address
  city          — city
  channel_pref  — preferred messaging channel; canonical values: whatsapp | sms | email | rcs

entity_type "orders" fields:
  customer_ref      — column identifying the customer (an id, email, or phone)
  customer_ref_type — what customer_ref contains: "external_id" | "email" | "phone"
  order_date        — date/time of the order
  amount            — order value (may contain currency symbols/commas)
  category          — product category
  product_name      — product name/title
  status            — canonical values: completed | returned | cancelled

Respond with ONLY this JSON (no markdown, no explanation):
{
  "entity_type": "customers" | "orders",
  "confidence": 0.0-1.0,
  "mapping": { "<source_header>": "<canonical_field>" },     // omit unmappable headers
  "customer_ref_type": "external_id"|"email"|"phone"|null,   // orders only, else null
  "value_mappings": {                                        // for channel_pref / status columns
    "<canonical_field>": { "<source_value>": "<canonical_value>" }
  },
  "default_country_code": "+91",   // best guess for bare local phone numbers
  "notes": "<one short sentence about anything ambiguous>"
}

Rules:
- Map a full-name column (e.g. "Customer Name") to first_name; the importer splits it.
- Map every source value of a channel-like column to one of: whatsapp, sms, email, rcs
  (e.g. "WA"->"whatsapp", "Text"->"sms", "Mail"->"email"). Same idea for order status.
- If a header has no canonical counterpart, leave it out of mapping.
- Never invent headers that are not in the input.
"""


def map_import_headers(headers: list[str], sample_rows: list[dict], distinct_values: dict[str, list]) -> dict:
    """
    Ask the LLM to classify an uploaded file and map its headers to the
    canonical customers/orders schema. Returns the parsed mapping dict.
    """
    user_prompt = (
        f"Headers: {json.dumps(headers)}\n\n"
        f"First sample rows:\n{json.dumps(sample_rows, default=str, indent=2)}\n\n"
        f"Distinct values of low-cardinality columns:\n{json.dumps(distinct_values, default=str, indent=2)}"
    )
    response = _get_groq_client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": IMPORT_MAPPING_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
        max_tokens=1500,
    )
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    return json.loads(raw)


# ── 4. Customer 360 Summary ───────────────────────────────────────────────────

def generate_customer_summary(customer: dict, orders: list, campaigns: list) -> str:
    """Generate a 2-sentence AI summary for a customer profile."""
    prompt = f"""
You are a CRM analyst. Write a 2-sentence customer summary for a marketer.
Include: purchase pattern, top category, churn risk reason, and ONE suggested action.
Keep it under 60 words. Be specific, not generic.

Customer: {customer['first_name']} {customer.get('last_name', '')}, {customer.get('city', 'unknown city')}
Orders: {len(orders)} total, last order {customer.get('score', {}).get('recency_days', '?')} days ago
Top category: {customer.get('score', {}).get('top_category', '?')}
Last product: {customer.get('score', {}).get('last_product', '?')}
Total spend: ₹{customer.get('score', {}).get('monetary', 0)}
Churn risk: {customer.get('score', {}).get('churn_risk', '?')}
Recent campaigns: {[c['name'] for c in campaigns[-3:]]}
"""
    response = _get_groq_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=150,
    )
    return response.choices[0].message.content.strip()


# ── 5. Post-Campaign Analyst ──────────────────────────────────────────────────

def generate_postmortem(campaign: dict, stats: dict, segment: dict) -> str:
    """Generate a post-campaign analysis paragraph after a campaign completes."""
    prompt = f"""
You are a marketing analyst. Write a post-campaign analysis in 3–4 sentences.
Be specific. Include numbers. End with one concrete recommendation.

Campaign: {campaign['name']}
Segment: {segment['name']} ({stats['total_sent']} customers)
Channel: {campaign['channel']}

Results:
- Delivery rate: {stats['delivery_rate']:.1f}%
- Open rate: {stats['open_rate']:.1f}%
- Click rate: {stats['click_rate']:.1f}%
- Failed: {stats['total_failed']}

Write the post-mortem now. Do not use bullet points. Paragraph form only.
"""
    response = _get_groq_client().chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.4,
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()
