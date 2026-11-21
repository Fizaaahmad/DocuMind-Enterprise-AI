"use client";

import { createContext, useContext, useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "../lib/api";
import { waitForDemo } from "../lib/demo-wake";

const DemoContext = createContext(false);
export const useDemo = () => useContext(DemoContext);

export function DemoProvider({ enabled, children }: { enabled: boolean; children: React.ReactNode }) {
  return <DemoContext.Provider value={enabled}>{children}</DemoContext.Provider>;
}

export function DemoNotice() {
  const demo = useDemo();
  if (!demo) return null;
  return <aside role="note" className="border-b border-indigo-200 bg-indigo-50 px-5 py-3 text-sm text-indigo-900">
    <strong>Read-only portfolio demo</strong> · Fictional sample data and saved results.
    Uploads, new searches, generation and edits are unavailable. No live AI requests are made.
  </aside>;
}

export function DemoEntry() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <section className="space-y-5">
    <p className="text-sm text-slate-500">Explore fictional documents, saved cited answers, comparisons and review history. This shared workspace is read-only.</p>
    {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
    <button className="btn-primary w-full" disabled={busy} onClick={async () => {
      setBusy(true); setError("");
      try {
        await waitForDemo();
        await api("/demo/enter", { method: "POST" });
        router.replace("/dashboard"); router.refresh();
      } catch (error) {
        setError(error instanceof Error ? error.message : "Demo unavailable; please try later.");
        setBusy(false);
      }
    }}>{busy ? "Checking demo availability…" : "Explore the demo"}</button>
    <p className="text-xs text-slate-500">Free hosting can sleep between visits. Availability checks stop within 25 seconds; retry if the service is still waking.</p>
    <p className="text-xs text-slate-500">No account or password required. Saved mock responses remain labeled as mock previews.</p>
  </section>;
}

export function DemoWake({ next }: { next: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return <main className="mx-auto max-w-lg p-8">
    <h1 className="text-2xl font-semibold">Your demo may be waking</h1>
    <p className="my-5 text-sm text-slate-500">Free hosting can pause between visits. Check availability, then resume your existing authenticated session. No new login or refresh request is retried automatically.</p>
    {error && <p role="alert" className="my-4 text-sm text-red-600">{error}</p>}
    <button className="btn-primary" disabled={busy} onClick={async () => {
      setBusy(true); setError("");
      try { await waitForDemo(); router.replace(next); router.refresh(); }
      catch (error) { setError(error instanceof Error ? error.message : "Please retry later."); setBusy(false); }
    }}>{busy ? "Checking availability…" : "Check and resume"}</button>
    <p className="mt-4 text-xs text-slate-500">Each check is bounded to 25 seconds. Persistent failures may require the project owner to resume the database.</p>
  </main>;
}
