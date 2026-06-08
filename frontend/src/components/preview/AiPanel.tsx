"use client";
import { Send } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { AnomalyBadge } from "./AnomalyBadge";
import { ai } from "@/lib/api";
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

export function AiPanel({ studyId, tableId, anomalies, onScanAnomalies, isScanning }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [dismissed, setDismissed] = useState<Set<number>>(new Set());
  const listRef = useRef<HTMLDivElement>(null);

  // Keep the latest text in view as it streams in.
  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const send = async () => {
    if (!input.trim() || streaming) return;
    const next = [...messages, { role: "user" as const, content: input }];
    setMessages(next);
    setInput("");
    setStreaming(true);
    let buffer = "";
    setMessages([...next, { role: "assistant", content: "" }]);
    await ai.chatStream(studyId, tableId, next, (chunk) => {
      buffer += chunk;
      setMessages([...next, { role: "assistant", content: buffer }]);
    });
    setStreaming(false);
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <Card className="flex-1 flex flex-col min-h-0">
        <CardHeader>
          <CardTitle className="text-base">AI Assistant</CardTitle>
        </CardHeader>
        <CardContent className="flex-1 flex flex-col gap-2 min-h-0">
          <div ref={listRef} className="flex-1 space-y-3 overflow-auto text-sm">
            {messages.length === 0 && (
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
                    ? "rounded-md bg-slate-100 p-2"
                    : "rounded-md bg-blue-50 p-2 whitespace-pre-wrap"
                }
              >
                <div className="text-xs font-medium text-slate-500 mb-1">{m.role}</div>
                {m.content || (streaming && i === messages.length - 1 ? "…" : "")}
              </div>
            ))}
          </div>
          <div className="flex gap-2">
            <Textarea
              rows={2}
              placeholder="Why is n lower at Week 16?"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  send();
                }
              }}
            />
            <Button onClick={send} disabled={streaming || !input.trim()}>
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
