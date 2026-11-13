"use client";

import { useState } from "react";
import { apiFetch } from "@/lib/api";
import type { ChatResponse } from "@/lib/types";
import { Icon } from "./Icon";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  guardrail?: boolean;
}

const INITIAL_SUGGESTIONS = [
  "How do I report an overflowing bin?",
  "Show live complaint summary",
  "How does verification work?",
];

export function CivicChatbot() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>(INITIAL_SUGGESTIONS);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      text: "Ask me about CivicOps waste complaints, reporting overflowing bins or missed collection, tracking IDs (INC-/RPT-), or verification status.",
    },
  ]);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      role: "user",
      text: trimmed,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setSending(true);

    try {
      const res = await apiFetch<ChatResponse>("/chat", {
        method: "POST",
        body: JSON.stringify({
          message: trimmed,
          history: messages.slice(-6).map((m) => ({
            role: m.role,
            content: m.text,
          })),
        }),
      });
      setMessages((prev) => [
        ...prev,
        {
          id: `a-${Date.now()}`,
          role: "assistant",
          text: res.reply,
          guardrail: res.guardrail_triggered,
        },
      ]);
      if (res.suggestions.length > 0) {
        setSuggestions(res.suggestions);
      }
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: `e-${Date.now()}`,
          role: "assistant",
          text:
            err instanceof Error
              ? err.message
              : "Assistant is temporarily unavailable.",
        },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="chatbot-root">
      {open ? (
        <section
          className="chatbot-panel"
          aria-label="CivicOps Waste Assistant"
        >
          <div className="chatbot-head">
            <div>
              <strong>CivicOps Assistant</strong>
              <small>Waste complaints &amp; tracking · Guardrailed</small>
            </div>
            <button
              type="button"
              className="chatbot-close"
              onClick={() => setOpen(false)}
              aria-label="Close assistant"
            >
              <Icon name="close" size={18} />
            </button>
          </div>

          <div className="chatbot-messages" role="log" aria-live="polite">
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`chatbot-bubble ${
                  msg.role === "user" ? "is-user" : "is-assistant"
                }${msg.guardrail ? " is-guardrail" : ""}`}
              >
                {msg.guardrail ? (
                  <span className="chatbot-guardrail-tag">Scope guardrail</span>
                ) : null}
                <p>{msg.text}</p>
              </div>
            ))}
          </div>

          <div className="chatbot-suggestions">
            {suggestions.map((item) => (
              <button
                key={item}
                type="button"
                className="chatbot-chip"
                onClick={() => void sendMessage(item)}
                disabled={sending}
              >
                {item}
              </button>
            ))}
          </div>

          <form
            className="chatbot-form"
            onSubmit={(e) => {
              e.preventDefault();
              void sendMessage(input);
            }}
          >
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about complaints, wards, or INC-2026-..."
              maxLength={600}
              aria-label="Ask CivicOps Assistant"
            />
            <button
              type="submit"
              className="button button-primary button-small"
              disabled={sending || !input.trim()}
            >
              {sending ? "..." : "Send"}
            </button>
          </form>
        </section>
      ) : null}

      <button
        type="button"
        className="chatbot-toggle"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
      >
        <Icon name="spark" size={18} />
        <span>{open ? "Hide assistant" : "CivicOps Help"}</span>
      </button>
    </div>
  );
}

