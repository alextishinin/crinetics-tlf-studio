"use client";
import Link from "next/link";
import { KeyRound, Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import ReactMarkdown from "react-markdown";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { AnomalyBadge } from "./AnomalyBadge";
import { ai, settings as settingsApi } from "@/lib/api";
import type { Anomaly } from "@/types/ai";

interface Props {
  studyId: string;
  tableId: string;
  anomalies: Anomaly[];
  onScanAnomalies: () => void;
  isScanning: boolean;
}

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

// Chat history survives navigating away and back within the tab.
const storageKey = (studyId: string, tableId: string) =>
  `tlf-chat:${studyId}:${tableId}`;

function loadHistory(studyId: string, tableId: string): ChatMessage[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = sessionStorage.getItem(storageKey(studyId, tableId));
    return raw ? (JSON.parse(raw) as ChatMessage[]) : [];
  } catch {
    return [];
  }
}

export function AiPanel({ studyId, tableId, anomalies, onScanAnomalies, isScanning }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>(() =>
    loadHistory(studyId, tableId),
  );
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());
  const listRef = useRef<HTMLDivElement>(null);

  const { data: settingsInfo } = useQuery({
    queryKey: ["settings"],
    queryFn: () => settingsApi.get(),
  });
  const keyMissing = settingsInfo ? !settingsInfo.key_present : false;

  // Keep the latest text in view as it streams in.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  // Persist history per table so navigating away doesn't lose the thread.
  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey(studyId, tableId), JSON.stringify(messages));
    } catch {
      /* storage full / unavailable — chat still works, just unpersisted */
    }
  }, [messages, studyId, tableId]);

  const send = async () => {
    if (!input.trim() || streaming || keyMissing) return;
    const next = [...messages, { role: "user" as const, content: input }];
    setMessages(next);
    setInput("");
    setStreaming(true);
    let buffer = "";
    setMessages([...next, { role: "assistant", content: "" }]);
    try {
      await ai.chatStream(studyId, tableId, next, (chunk) => {
        buffer += chunk;
        setMessages([...next, { role: "assistant", content: buffer }]);
      });
    } catch (err) {
      setMessages([
        ...next,
        {
          role: "assistant",
          content: `Sorry — the request failed (${err instanceof Error ? err.message : "network error"}).`,
        },
      ]);
    } finally {
      setStreaming(false);
    }
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <Card className="flex-1 flex flex-col min-h-0">
        <CardHeader>
          <CardTitle className="text-base">AI Assistant</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col gap-2 min-h-0">
          <div ref={listRef} className="flex-1 space-y-3 overflow-auto text-sm">
            {keyMissing && (
              <Link
                href="/settings"
                className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-2 text-xs text-amber-900 hover:bg-amber-100"
              >
                <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                <span>
                  Add your Anthropic API key in Settings to enable the assistant and
                  anomaly detection.
                </span>
              </Link>
            )}
            {messages.length === 0 && !keyMissing && (
              <p className="text-xs text-slate-500">
                Ask anything about this table or the underlying patient-level data — n counts,
                footnote rules, CDISC standards, or queries like &ldquo;list the subject IDs who
                discontinued due to an AE.&rdquo;
              </p>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={
                  m.role === "user"
                    ? "ml-6 rounded-lg rounded-br-sm bg-crinetics-tealLight px-3 py-2"
                    : "mr-2 rounded-lg rounded-bl-sm border bg-white px-3 py-2"
                }
              >
                {m.role === "assistant" ? (
                  <div className="prose-sm max-w-none [&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1 [&_ol]:list-decimal [&_ol]:pl-4 [&_p]:my-1 [&_ul]:list-disc [&_ul]:pl-4">
                    {m.content ? (
                      <ReactMarkdown>{m.content}</ReactMarkdown>
                    ) : streaming && i === messages.length - 1 ? (
                      <span className="text-slate-400">Thinking…</span>
                    ) : null}
                  </div>
                ) : (
                  <span className="whitespace-pre-wrap">{m.content}</span>
                )}
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Textarea
              rows={2}
              placeholder={keyMissing ? "Set your API key in Settings first" : "Why is n lower at Week 16?"}
              value={input}
              disabled={keyMissing}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <Button
              onClick={send}
              disabled={streaming || !input.trim() || keyMissing}
              aria-label="Send message"
            >
              <Send className="h-4 w-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center justify-between">
            Anomaly Detection
            <Button size="sm" variant="outline" onClick={onScanAnomalies} disabled={isScanning}>
              {isScanning ? "Scanning…" : "Scan"}
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          {anomalies.length === 0 && !isScanning && (
            <p className="text-xs text-slate-500">No anomalies detected yet. Generate the preview, then scan.</p>
          )}
          {anomalies.map((a, i) => {
            if (dismissed.has(i)) return null;
            return (
              <AnomalyBadge
                key={i}
                anomaly={a}
                onDismiss={() => setDismissed((s) => new Set(s).add(i))}
              />
            );
          })}
        </CardContent>
      </Card>
    </div>
  );
}
