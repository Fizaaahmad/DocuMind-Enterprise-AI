"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { fetchHealth, type HealthSnapshot } from "../lib/health";

const services = [
  { key: "api", name: "Backend API", detail: "FastAPI · v1", description: "Application server and HTTP endpoints" },
  { key: "database", name: "PostgreSQL", detail: "Relational database", description: "Persistent storage and database connectivity" },
  { key: "pgvector", name: "pgvector", detail: "Vector extension", description: "Database extension for future semantic search" },
] as const;

export function SystemStatus() {
  const [health, setHealth] = useState<HealthSnapshot | null>(null);
  const [checking, setChecking] = useState(true);
  const [checkedAt, setCheckedAt] = useState<string | null>(null);
  const active = useRef(true);
  const inFlight = useRef(false);

  const refresh = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setChecking(true);
    try {
      const snapshot = await fetchHealth();
      if (active.current) {
        setHealth(snapshot);
        setCheckedAt(new Date().toLocaleTimeString());
      }
    } finally {
      inFlight.current = false;
      if (active.current) setChecking(false);
    }
  }, []);

  useEffect(() => {
    active.current = true;
    void refresh();
    return () => { active.current = false; };
  }, [refresh]);

  const healthy = health && Object.values(health).every((status) => status === "ok");

  return (
    <section aria-labelledby="services-heading" className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-100 p-6 sm:p-8">
        <div>
          <h2 id="services-heading" className="text-lg font-semibold text-slate-950">System services</h2>
          <p role="status" className="mt-1 text-sm text-slate-500">
            {checking ? "Checking services…" : healthy ? "All services operational" : "Some services need attention"}
          </p>
        </div>
        <button onClick={() => void refresh()} disabled={checking} className="rounded-lg border border-slate-200 px-4 py-2 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-indigo-600 disabled:cursor-wait disabled:opacity-50">
          {checking ? "Checking…" : "Refresh status"}
        </button>
      </div>
      <ul className="divide-y divide-slate-100">
        {services.map((service) => {
          const status = health?.[service.key];
          return (
            <li key={service.key} className="flex flex-wrap items-center justify-between gap-4 px-6 py-6 sm:px-8">
              <div>
                <h3 className="font-medium text-slate-900">{service.name}</h3>
                <p className="mt-1 text-sm text-slate-500">{service.description}</p>
                <p className="mt-2 text-xs text-slate-400">{service.detail}</p>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs font-medium ${checking ? "bg-slate-100 text-slate-600" : status === "ok" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-800"}`}>
                {checking ? "Checking" : status === "ok" ? "Operational" : "Unavailable"}
              </span>
            </li>
          );
        })}
      </ul>
      <div className="border-t border-slate-100 px-6 py-4 text-xs text-slate-500 sm:px-8">
        {checkedAt ? `Last checked at ${checkedAt}. Refresh to check again.` : "Connecting to your local development services."}
      </div>
      {!checking && health && !healthy && (
        <p className="border-t border-amber-100 bg-amber-50 px-6 py-4 text-sm text-amber-900 sm:px-8">
          Start the backend and database, then run the database migrations. See the README for setup instructions.
        </p>
      )}
    </section>
  );
}
