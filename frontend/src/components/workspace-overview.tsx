"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "../lib/api";
import type { DocumentList } from "../lib/documents";
import { EmptyState, Icon, Skeleton, StatusBadge, type IconName } from "./ui";

type Summary = {
  totals: Record<string, number>;
  inventory: {
    documents: Record<string, number>;
    analyses: Record<string, number>;
  };
  counting: string;
};
type Activity = {
  id: string;
  action: string;
  actor_name: string | null;
  created_at: string;
  source_unavailable: boolean;
};

export function WorkspaceOverview({ organization }: { organization: string }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [documents, setDocuments] = useState<DocumentList | null>(null);
  const [activity, setActivity] = useState<Activity[] | null>(null);
  const [completed, setCompleted] = useState({
    documents: false,
    activity: false,
  });
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const options = { signal: controller.signal };
    const report = () => {
      if (active)
        setError(
          "Some overview information is unavailable. Open the relevant workspace to retry.",
        );
    };
    void api<Summary>(
      `/organizations/${organization}/operations/summary?engine=all`,
      options,
    )
      .then((data) => {
        if (active && data.inventory) setSummary(data);
      })
      .catch(report);
    void api<DocumentList>(
      `/organizations/${organization}/documents?page_size=5&sort=newest`,
      options,
    )
      .then((data) => {
        if (active && data.items) setDocuments(data);
      })
      .catch(report)
      .finally(() => {
        if (active)
          setCompleted((current) => ({ ...current, documents: true }));
      });
    void api<{ items: Activity[] }>(
      `/organizations/${organization}/operations/activity?page_size=5`,
      options,
    )
      .then((data) => {
        if (active && data.items) setActivity(data.items.slice(0, 5));
      })
      .catch(report)
      .finally(() => {
        if (active) setCompleted((current) => ({ ...current, activity: true }));
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, [organization]);
  const inventory = summary?.inventory?.documents;
  const count = inventory
    ? Object.values(inventory).reduce((a, b) => a + b, 0)
    : null;
  const metrics: {
    label: string;
    value: number | null;
    detail: string;
    icon: IconName;
    href: string;
    tone: string;
  }[] = [
    {
      label: "Documents",
      value: count,
      detail: "In your organization",
      icon: "documents",
      href: "/documents",
      tone: "violet",
    },
    {
      label: "Pending reviews",
      value: summary?.totals?.pending_reviews ?? null,
      detail: "Ready for a human decision",
      icon: "intelligence",
      href: "/operations?view=reviews&focus=pending_reviews&engine=all",
      tone: "blue",
    },
    {
      label: "Open obligations",
      value: summary?.totals?.open_obligations ?? null,
      detail: "Commitments to follow through",
      icon: "operations",
      href: "/operations?view=obligations&focus=open_obligations&engine=all",
      tone: "green",
    },
    {
      label: "Overdue deadlines",
      value: summary?.totals?.overdue_obligations ?? null,
      detail: "Contractual dates needing attention",
      icon: "clock",
      href: "/operations?view=obligations&focus=overdue_obligations&engine=all",
      tone: "amber",
    },
  ];
  const processing = inventory
    ? (inventory.pending ?? 0) + (inventory.processing ?? 0)
    : null;
  return (
    <div className="overview-space">
      <div className="metrics-grid">
        {metrics.map((metric) => (
          <Link
            key={metric.label}
            href={`${metric.href}${metric.href.includes("?") ? "&" : "?"}organization=${organization}`}
            className={`metric-card metric-${metric.tone}`}
          >
            <div className="metric-top">
              <span>{metric.label}</span>
              <span className="metric-icon">
                <Icon name={metric.icon} />
              </span>
            </div>
            <p className="metric-number">
              {metric.value === null ? "—" : metric.value.toLocaleString()}
            </p>
            <div className="metric-bottom">
              <span>{metric.detail}</span>
              <Icon name="arrow" />
            </div>
          </Link>
        ))}
      </div>
      {error && (
        <p role="alert" className="error-box">
          {error}
        </p>
      )}
      <div className="overview-main-grid">
        <section className="panel">
          <div className="module-heading">
            <div>
              <h2>Recent documents</h2>
              <p>Your latest source files, ready for the next step</p>
            </div>
            <Link
              className="text-xs font-semibold text-indigo-600"
              href={`/documents?organization=${organization}`}
            >
              View library <span aria-hidden="true">↗</span>
            </Link>
          </div>
          {documents ? (
            documents.items.length ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  <thead>
                    <tr>
                      <th className="px-5 py-3">Name</th>
                      <th className="px-4 py-3">Processing</th>
                      <th className="px-4 py-3">Sources</th>
                    </tr>
                  </thead>
                  <tbody>
                    {documents.items.map((document) => (
                      <tr
                        key={document.id}
                        className="border-t border-slate-100"
                      >
                        <td className="px-5 py-3">
                          <Link
                            href={`/documents?organization=${organization}&document=${document.id}`}
                            className="flex min-w-0 items-center gap-3"
                          >
                            <span className="file-tile">
                              {document.format.toUpperCase()}
                            </span>
                            <span className="min-w-0">
                              <strong className="block max-w-72 truncate text-xs font-semibold">
                                {document.filename}
                              </strong>
                              <span className="text-[10px] text-slate-500">
                                {document.created_at
                                  ? new Date(
                                      document.created_at,
                                    ).toLocaleDateString(undefined, {
                                      month: "short",
                                      day: "numeric",
                                    })
                                  : document.format.toUpperCase()}
                              </span>
                            </span>
                          </Link>
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge value={document.status} />
                        </td>
                        <td className="px-4 py-3 text-xs text-slate-500">
                          {document.section_count}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState title="Build your knowledge library">
                <p>
                  Upload a document to start extracting evidence and insights.
                </p>
                <Link
                  className="btn-primary mt-4"
                  href={`/documents?organization=${organization}`}
                >
                  Upload your first document
                </Link>
              </EmptyState>
            )
          ) : completed.documents ? (
            <p className="p-5 text-xs text-slate-500">
              Recent documents are unavailable. Open the library to retry.
            </p>
          ) : (
            <Skeleton rows={5} />
          )}
        </section>
        <section className="assistant-feature">
          <span className="feature-orbit" aria-hidden="true" />
          <span className="feature-icon">
            <Icon name="assistant" />
          </span>
          <p className="section-label">YOUR KNOWLEDGE, CONNECTED</p>
          <h2>
            Answers you can
            <br />
            trace to the source.
          </h2>
          <p>
            Ask a question across your documents. Inspect the passages behind
            each answer and move forward with context.
          </p>
          <Link
            className="btn-primary"
            href={`/assistant?organization=${organization}`}
          >
            Open Knowledge Assistant <Icon name="arrow" />
          </Link>
          <span className="feature-caption">
            <Icon name="quote" /> Evidence citations included
          </span>
        </section>
      </div>
      <div className="overview-bottom-grid">
        <section className="panel">
          <div className="module-heading">
            <div>
              <h2>Processing activity</h2>
              <p>Current document pipeline</p>
            </div>
            <Icon name="activity" />
          </div>
          <div className="pipeline-stats">
            <div>
              <span className="pipeline-dot bg-indigo-500" />
              <strong>{processing ?? "—"}</strong>
              <span>Pending & processing</span>
            </div>
            <div>
              <span className="pipeline-dot bg-emerald-500" />
              <strong>{inventory?.completed ?? (inventory ? 0 : "—")}</strong>
              <span>Completed</span>
            </div>
            <div>
              <span className="pipeline-dot bg-rose-400" />
              <strong>{inventory?.failed ?? (inventory ? 0 : "—")}</strong>
              <span>Needs attention</span>
            </div>
          </div>
        </section>
        <section className="panel">
          <div className="module-heading">
            <div>
              <h2>Recent workflow activity</h2>
              <p>Reviews, assignments and status changes</p>
            </div>
            <Link
              href={`/operations?organization=${organization}`}
              className="text-xs text-indigo-600"
            >
              Operations ↗
            </Link>
          </div>
          {activity ? (
            activity.length ? (
              <ul className="activity-preview">
                {activity.map((event) => (
                  <li key={event.id}>
                    <span className="activity-mark">
                      <Icon name="check" />
                    </span>
                    <div>
                      <strong>{event.action.replaceAll("_", " ")}</strong>
                      <p>
                        {event.actor_name ?? "Former member"}
                        {event.source_unavailable
                          ? " · Source unavailable"
                          : ""}
                      </p>
                    </div>
                    <time dateTime={event.created_at}>
                      {new Date(event.created_at).toLocaleDateString(
                        undefined,
                        { month: "short", day: "numeric" },
                      )}
                    </time>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-5 py-6 text-xs text-slate-500">
                Your team’s review and assignment activity will appear here.
              </p>
            )
          ) : completed.activity ? (
            <p className="p-5 text-xs text-slate-500">
              Workflow activity is unavailable. Open Operations to retry.
            </p>
          ) : (
            <Skeleton rows={2} />
          )}
        </section>
      </div>
      <p className="overview-counting" title={summary?.counting}>
        Organization-wide document inventory. Analysis counts show current
        records across all engines, including development mock runs; independent
        templates and engines may overlap.
      </p>
    </div>
  );
}
