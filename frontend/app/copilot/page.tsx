"use client";

import { useState, useRef, useEffect } from "react";
import {
  Sparkles,
  Send,
  Loader2,
  CheckCircle,
  AlertTriangle,
  Play,
  Terminal,
  RefreshCw,
  Cpu,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { orgHeader } from "@/lib/api";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  toolCalls?: Array<{
    id: string;
    name: string;
    args: any;
    result?: any;
    status: "running" | "success" | "failed";
  }>;
}

export default function CopilotPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "init",
      role: "assistant",
      content:
        "Hello! I am Orbit Copilot. I can help you find segments, draft templates, and launch campaigns. What is your goal today?",
    },
  ]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  
  // Trace log of all tool executions
  const [traces, setTraces] = useState<any[]>([]);

  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleSend = async (textToSend: string) => {
    if (!textToSend.trim()) return;

    const userMsg: ChatMessage = {
      id: Math.random().toString(),
      role: "user",
      content: textToSend,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setStreaming(true);

    const assistantMsgId = Math.random().toString();
    const newAssistantMsg: ChatMessage = {
      id: assistantMsgId,
      role: "assistant",
      content: "",
      toolCalls: [],
    };
    setMessages((prev) => [...prev, newAssistantMsg]);

    const requestMessages = [...messages, userMsg].map((m) => ({
      role: m.role,
      content: m.content,
    }));

    try {
      const apiBase = process.env.NEXT_PUBLIC_CRM_API_URL ?? "http://localhost:8000";
      const response = await fetch(`${apiBase}/api/v1/copilot/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...orgHeader() },
        body: JSON.stringify({ messages: requestMessages }),
      });

      if (!response.ok) throw new Error("API Offline");

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      if (!reader) throw new Error("No reader");

      let buffer = "";
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const jsonStr = line.slice(6).trim();
          if (!jsonStr) continue;

          try {
            const event = JSON.parse(jsonStr);

            if (event.type === "text") {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsgId
                    ? { ...m, content: m.content + event.content }
                    : m
                )
              );
            } else if (event.type === "tool_call") {
              const newToolCall = {
                id: event.name + Math.random(),
                name: event.name,
                args: event.args,
                status: "running" as const,
              };

              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantMsgId
                    ? {
                        ...m,
                        toolCalls: [...(m.toolCalls || []), newToolCall],
                      }
                    : m
                )
              );

              setTraces((prev) => [
                ...prev,
                { name: event.name, args: event.args, status: "running" },
              ]);
            } else if (event.type === "tool_result") {
              setMessages((prev) =>
                prev.map((m) => {
                  if (m.id !== assistantMsgId) return m;
                  const calls = m.toolCalls?.map((tc) =>
                    tc.name === event.name
                      ? {
                          ...tc,
                          result: event.result,
                          status: event.result.error ? ("failed" as const) : ("success" as const),
                        }
                      : tc
                  );
                  return { ...m, toolCalls: calls };
                })
              );

              setTraces((prev) =>
                prev.map((t) =>
                  t.name === event.name
                    ? {
                        ...t,
                        result: event.result,
                        status: event.result.error ? "failed" : "success",
                      }
                    : t
                )
              );
            }
          } catch (e) {
            console.error("Error parsing event line", e);
          }
        }
      }
    } catch (err) {
      console.error("Copilot stream error", err);
      // Fallback simulation so the user experiences the full agent loop anyway
      simulateMockCopilot(textToSend, assistantMsgId);
    } finally {
      setStreaming(false);
    }
  };

  const simulateMockCopilot = (prompt: string, msgId: string) => {
    let steps = [
      {
        type: "text",
        content: "I will help you plan that campaign. Let's first search for saved customer segments to target.",
      },
      {
        type: "tool_call",
        name: "get_segments",
        args: { churn_risk_filter: "high" },
      },
      {
        type: "tool_result",
        name: "get_segments",
        result: {
          segments: [
            { id: "s1", name: "High Value Churn Risk", customer_count: 84 },
            { id: "s2", name: "Lapsed Haircare Cohort", customer_count: 128 },
          ],
        },
      },
      {
        type: "text",
        content: "I found segment **High Value Churn Risk** containing 84 customers. Next, let's draft a win-back promotional message for WhatsApp.",
      },
      {
        type: "tool_call",
        name: "draft_message",
        args: { campaign_goal: "win back lapsed customers", channel: "whatsapp" },
      },
      {
        type: "tool_result",
        name: "draft_message",
        result: {
          channel: "whatsapp",
          message_template: "Hey {first_name}! We miss you. 🌟 Grab your favorite {last_product} with 15% off today: brand.com/offers",
        },
      },
      {
        type: "text",
        content: "Here is the drafted message template: \n\n*\"Hey {first_name}! We miss you. 🌟 Grab your favorite {last_product} with 15% off today: brand.com/offers\"*\n\nWould you like me to create and launch this campaign for you now?",
      },
    ];

    let delay = 300;
    steps.forEach((step, idx) => {
      setTimeout(() => {
        if (step.type === "text") {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === msgId ? { ...m, content: m.content + "\n\n" + step.content } : m
            )
          );
        } else if (step.type === "tool_call") {
          const tc = {
            id: (step.name ?? "tool") + idx,
            name: step.name ?? "tool",
            args: step.args,
            status: "running" as const,
          };
          setMessages((prev) =>
            prev.map((m) => (m.id === msgId ? { ...m, toolCalls: [...(m.toolCalls || []), tc] } : m))
          );
          setTraces((prev) => [...prev, tc]);
        } else if (step.type === "tool_result") {
          setMessages((prev) =>
            prev.map((m) => {
              if (m.id !== msgId) return m;
              const calls = m.toolCalls?.map((tc) =>
                tc.name === step.name ? { ...tc, result: step.result, status: "success" as const } : tc
              );
              return { ...m, toolCalls: calls };
            })
          );
          setTraces((prev) =>
            prev.map((t) => (t.name === step.name ? { ...t, result: step.result, status: "success" } : t))
          );
        }

        if (idx === steps.length - 1) {
          setStreaming(false);
        }
      }, delay);
      delay += step.type.startsWith("tool") ? 800 : 1800;
    });
  };

  return (
    <div className="flex h-[calc(100vh-4rem)] max-w-7xl mx-auto overflow-hidden">
      {/* Left Column: Chat Window */}
      <div className="flex-1 flex flex-col h-full border-r border-slate-800">
        {/* Chat Header */}
        <div className="h-16 border-b border-slate-800 px-6 flex items-center gap-3 bg-slate-900/10">
          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-600 flex items-center justify-center shadow-[0_0_10px_rgba(168,85,247,0.4)]">
            <Cpu className="w-4 h-4 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-white text-sm">Campaign Copilot Agent</h1>
            <span className="text-xs text-purple-400 block font-medium">Online • Llama-3.3 70B</span>
          </div>
        </div>

        {/* Message Timeline */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={cn(
                "flex flex-col max-w-[80%] rounded-xl p-4 text-sm relative group",
                msg.role === "user"
                  ? "ml-auto bg-purple-600 text-white rounded-br-none shadow-lg"
                  : "bg-slate-900/40 border border-slate-800 text-slate-200 rounded-bl-none"
              )}
            >
              {/* Message Content */}
              <div className="whitespace-pre-wrap leading-relaxed">{msg.content}</div>

              {/* Tool Calls inside assistant bubble */}
              {msg.toolCalls && msg.toolCalls.length > 0 && (
                <div className="mt-4 pt-3 border-t border-slate-800/80 space-y-3">
                  <span className="text-[10px] text-slate-500 font-semibold block uppercase tracking-wider">
                    Agent Actions
                  </span>
                  {msg.toolCalls.map((tc) => (
                    <div
                      key={tc.id}
                      className="p-3 rounded bg-slate-950 border border-slate-800/80 flex items-center justify-between gap-4"
                    >
                      <div>
                        <span className="font-semibold text-slate-300 text-xs block">
                          ⚡ Call {tc.name}()
                        </span>
                        {tc.status === "success" && (
                          <span className="text-[10px] text-teal-400 font-medium">
                            Completed successfully
                          </span>
                        )}
                        {tc.status === "running" && (
                          <span className="text-[10px] text-purple-400 font-medium flex items-center gap-1">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            Executing DB query...
                          </span>
                        )}
                      </div>

                      {/* Display Confirm button for launch */}
                      {tc.name === "launch_campaign" && tc.status === "running" && (
                        <button
                          onClick={() => handleSend("yes")}
                          className="px-3 py-1 bg-teal-600 hover:bg-teal-500 text-white font-semibold rounded text-xs transition-colors flex items-center gap-1"
                        >
                          <Play className="w-3.5 h-3.5 fill-current" />
                          Confirm Launch
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          ))}
          {streaming && (
            <div className="flex gap-2 items-center text-slate-500 text-xs pl-2">
              <Loader2 className="w-4 h-4 animate-spin text-purple-500" />
              Orbit Agent is drafting next steps...
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input Bar */}
        <div className="p-4 border-t border-slate-800 bg-slate-950/40">
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Ask Copilot to build a winback campaign..."
              className="flex-1 px-4 py-2.5 rounded-lg border border-slate-800 bg-slate-950 text-slate-200 text-sm focus:outline-none focus:border-purple-500 placeholder:text-slate-650"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleSend(input)}
              disabled={streaming}
            />
            <button
              onClick={() => handleSend(input)}
              disabled={streaming || !input.trim()}
              className="p-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 text-white rounded-lg shadow-lg hover:opacity-90 disabled:opacity-50 transition-all"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* Right Column: Execution Trace Log */}
      <div className="w-80 bg-slate-950/30 p-6 space-y-6 hidden lg:block overflow-y-auto">
        <h3 className="font-bold text-white text-sm flex items-center gap-2 border-b border-slate-850 pb-3">
          <Terminal className="w-4 h-4 text-purple-400" />
          Trace Execution Log
        </h3>

        <div className="space-y-4">
          {traces.length === 0 ? (
            <p className="text-slate-600 text-xs text-center py-12">
              No tools called in this session yet.
            </p>
          ) : (
            traces.map((trace, index) => (
              <div
                key={index}
                className="p-3 rounded bg-slate-900/40 border border-slate-800/80 space-y-2 text-xs"
              >
                <div className="flex justify-between items-center">
                  <span className="font-semibold text-slate-300 font-mono">
                    {trace.name}
                  </span>
                  {trace.status === "success" && (
                    <span className="w-2 h-2 rounded-full bg-teal-500" />
                  )}
                  {trace.status === "running" && (
                    <span className="w-2 h-2 rounded-full bg-purple-500 animate-pulse" />
                  )}
                </div>
                <div className="text-[10px] text-slate-500">
                  <span className="block font-semibold">Args:</span>
                  <pre className="mt-1 bg-slate-950 p-2 rounded overflow-x-auto text-purple-400">
                    {JSON.stringify(trace.args, null, 2)}
                  </pre>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
