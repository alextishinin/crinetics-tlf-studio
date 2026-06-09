"use client";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertCircle, CheckCircle2, KeyRound, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Header } from "@/components/layout/Header";
import { settings as settingsApi } from "@/lib/api";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["settings"], queryFn: () => settingsApi.get() });

  const [apiKey, setApiKey] = useState("");
  const save = useMutation({
    mutationFn: () => settingsApi.setApiKey(apiKey),
    onSuccess: () => {
      setApiKey("");
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["models"] });
    },
  });

  // Model selection — options come from the Anthropic API (key required).
  const { data: modelsData } = useQuery({
    queryKey: ["models"],
    queryFn: () => settingsApi.getModels(),
    enabled: !!data?.key_present,
  });
  const setModel = useMutation({
    mutationFn: (model: string) => settingsApi.setModel(model),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["settings"] });
      qc.invalidateQueries({ queryKey: ["models"] });
    },
  });

  // Desktop-only update controls (exposed by the Electron preload).
  const [isDesktop, setIsDesktop] = useState(false);
  const [updateMsg, setUpdateMsg] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);
  useEffect(() => {
    setIsDesktop(typeof window !== "undefined" && !!window.tlfStudio?.isDesktop);
  }, []);

  const checkUpdates = async () => {
    if (!window.tlfStudio?.checkForUpdates) return;
    setChecking(true);
    setUpdateMsg(null);
    try {
      const r = await window.tlfStudio.checkForUpdates();
      setUpdateMsg(r.message || r.status);
    } catch (e) {
      setUpdateMsg(e instanceof Error ? e.message : String(e));
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="flex min-h-full flex-col">
      <Header title="Settings" />
      <div className="max-w-2xl space-y-4 p-6">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <KeyRound className="h-4 w-4" /> Anthropic API key
            </CardTitle>
            <CardDescription>
              Required for AI features (protocol / SAP / CRF extraction, table chat, anomaly
              detection). It is stored locally on this machine and never leaves it except to call
              the Anthropic API.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="text-sm">
              Status:{" "}
              {data?.key_present ? (
                <span className="font-medium text-emerald-700">
                  Configured ({data.key_masked})
                </span>
              ) : (
                <span className="font-medium text-amber-700">Not set</span>
              )}
            </div>
            <div className="space-y-1">
              <Label className="text-xs">API key</Label>
              <Input
                type="password"
                placeholder="sk-ant-..."
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
              />
              <p className="text-xs text-slate-500">
                Get a key from{" "}
                <a className="underline" href="https://console.anthropic.com/" target="_blank" rel="noreferrer">
                  console.anthropic.com
                </a>
                . Saving verifies it with a tiny test request.
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Button onClick={() => save.mutate()} disabled={!apiKey.trim() || save.isPending}>
                {save.isPending ? "Saving…" : "Save key"}
              </Button>
              {save.data && (
                <span
                  className={`flex items-center gap-1 text-sm ${
                    save.data.valid ? "text-emerald-700" : "text-amber-700"
                  }`}
                >
                  {save.data.valid ? (
                    <CheckCircle2 className="h-4 w-4" />
                  ) : (
                    <AlertCircle className="h-4 w-4" />
                  )}
                  {save.data.message}
                </span>
              )}
              {save.isError && (
                <span className="flex items-center gap-1 text-sm text-rose-700">
                  <AlertCircle className="h-4 w-4" /> Could not save the key.
                </span>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">AI model</CardTitle>
            <CardDescription>
              Which Claude model the app uses for all AI features. Opus is the most capable but
              costs more; Sonnet is a good balance; Haiku is the fastest and cheapest.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {!data?.key_present ? (
              <p className="text-sm text-amber-700">Add an API key above to choose a model.</p>
            ) : (
              <>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
                  value={data?.model ?? ""}
                  onChange={(e) => setModel.mutate(e.target.value)}
                  disabled={setModel.isPending}
                >
                  {(modelsData?.models ?? []).map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.display_name || m.id}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-slate-500">
                  Current: <span className="font-mono">{data?.model ?? "—"}</span>
                </p>
                {modelsData?.error && <p className="text-xs text-amber-700">{modelsData.error}</p>}
                {setModel.isPending && <p className="text-xs text-slate-500">Saving…</p>}
                {setModel.data?.saved && (
                  <p className="text-xs text-emerald-700">{setModel.data.message}</p>
                )}
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">About</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <div className="flex justify-between border-b pb-1">
              <span className="text-slate-500">Version</span>
              <span className="font-medium">{data?.app_version ?? "—"}</span>
            </div>
            {isDesktop && (
              <div className="flex items-center justify-between gap-3 pt-2">
                <span className="text-slate-500">
                  {updateMsg ?? "Updates install automatically; you can also check now."}
                </span>
                <Button size="sm" variant="outline" onClick={checkUpdates} disabled={checking}>
                  <RefreshCw className="h-4 w-4" /> {checking ? "Checking…" : "Check for updates"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
