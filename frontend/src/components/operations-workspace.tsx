"use client";

import Link from "next/link";
import { BusinessValues, Dialog } from "./ui";
import { WorkspaceShell } from "./workspace-shell";
import { preferredOrganization } from "../lib/organization-preference";
import { useEffect, useState } from "react";
import { api, apiResponse } from "../lib/api";
import type { Organization, User } from "../lib/types";
import { ReviewPanel, type Item } from "./structured-workspace";

type Member = { id: string; name: string };
type RecordItem = Item & {
  document_id: string;
  filename: string;
  template_name: string;
  engine: string;
  effective_validation: string;
  contract_deadline: string | null;
  assignment_due_date: string | null;
  assignee_id: string | null;
  assignee_name: string | null;
  responsible_party: string | null;
  severity: string | null;
  is_current: boolean;
  source_superseded: boolean;
  analysis_superseded: boolean;
  is_done: boolean;
  completed_at: string | null;
  can_assign: boolean;
  can_review: boolean;
};
type Summary = {
  totals: Record<string, number>;
  severity: Record<string, number>;
  inventory: {
    documents: Record<string, number>;
    analyses: Record<string, number>;
  };
  counting: string;
  date_basis: string;
  filters: { as_of: string };
};
type Activity = {
  engine: string;
  id: string;
  item_id: string;
  run_id: string;
  actor_id: string | null;
  actor_name: string | null;
  action: string;
  reason: string;
  created_at: string;
  source_unavailable: boolean;
  before: unknown;
  after: unknown;
};
const labels: Record<string, string> = {
  records: "Analysis records",
  risks: "Risk finding records",
  obligations: "Obligation records",
  pending_reviews: "Pending reviews",
  open_obligations: "Open obligation records",
  overdue_obligations: "Overdue contract deadlines",
  upcoming_obligations: "Upcoming contract deadlines",
  open_assignments: "Open assignments",
  unresolved: "Unresolved validation",
};

export function OperationsWorkspace({
  user,
  initialView,
  initialFocus,
  initialEngine,
}: {
  user?: User;
  initialView?: string;
  initialFocus?: string;
  initialEngine?: string;
} = {}) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organization, setOrganization] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<Organization[]>("/organizations")
      .then((items) => {
        if (active) {
          setOrganizations(items);
          setOrganization(preferredOrganization(items));
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <WorkspaceShell
      user={user}
      active="operations"
      title="Enterprise overview"
      description="Bring evidence, commitments and accountability into one clear view."
      organizationId={organization}
      organizationSelector={
        <label className="mb-6 block max-w-sm text-sm font-medium">
          Organization
          <select
            className="input mt-2"
            value={organization}
            onChange={(e) => setOrganization(e.target.value)}
          >
            {organizations.map((o) => (
              <option key={o.id} value={o.id}>
                {o.name}
              </option>
            ))}
          </select>
        </label>
      }
    >
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}

      {organization ? (
        <Workspace
          key={organization}
          organization={organization}
          initialView={initialView}
          initialFocus={initialFocus}
          initialEngine={initialEngine}
        />
      ) : (
        <p>Create an organization to begin.</p>
      )}
    </WorkspaceShell>
  );
}

function Workspace({
  organization,
  initialView,
  initialFocus,
  initialEngine,
}: {
  organization: string;
  initialView?: string;
  initialFocus?: string;
  initialEngine?: string;
}) {
  const base = `/organizations/${organization}/operations`;
  const startingView = [
    "overview",
    "obligations",
    "reviews",
    "risks",
    "activity",
  ].includes(initialView ?? "")
    ? initialView!
    : "overview";
  const [tab, setTab] = useState(startingView);
  const [filters, setFilters] = useState<Record<string, string>>({
    scope: "current",
    engine: ["deterministic", "openai", "mock", "all"].includes(
      initialEngine ?? "",
    )
      ? initialEngine!
      : "deterministic",
    kind:
      startingView === "reviews"
        ? "review"
        : startingView === "risks"
          ? "risk"
          : startingView === "obligations"
            ? "obligation"
            : "",
    focus:
      initialFocus && Object.hasOwn(labels, initialFocus) ? initialFocus : "",
  });
  const [summary, setSummary] = useState<Summary | null>(null);
  const [items, setItems] = useState<RecordItem[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [documentSearch, setDocumentSearch] = useState("");
  const [documents, setDocuments] = useState<
    { id: string; filename: string }[]
  >([]);
  const [events, setEvents] = useState<Activity[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [activeId, setActiveId] = useState("");
  const [evidence, setEvidence] = useState<Item["evidence"][number] | null>(
    null,
  );
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const params = new URLSearchParams(
    Object.entries(filters).filter(([, value]) => value !== ""),
  ).toString();
  const activeItem = items.find((item) => item.id === activeId);
  const change = (name: string, value: string) => {
    setError("");
    if ((filters[name] ?? "") === value) return;
    setFilters((current) => ({ ...current, [name]: value }));
    setPage(1);
    setEvidence(null);
    setLoading(true);
  };
  function view(next: string) {
    setError("");
    setTab(next);
    setPage(1);
    setActiveId("");
    setEvidence(null);
    setLoading(true);
    setFilters((current) => ({
      ...current,
      kind:
        next === "obligations"
          ? "obligation"
          : next === "reviews"
            ? "review"
            : next === "risks"
              ? "risk"
              : "",
      work_status: "",
      timing: "",
      severity: "",
      unresolved: "",
      focus: "",
    }));
  }
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api<{ items: { id: string; filename: string }[] }>(
        `/organizations/${organization}/documents?page_size=50&q=${encodeURIComponent(documentSearch)}`,
        { signal: controller.signal },
      )
        .then((data) => {
          if (active) setDocuments(data.items);
        })
        .catch((e) => {
          if (active) setError(e.message);
        });
    }, 250);
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [organization, documentSearch]);
  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        if (tab === "activity") {
          const data = await api<{ items: Activity[]; total: number }>(
            `${base}/activity?page=${page}`,
          );
          if (alive) {
            setEvents(data.items);
            setTotal(data.total);
            setLoading(false);
          }
          return;
        }
        const [nextSummary, rows, people] = await Promise.all([
          api<Summary>(`${base}/summary?${params}`),
          api<{ items: RecordItem[]; total: number }>(
            `${base}/items?${params}&page=${page}`,
          ),
          api<Member[]>(`${base}/members`),
        ]);
        if (alive) {
          setSummary(nextSummary);
          setItems(rows.items);
          setTotal(rows.total);
          setMembers(people);
          setLoading(false);
          if (!rows.items.some((item) => item.id === activeId))
            setEvidence(null);
        }
      } catch (e) {
        if (alive) {
          setError((e as Error).message);
          setItems([]);
          setEvents([]);
          setSummary(null);
          setEvidence(null);
          setLoading(false);
        }
      }
    };
    void load();
    const timer = setInterval(() => {
      if (!document.hidden && !busy) void load();
    }, 10000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [base, params, page, tab, refresh, activeId, busy]);
  async function action(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
      setRefresh((n) => n + 1);
    }
  }
  async function download(format: string) {
    await action(async () => {
      const response = await apiResponse(
        `${base}/export?${params}&format=${format}`,
      );
      const url = URL.createObjectURL(await response.blob());
      const a = document.createElement("a");
      a.href = url;
      a.download = `operations.${format}`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }
  return (
    <div className="space-y-6">
      <nav className="flex flex-wrap gap-2" aria-label="Operations views">
        {["overview", "obligations", "reviews", "risks", "activity"].map(
          (key) => (
            <button
              key={key}
              disabled={busy}
              aria-pressed={tab === key}
              className={
                tab === key
                  ? "btn-primary capitalize"
                  : "btn-secondary capitalize"
              }
              onClick={() => {
                if (tab !== key) view(key);
              }}
            >
              {key === "reviews"
                ? "Review queue"
                : key === "risks"
                  ? "Risk register"
                  : key}
            </button>
          ),
        )}
      </nav>
      <p className="review-disclaimer">
        Findings are review candidates, not verified legal or compliance
        conclusions. Counts represent analysis records; independent templates
        may describe overlapping business items. Engines remain separate
        records. Mock records are excluded by default and labeled when included.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      {tab !== "activity" && (
        <section
          className="panel grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4"
          aria-label="Portfolio filters"
        >
          <Select
            label="Record scope"
            value={filters.scope}
            options={[
              ["current", "Current records"],
              ["superseded", "Superseded records"],
              ["all", "Current & historical"],
            ]}
            onChange={(value) => change("scope", value)}
          />
          <Select
            label="Engine"
            value={filters.engine}
            options={[
              ["deterministic", "Deterministic only"],
              ["mock", "DEVELOPMENT MOCK only"],
              ["openai", "OpenAI GPT review candidates"],
              ["all", "All engines (separate records)"],
            ]}
            onChange={(value) => change("engine", value)}
          />
          <label className="text-xs font-medium">
            Find document by filename
            <input
              className="input mt-1"
              value={documentSearch}
              maxLength={180}
              onChange={(e) => {
                setDocumentSearch(e.target.value);
                change("document_id", "");
              }}
              placeholder="Search all organization documents"
            />
          </label>
          <Select
            label="Document"
            value={filters.document_id ?? ""}
            options={[
              ["", "All documents"],
              ...documents.map((d) => [d.id, d.filename]),
            ]}
            onChange={(value) => change("document_id", value)}
          />
          <details className="advanced-filters">
            <summary>Advanced filters & deadlines</summary>
            <div className="advanced-filter-grid">
              <Select
                label="Assignee"
                value={
                  filters.unassigned === "true"
                    ? "unassigned"
                    : (filters.assignee_id ?? "")
                }
                options={[
                  ["", "All assignments"],
                  ["unassigned", "Unassigned"],
                  ...members.map((m) => [m.id, m.name]),
                ]}
                onChange={(value) => {
                  setPage(1);
                  setFilters((current) => ({
                    ...current,
                    assignee_id: value === "unassigned" ? "" : value,
                    unassigned: value === "unassigned" ? "true" : "",
                  }));
                }}
              />
              <Select
                label="Review status"
                value={filters.review_status ?? ""}
                options={[
                  ["", "All review states"],
                  ...["pending", "corrected", "approved", "rejected"].map(
                    (value) => [value, value],
                  ),
                ]}
                onChange={(value) => change("review_status", value)}
              />
              <Select
                label="Obligation status"
                value={filters.obligation_status ?? ""}
                options={[
                  ["", "All lifecycle states"],
                  ...["open", "in_progress", "completed", "dismissed"].map(
                    (value) => [value, value],
                  ),
                ]}
                onChange={(value) => change("obligation_status", value)}
              />
              <Select
                label="Severity"
                value={filters.severity ?? ""}
                options={[
                  ["", "All severities"],
                  ["low", "Low"],
                  ["medium", "Medium"],
                  ["high", "High"],
                ]}
                onChange={(value) => change("severity", value)}
              />
              <label className="text-xs font-medium">
                Responsible party (source text)
                <input
                  className="input mt-1"
                  value={filters.party ?? ""}
                  maxLength={100}
                  onChange={(e) => change("party", e.target.value)}
                />
              </label>
              <Select
                label="Contract deadline timing"
                value={filters.timing ?? ""}
                options={[
                  ["", "All contract deadlines"],
                  ["overdue", "Overdue (open records)"],
                  ["upcoming", "Next 7 days (open records)"],
                  ["unknown", "Unknown deadline"],
                ]}
                onChange={(value) => change("timing", value)}
              />
              <Select
                label="Assignment timing"
                value={filters.assignment_timing ?? ""}
                options={[
                  ["", "All workflow due dates"],
                  ["overdue", "Overdue work"],
                  ["upcoming", "Upcoming work"],
                  ["unknown", "No workflow due date"],
                ]}
                onChange={(value) => change("assignment_timing", value)}
              />
              <label className="text-xs font-medium">
                Contract deadline from
                <input
                  type="date"
                  className="input mt-1"
                  value={filters.deadline_from ?? ""}
                  onChange={(e) => change("deadline_from", e.target.value)}
                />
              </label>
              <label className="text-xs font-medium">
                Contract deadline to
                <input
                  type="date"
                  className="input mt-1"
                  value={filters.deadline_to ?? ""}
                  onChange={(e) => change("deadline_to", e.target.value)}
                />
              </label>
              <label className="text-xs font-medium">
                Deadline reference date (UTC; current state)
                <input
                  type="date"
                  className="input mt-1"
                  value={filters.as_of ?? ""}
                  onChange={(e) => change("as_of", e.target.value)}
                />
              </label>
            </div>
          </details>
          <button
            className="btn-secondary self-end"
            onClick={() => {
              setFilters({
                scope: "current",
                engine: "deterministic",
                kind:
                  tab === "obligations"
                    ? "obligation"
                    : tab === "reviews"
                      ? "review"
                      : tab === "risks"
                        ? "risk"
                        : "",
              });
              setPage(1);
            }}
          >
            Reset filters
          </button>
        </section>
      )}
      {loading && <p role="status">Loading organization records…</p>}
      {tab !== "activity" && summary && (
        <>
          <section>
            <h2 className="mb-3 font-semibold">Filtered record totals</h2>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
              {Object.entries(summary.totals).map(([key, value]) => (
                <button
                  key={key}
                  disabled={Boolean(filters.focus) || value === 0}
                  className="panel p-4 text-left"
                  onClick={() => {
                    setFilters((current) => ({ ...current, focus: key }));
                    setPage(1);
                  }}
                >
                  <p className="text-xs text-slate-500">{labels[key] ?? key}</p>
                  <p className="mt-2 text-2xl font-semibold">{value}</p>
                </button>
              ))}
            </div>
            <p className="mt-3 text-xs text-slate-500">
              Drilldown: {filters.focus || "none"}. Reset filters to return. As
              of {summary.filters.as_of}. {summary.date_basis}. Unreviewed
              obligation candidates remain open lifecycle records.
            </p>
            <div className="mt-3 flex gap-3 text-xs">
              {Object.entries(summary.severity).map(([severity, number]) => (
                <button
                  className="btn-secondary"
                  key={severity}
                  disabled={Boolean(filters.focus)}
                  onClick={() => {
                    setFilters((current) => ({
                      ...current,
                      focus: "risks",
                      severity,
                    }));
                    setPage(1);
                  }}
                >
                  {severity}: {number}
                </button>
              ))}
            </div>
          </section>
          {tab === "overview" && (
            <details className="panel inventory-details">
              <summary className="font-semibold">
                Organization-wide inventory (not item-filtered)
              </summary>
              <div className="mt-3 grid gap-4 text-sm sm:grid-cols-2">
                <div>
                  <Link
                    className="text-indigo-700"
                    href={`/documents?organization=${organization}`}
                  >
                    Documents
                  </Link>
                  <p>
                    {Object.entries(summary.inventory.documents)
                      .map(([state, number]) => `${state}: ${number}`)
                      .join(" · ") || "No documents"}
                  </p>
                </div>
                <div>
                  <Link
                    className="text-indigo-700"
                    href={`/intelligence?organization=${organization}`}
                  >
                    Analyses
                  </Link>
                  <p>
                    {Object.entries(summary.inventory.analyses)
                      .map(([state, number]) => `${state}: ${number}`)
                      .join(" · ") || "No analyses"}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Includes all engines and historical runs. Unavailable
                    analyses retain audit metadata only. Deleted source content
                    is excluded from all portfolio views.
                  </p>
                </div>
              </div>
            </details>
          )}
        </>
      )}
      {tab === "activity" ? (
        <section className="panel p-5">
          <h2 className="font-semibold">Organization workflow activity</h2>
          <p className="mt-2 text-xs text-slate-500">
            Review and assignment events share the original audit history. Item
            filters do not apply to this organization-wide feed.
          </p>
          {events.map((event) => (
            <article
              key={event.id}
              className="border-b border-slate-100 py-4 text-sm"
            >
              <p className="font-medium">
                {event.action} ·{" "}
                {event.actor_name ?? event.actor_id ?? "Former user"}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {event.engine === "mock"
                  ? "DEVELOPMENT MOCK record"
                  : event.engine === "openai"
                    ? "OpenAI GPT review candidate"
                    : "Rule-based record"}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {event.created_at} · {event.reason}
              </p>
              {event.source_unavailable ? (
                <p className="mt-1 text-xs text-amber-800">
                  Source deleted — retained audit metadata only.
                </p>
              ) : (
                <Link
                  className="mt-2 inline-block text-xs text-indigo-700"
                  href={`/intelligence?organization=${organization}&run=${event.run_id}&item=${event.item_id}`}
                >
                  Open original result
                </Link>
              )}
              <details className="mt-2 text-xs">
                <summary>Change metadata</summary>
                <pre className="overflow-auto whitespace-pre-wrap">
                  {JSON.stringify(
                    { before: event.before, after: event.after },
                    null,
                    2,
                  )}
                </pre>
              </details>
            </article>
          ))}
          {!events.length && !loading && (
            <p className="mt-4 text-sm text-slate-500">
              No workflow activity yet.
            </p>
          )}
        </section>
      ) : (
        <section className="panel overflow-hidden">
          <div className="flex flex-wrap justify-between gap-3 p-5">
            <h2 className="font-semibold">{total} matching analysis records</h2>
            <div className="flex gap-2">
              <button
                className="btn-secondary"
                disabled={busy || loading}
                onClick={() => void download("csv")}
              >
                Export filtered CSV
              </button>
              <button
                className="btn-secondary"
                disabled={busy || loading}
                onClick={() => void download("json")}
              >
                Export filtered JSON
              </button>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="bg-slate-50 text-xs text-slate-500">
                <tr>
                  {[
                    "Record & source",
                    "State",
                    "Contract deadline",
                    "Assignment due date",
                    "Assignee",
                    "Actions",
                  ].map((heading) => (
                    <th className="px-5 py-3" key={heading}>
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr className="border-t border-slate-100" key={item.id}>
                    <td className="px-5 py-4">
                      <p className="font-medium record-name">
                        {item.name.replaceAll("_", " ")}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {item.filename} · {item.template_name}
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        {item.engine === "openai"
                          ? "OpenAI GPT · review required"
                          : item.engine === "mock"
                            ? "DEVELOPMENT MOCK"
                            : "Rule-based"}{" "}
                        · {item.kind} ·{" "}
                        {item.is_current
                          ? "Current"
                          : item.source_superseded
                            ? "Source superseded"
                            : "Analysis superseded"}
                      </p>
                      {item.responsible_party && (
                        <p className="mt-1 text-xs">
                          Party candidate: {item.responsible_party}
                        </p>
                      )}
                    </td>
                    <td className="px-5 py-4 text-xs">
                      {item.kind === "obligation"
                        ? item.obligation_status
                        : item.review_status}
                      <br />
                      {item.severity ?? item.effective_validation}
                      {item.completed_at && (
                        <p className="mt-1">Completed: {item.completed_at}</p>
                      )}
                    </td>
                    <td className="px-5 py-4">
                      {item.kind === "obligation"
                        ? (item.contract_deadline ?? "Unknown")
                        : "—"}
                    </td>
                    <td className="px-5 py-4">
                      {item.assignment_due_date ?? "Not set"}
                    </td>
                    <td className="px-5 py-4">
                      {item.assignee_name ?? "Unassigned"}
                    </td>
                    <td className="space-y-2 px-5 py-4">
                      <button
                        className="text-indigo-700"
                        disabled={busy}
                        onClick={() => {
                          setActiveId(activeId === item.id ? "" : item.id);
                          setEvidence(null);
                        }}
                      >
                        Inspect / review
                      </button>
                      <Link
                        className="block text-xs text-indigo-700"
                        href={`/intelligence?organization=${organization}&run=${item.run_id}&item=${item.id}`}
                      >
                        Original analysis
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!items.length && !loading && (
            <p className="p-8 text-sm text-slate-500">
              No records match these filters.
            </p>
          )}
        </section>
      )}
      <div className="flex items-center justify-between text-sm">
        <button
          className="btn-secondary"
          disabled={page <= 1 || busy}
          onClick={() => {
            setPage(page - 1);
            setLoading(true);
          }}
        >
          Previous
        </button>
        <span>Page {page}</span>
        <button
          className="btn-secondary"
          disabled={page * (tab === "activity" ? 30 : 20) >= total || busy}
          onClick={() => {
            setPage(page + 1);
            setLoading(true);
          }}
        >
          Next
        </button>
      </div>
      {activeItem && tab !== "activity" && (
        <section className="panel p-5" aria-label="Record inspection">
          <h2 className="font-semibold">
            {activeItem.name} · {activeItem.filename}
          </h2>
          <p className="mt-2 text-xs text-slate-500">
            Original values and evidence are retained separately from
            corrections. Historical assignments are not migrated onto new
            analysis records.
          </p>
          <BusinessValues value={activeItem.original} />
          {activeItem.corrected && (
            <BusinessValues value={activeItem.corrected} corrected />
          )}

          <div className="my-3 flex flex-wrap gap-2">
            {[
              ...activeItem.evidence,
              ...((activeItem.corrected?.evidence as
                Item["evidence"] | undefined) ?? []),
            ].map((source, index) => (
              <button
                className="btn-secondary"
                key={index}
                onClick={() => setEvidence(source)}
              >
                {source.label} [{source.start}:{source.end}]
              </button>
            ))}
          </div>
          {!activeItem.evidence.length && (
            <p className="text-xs text-amber-800">
              Not-detected findings reference inspected coverage, not a
              fabricated quotation. Open the original analysis to inspect
              coverage.
            </p>
          )}
          {activeItem.can_assign && (
            <AssignmentForm
              key={`${activeItem.id}-${activeItem.version}`}
              item={activeItem}
              members={members}
              busy={busy}
              onSave={(payload) =>
                action(async () => {
                  await api(`${base}/items/${activeItem.id}/assignment`, {
                    method: "PATCH",
                    body: JSON.stringify({
                      version: activeItem.version,
                      ...payload,
                    }),
                  });
                })
              }
            />
          )}
          {activeItem.can_review && (
            <ReviewPanel
              key={`review-${activeItem.id}-${activeItem.version}`}
              item={activeItem}
              busy={busy}
              sourceEvidence={null}
              onReview={(payload) =>
                action(async () => {
                  await api(
                    `/organizations/${organization}/structured/runs/${activeItem.run_id}/items/${activeItem.id}/review`,
                    {
                      method: "POST",
                      body: JSON.stringify({
                        version: activeItem.version,
                        ...payload,
                      }),
                    },
                  );
                })
              }
            />
          )}
        </section>
      )}
      {evidence && (
        <Dialog title="Evidence viewer" onClose={() => setEvidence(null)} wide>
          <section aria-label="Source evidence" className="evidence-view">
            <span className="evidence-label">ORIGINAL SOURCE PASSAGE</span>
            <h3>{evidence.label}</h3>
            <blockquote>{evidence.quote}</blockquote>
            <button className="btn-secondary" onClick={() => setEvidence(null)}>
              Close evidence
            </button>
          </section>
        </Dialog>
      )}
    </div>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[][];
  onChange: (value: string) => void;
}) {
  return (
    <label className="text-xs font-medium">
      {label}
      <select
        className="input mt-1"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        {options.map(([id, name]) => (
          <option key={id} value={id}>
            {name}
          </option>
        ))}
      </select>
    </label>
  );
}

function AssignmentForm({
  item,
  members,
  busy,
  onSave,
}: {
  item: RecordItem;
  members: Member[];
  busy: boolean;
  onSave: (payload: Record<string, unknown>) => Promise<void>;
}) {
  const [assignee, setAssignee] = useState(item.assignee_id ?? "");
  const [due, setDue] = useState(item.assignment_due_date ?? "");
  return (
    <form
      className="mt-5 grid gap-3 rounded-xl border border-slate-200 p-4 sm:grid-cols-3"
      onSubmit={(e) => {
        e.preventDefault();
        void onSave({ assignee_id: assignee || null, due_date: due || null });
      }}
    >
      <Select
        label="Assign to member"
        value={assignee}
        options={[
          ["", "Unassigned"],
          ...members.map((member) => [member.id, member.name]),
        ]}
        onChange={setAssignee}
      />
      <label className="text-xs font-medium">
        Workflow due date (not contract deadline)
        <input
          className="input mt-1"
          type="date"
          value={due}
          onChange={(e) => setDue(e.target.value)}
        />
      </label>
      <button className="btn-primary self-end" disabled={busy}>
        Save assignment
      </button>
    </form>
  );
}
