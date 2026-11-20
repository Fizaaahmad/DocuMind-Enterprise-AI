"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, apiResponse } from "../lib/api";
import type { Organization } from "../lib/types";

type Document = { id: string; filename: string; status: string };
type Revision = { id: string; created_at: string; current: boolean };
type Template = {
  id: string;
  name: string;
  definition: Record<string, unknown>;
};
type Run = {
  id: string;
  mode: string;
  engine: string;
  state: string;
  error: string | null;
  created_at: string;
  left_revision_id: string;
  right_revision_id: string | null;
  coverage: Record<string, unknown>;
};
type Evidence = {
  section_id: string;
  revision_id: string;
  label: string;
  page_number: number | null;
  start: number;
  end: number;
  quote: string;
};
export type Item = {
  id: string;
  run_id: string;
  kind: string;
  name: string;
  original: Record<string, unknown>;
  corrected: Record<string, unknown> | null;
  evidence: Evidence[];
  validation: string;
  review_status: string;
  obligation_status: string;
  version: number;
  can_review?: boolean;
};
type Review = {
  id: string;
  item_id: string;
  action: string;
  reason: string;
  created_at: string;
  actor_id: string;
};
type Detail = {
  run: Run;
  usage?: {
    model: string;
    input_tokens: number | null;
    output_tokens: number | null;
    estimated_cost_usd: string | null;
  } | null;
  items: Item[];
  reviews: Review[];
  superseded: boolean;
  can_manage: boolean;
  sources: { revision_id: string; filename: string }[];
};
type Section = {
  id: string;
  label: string;
  text: string;
  page_number: number | null;
};

const example = {
  name: "Contract facts v1",
  fields: [
    {
      name: "party",
      type: "text",
      label: "Party",
      description: "Explicit party label",
      required: true,
    },
    {
      name: "effective_date",
      type: "date",
      label: "Effective Date",
      required: true,
    },
    { name: "fee", type: "money", label: "Fee", required: false },
  ],
  rules: [
    {
      name: "Unlimited liability term",
      type: "contains",
      term: "unlimited liability",
      severity: "high",
    },
    {
      name: "Termination term not detected",
      type: "missing",
      term: "termination",
      severity: "medium",
    },
    {
      name: "Fee above 10000",
      type: "threshold",
      field: "fee",
      threshold: 10000,
      severity: "medium",
    },
  ],
  obligations: true,
};
const pretty = (value: unknown) => JSON.stringify(value, null, 2);

export function StructuredWorkspace({
  initialOrganization = "",
  initialRun = "",
  initialItem = "",
}: {
  initialOrganization?: string;
  initialRun?: string;
  initialItem?: string;
} = {}) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selected, setSelected] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<Organization[]>("/organizations")
      .then((items) => {
        if (active) {
          setOrganizations(items);
          setSelected(
            items.find((item) => item.id === initialOrganization)?.id ??
              items[0]?.id ??
              "",
          );
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [initialOrganization]);
  return (
    <main className="mx-auto max-w-7xl p-4 sm:p-8">
      <header className="mb-7 flex flex-wrap justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-indigo-600">
            DOCUMIND / STRUCTURED INTELLIGENCE
          </p>
          <h1 className="mt-2 text-3xl font-semibold">Document intelligence</h1>
          <p className="mt-2 text-slate-500">
            Turn source passages into traceable, reviewable information.
          </p>
        </div>
        <nav className="flex gap-4 text-sm text-indigo-700">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/documents">Documents</Link>
          <Link href="/assistant">Assistant</Link>
        </nav>
      </header>
      <p className="mb-6 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
        Deterministic extraction and rule-based review candidates. Mock runs are
        development simulations. Findings are not legal or compliance
        conclusions.
      </p>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
      <label className="mb-6 block max-w-sm text-sm font-medium">
        Organization
        <select
          className="input mt-2"
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
        >
          {organizations.map((o) => (
            <option key={o.id} value={o.id}>
              {o.name}
            </option>
          ))}
        </select>
      </label>
      {selected ? (
        <Workspace
          key={selected}
          organization={selected}
          initialRun={
            !initialOrganization || selected === initialOrganization
              ? initialRun
              : ""
          }
          initialItem={
            !initialOrganization || selected === initialOrganization
              ? initialItem
              : ""
          }
          admin={organizations.find((o) => o.id === selected)?.role === "admin"}
        />
      ) : (
        <p>Create an organization to begin.</p>
      )}
    </main>
  );
}

function Workspace({
  organization,
  admin,
  initialRun,
  initialItem,
}: {
  organization: string;
  admin: boolean;
  initialRun: string;
  initialItem: string;
}) {
  const base = `/organizations/${organization}/structured`;
  const [documents, setDocuments] = useState<Document[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [left, setLeft] = useState("");
  const [right, setRight] = useState("");
  const [leftRevision, setLeftRevision] = useState("");
  const [rightRevision, setRightRevision] = useState("");
  const [template, setTemplate] = useState("");
  const [mode, setMode] = useState("extract");
  const [engine, setEngine] = useState("deterministic");
  const [selected, setSelected] = useState(initialRun);
  const focused = useRef(false);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [tab, setTab] = useState("field");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [definition, setDefinition] = useState(pretty(example));
  const [showTemplates, setShowTemplates] = useState(false);
  const [evidence, setEvidence] = useState<Evidence | null>(null);
  const [correctionEvidence, setCorrectionEvidence] = useState<Evidence | null>(
    null,
  );
  const load = useCallback(async () => {
    const [docs, definitions, jobs] = await Promise.all([
      api<{ items: Document[] }>(
        `/organizations/${organization}/documents?page_size=50`,
      ),
      api<Template[]>(`${base}/templates`),
      api<Run[]>(`${base}/runs`),
    ]);
    setDocuments(docs.items);
    setTemplates(definitions);
    setRuns(jobs);
  }, [base, organization]);
  useEffect(() => {
    let active = true;
    const refresh = async () => {
      try {
        if (active) await load();
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    void refresh();
    const timer = setInterval(() => {
      if (!document.hidden) void refresh();
    }, 3000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [load]);
  const loadDetail = useCallback(async () => {
    if (!selected) return;
    const next = await api<Detail>(`${base}/runs/${selected}`);
    setDetail(next);
  }, [base, selected]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    const refresh = async () => {
      try {
        const next = await api<Detail>(`${base}/runs/${selected}`);
        if (active) {
          setDetail(next);
          if (initialItem && selected === initialRun && !focused.current) {
            const item = next.items.find((row) => row.id === initialItem);
            if (item) {
              setTab(item.kind);
              focused.current = true;
              requestAnimationFrame(() =>
                document
                  .getElementById(`result-${initialItem}`)
                  ?.scrollIntoView?.(),
              );
            }
          }
        }
      } catch (e) {
        if (active) {
          setDetail(null);
          setEvidence(null);
          setError((e as Error).message);
        }
      }
    };
    void refresh();
    const timer = setInterval(() => {
      if (!document.hidden) void refresh();
    }, 3000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [base, selected, initialItem, initialRun]);
  async function action(work: () => Promise<void>) {
    setBusy(true);
    setError("");
    try {
      await work();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function submit() {
    await action(async () => {
      const run = await api<Run>(`${base}/runs`, {
        method: "POST",
        body: JSON.stringify({
          document_id: left,
          revision_id: leftRevision || null,
          other_document_id: mode === "compare" ? right : null,
          other_revision_id: rightRevision || null,
          template_id: mode === "extract" ? template : null,
          mode,
          engine,
        }),
      });
      setDetail(null);
      setEvidence(null);
      setSelected(run.id);
      setTab(mode === "compare" ? "change" : "field");
      await load();
    });
  }
  async function download(format: string, obligationsOnly = false) {
    await action(async () => {
      const response = await apiResponse(
        `${base}/runs/${selected}/export?format=${format}${obligationsOnly ? "&kind=obligation" : ""}`,
      );
      const url = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `analysis-${selected}.${format}`;
      anchor.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }
  return (
    <div className="grid gap-6 lg:grid-cols-[290px_1fr]">
      <aside className="space-y-5">
        <section className="panel space-y-3 p-5">
          <h2 className="font-semibold">New analysis</h2>
          <label className="block text-sm">
            Analysis type
            <select
              className="input mt-1"
              value={mode}
              onChange={(e) => setMode(e.target.value)}
            >
              <option value="extract">
                Extract facts, rules & obligations
              </option>
              <option value="compare">Compare revisions</option>
            </select>
          </label>
          <label className="block text-sm">
            Source document
            <select
              className="input mt-1"
              value={left}
              onChange={(e) => {
                setLeft(e.target.value);
                setLeftRevision("");
              }}
            >
              <option value="">Select document</option>
              {documents
                .filter((d) => d.status === "completed")
                .map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.filename}
                  </option>
                ))}
            </select>
          </label>
          {left && (
            <RevisionPicker
              key={left}
              base={base}
              documentId={left}
              value={leftRevision}
              onChange={setLeftRevision}
            />
          )}
          {mode === "compare" ? (
            <>
              <label className="block text-sm">
                Compare with
                <select
                  className="input mt-1"
                  value={right}
                  onChange={(e) => {
                    setRight(e.target.value);
                    setRightRevision("");
                  }}
                >
                  <option value="">Select second document</option>
                  {documents
                    .filter((d) => d.status === "completed")
                    .map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.filename}
                      </option>
                    ))}
                </select>
              </label>
              {right && (
                <RevisionPicker
                  key={right}
                  base={base}
                  documentId={right}
                  value={rightRevision}
                  onChange={setRightRevision}
                />
              )}
            </>
          ) : (
            <>
              <label className="block text-sm">
                Template version
                <select
                  className="input mt-1"
                  value={template}
                  onChange={(e) => setTemplate(e.target.value)}
                >
                  <option value="">Select template</option>
                  {templates.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name} · {t.id.slice(0, 6)}
                    </option>
                  ))}
                </select>
              </label>
              <label className="block text-sm">
                Engine
                <select
                  className="input mt-1"
                  value={engine}
                  onChange={(e) => setEngine(e.target.value)}
                >
                  <option value="deterministic">
                    Deterministic / rule-based
                  </option>
                  <option value="mock">Development mock simulation</option>
                  <option value="openai">OpenAI GPT · human review required</option>
                </select>
              </label>
            </>
          )}
          {mode === "compare" && (
            <label className="block text-sm">Comparison engine
              <select className="input mt-1" value={engine} onChange={(e) => setEngine(e.target.value)}>
                <option value="deterministic">Deterministic text differences</option>
                <option value="openai">Text differences + GPT explanations</option>
              </select>
            </label>
          )}
          <p className="text-xs text-slate-500">
            Uploader/Admin permission is required for each source. Analysis
            scans the full revision and does not require embeddings.
          </p>
          <button
            className="btn-primary w-full"
            disabled={
              busy || !left || (mode === "compare" ? !right : !template)
            }
            onClick={() => void submit()}
          >
            Queue analysis
          </button>
          {admin && (
            <button
              className="text-sm text-indigo-700"
              onClick={() => setShowTemplates(!showTemplates)}
            >
              Configure templates & rules
            </button>
          )}
        </section>
        <section className="panel p-5">
          <h2 className="mb-3 font-semibold">Analysis history</h2>
          <div className="max-h-96 space-y-2 overflow-y-auto">
            {!runs.length && (
              <p className="text-sm text-slate-500">No analyses yet.</p>
            )}
            {runs.map((r) => (
              <button
                key={r.id}
                className={`block w-full rounded-lg p-3 text-left text-sm ${r.id === selected ? "bg-indigo-50 text-indigo-700" : "hover:bg-slate-50"}`}
                onClick={() => {
                  setDetail(null);
                  setEvidence(null);
                  setSelected(r.id);
                  setTab(r.mode === "compare" ? "change" : "field");
                }}
              >
                <span className="font-medium">
                  {r.mode === "compare" ? "Comparison" : "Extraction"} ·{" "}
                  {r.id.slice(0, 6)}
                </span>
                <br />
                {r.engine === "openai" ? "GPT review candidates · " : r.engine === "mock" ? "MOCK · " : "Rule-based · "}
                {r.state}
              </button>
            ))}
          </div>
        </section>
      </aside>
      <div className="space-y-5">
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        {busy && (
          <p role="status" className="text-sm text-indigo-700">
            Saving changes…
          </p>
        )}
        {showTemplates && admin && (
          <section className="panel space-y-3 p-5">
            <h2 className="font-semibold">
              Versioned template & rule definition
            </h2>
            <p className="text-sm text-slate-500">
              Literal labels use “Label: value”. Dates require YYYY-MM-DD; money
              requires a currency code, e.g. USD 15000. Save creates an
              immutable version.
            </p>
            <select
              aria-label="Copy template"
              className="input"
              onChange={(e) => {
                const t = templates.find((t) => t.id === e.target.value);
                if (t)
                  setDefinition(
                    pretty({
                      name: `${t.name} revised`,
                      parent_id: t.id,
                      ...t.definition,
                    }),
                  );
              }}
            >
              <option value="">Copy an existing version</option>
              {templates.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
            </select>
            <textarea
              aria-label="Template JSON"
              className="input min-h-80 font-mono text-xs"
              value={definition}
              onChange={(e) => setDefinition(e.target.value)}
            />
            <button
              className="btn-primary"
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  await api(`${base}/templates`, {
                    method: "POST",
                    body: JSON.stringify(JSON.parse(definition)),
                  });
                  await load();
                  setShowTemplates(false);
                })
              }
            >
              Save template version
            </button>
          </section>
        )}
        {!detail ? (
          <section className="panel p-12 text-center text-slate-500">
            Select an analysis or queue a new one. Documents, original values,
            and review history remain separate.
          </section>
        ) : (
          <>
            <section className="panel p-5">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold">
                    {detail.run.mode === "compare"
                      ? "Revision comparison"
                      : "Structured extraction"}
                  </h2>
                  <p className="mt-1 text-sm text-slate-500">
                    {detail.run.engine === "mock"
                      ? "DEVELOPMENT MOCK — simulated extraction"
                      : detail.run.engine === "openai"
                        ? "OpenAI GPT — review candidates; verify evidence before reliance"
                        : "Deterministic / rule-based"}{" "}
                    · {detail.run.state}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    className="btn-secondary"
                    disabled={busy || detail.run.state !== "completed"}
                    onClick={() => void download("json")}
                  >
                    Export JSON
                  </button>
                  <button
                    className="btn-secondary"
                    disabled={busy || detail.run.state !== "completed"}
                    onClick={() => void download("csv", tab === "obligation")}
                  >
                    {tab === "obligation"
                      ? "Export obligations CSV"
                      : "Export CSV"}
                  </button>
                </div>
              </div>
              {detail.usage && (
                <p className="mt-2 text-xs text-slate-500">
                  {detail.usage.model} · Input {detail.usage.input_tokens ?? "unknown"} / output{" "}
                  {detail.usage.output_tokens ?? "unknown"} tokens · Estimated USD{" "}
                  {detail.usage.estimated_cost_usd ?? "unknown"}
                </p>
              )}
              {detail.superseded && (
                <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                  Historical revision — newer extraction exists. Reviewed values
                  have been preserved.
                </p>
              )}
              {detail.run.error && (
                <p className="error mt-3">{detail.run.error}</p>
              )}
              {detail.run.state === "failed" && detail.can_manage && (
                <button
                  className="btn-secondary mt-3"
                  onClick={() =>
                    void action(async () => {
                      await api(`${base}/runs/${selected}/retry`, {
                        method: "POST",
                      });
                      await loadDetail();
                    })
                  }
                >
                  Retry analysis
                </button>
              )}
              <p className="mt-3 text-xs text-slate-500">
                Coverage: {pretty(detail.run.coverage)}. Sources:{" "}
                {detail.sources.map((s) => s.filename).join(" / ")}
              </p>
            </section>
            <nav
              className="flex flex-wrap gap-2"
              aria-label="Result categories"
            >
              {[
                ["field", "Extraction"],
                ["change", "Comparison"],
                ["risk", "Risks"],
                ["obligation", "Obligations"],
              ].map(([key, label]) => (
                <button
                  key={key}
                  className={tab === key ? "btn-primary" : "btn-secondary"}
                  onClick={() => setTab(key)}
                >
                  {label} ({detail.items.filter((i) => i.kind === key).length})
                </button>
              ))}
            </nav>
            {detail.items.filter((i) => i.kind === tab).length === 0 && (
              <p className="panel p-8 text-sm text-slate-500">
                No results in this category. Pending jobs require the document
                worker; no detected findings does not guarantee absence of risk.
              </p>
            )}
            {detail.items
              .filter((i) => i.kind === tab)
              .map((item) => (
                <section
                  className={`panel p-5 ${initialItem === item.id ? "ring-2 ring-indigo-300" : ""}`}
                  id={`result-${item.id}`}
                  key={item.id}
                >
                  <div className="flex flex-wrap justify-between gap-2">
                    <h3 className="font-semibold">{item.name}</h3>
                    <span className="text-xs text-slate-500">
                      {item.validation} · {item.review_status} · v{item.version}
                    </span>
                  </div>
                  {item.kind === "change" ? (
                    <div className="mt-4 grid gap-3 sm:grid-cols-2">
                      <div className="rounded-lg bg-red-50 p-4">
                        <h4 className="mb-2 text-xs font-semibold text-red-800">
                          BEFORE
                        </h4>
                        <p className="whitespace-pre-wrap text-sm">
                          {String(
                            item.original.before ?? "No passage — addition",
                          )}
                        </p>
                      </div>
                      <div className="rounded-lg bg-emerald-50 p-4">
                        <h4 className="mb-2 text-xs font-semibold text-emerald-800">
                          AFTER
                        </h4>
                        <p className="whitespace-pre-wrap text-sm">
                          {String(
                            item.original.after ?? "No passage — removal",
                          )}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <pre className="mt-3 overflow-x-auto whitespace-pre-wrap rounded-lg bg-slate-50 p-4 text-xs leading-6">
                      {pretty(item.original)}
                    </pre>
                  )}
                  {item.corrected && (
                    <div className="mt-3">
                      <p className="text-xs font-semibold">
                        REVIEWER CORRECTION (original preserved)
                      </p>
                      <pre className="mt-2 whitespace-pre-wrap text-xs">
                        {pretty(item.corrected)}
                      </pre>
                    </div>
                  )}
                  <div className="mt-3 flex flex-wrap gap-2">
                    {[
                      ...item.evidence,
                      ...((item.corrected?.evidence as
                        | Evidence[]
                        | undefined) ?? []),
                    ].map((e, i) => (
                      <button
                        key={i}
                        className="rounded-lg border border-slate-200 px-3 py-2 text-xs text-indigo-700"
                        onClick={() => setEvidence(e)}
                      >
                        {
                          detail.sources.find(
                            (s) => s.revision_id === e.revision_id,
                          )?.filename
                        }{" "}
                        · {e.label} · [{e.start}:{e.end}]
                      </button>
                    ))}
                  </div>
                  {!item.evidence.length && (
                    <p className="mt-3 text-xs text-amber-800">
                      No positive passage found. This is a validation/coverage
                      finding, not quoted evidence of absence.
                    </p>
                  )}
                  {item.kind === "obligation" && (
                    <p className="mt-3 text-sm font-medium">
                      Tracking status: {item.obligation_status}
                    </p>
                  )}
                  {(detail.can_manage || item.can_review) && (
                    <ReviewPanel
                      item={item}
                      busy={busy}
                      sourceEvidence={
                        correctionEvidence &&
                        detail.sources.some(
                          (s) =>
                            s.revision_id === correctionEvidence.revision_id,
                        )
                          ? correctionEvidence
                          : null
                      }
                      onReview={(payload) =>
                        action(async () => {
                          await api(
                            `${base}/runs/${selected}/items/${item.id}/review`,
                            {
                              method: "POST",
                              body: JSON.stringify({
                                version: item.version,
                                ...payload,
                              }),
                            },
                          );
                          await loadDetail();
                        })
                      }
                    />
                  )}
                  <details className="mt-4 text-xs">
                    <summary className="cursor-pointer text-slate-500">
                      Review history (
                      {
                        detail.reviews.filter((r) => r.item_id === item.id)
                          .length
                      }
                      )
                    </summary>
                    {detail.reviews
                      .filter((r) => r.item_id === item.id)
                      .map((r) => (
                        <p className="mt-2" key={r.id}>
                          {r.created_at} · {r.action} · {r.reason} · reviewer{" "}
                          {r.actor_id?.slice(0, 8)}
                        </p>
                      ))}
                  </details>
                </section>
              ))}
            <CoverageBrowser
              key={detail.run.id}
              base={base}
              detail={detail}
              onEvidence={(source) => {
                setCorrectionEvidence(source);
                setEvidence(source);
              }}
            />
          </>
        )}
        {evidence && (
          <section
            className="panel border-indigo-200 p-5"
            aria-label="Source evidence"
          >
            <div className="flex justify-between">
              <h3 className="font-semibold">
                {evidence.label} · revision {evidence.revision_id.slice(0, 8)}
              </h3>
              <button onClick={() => setEvidence(null)}>Close</button>
            </div>
            <blockquote className="mt-3 whitespace-pre-wrap text-sm leading-7">
              {evidence.quote}
            </blockquote>
          </section>
        )}
      </div>
    </div>
  );
}

function RevisionPicker({
  base,
  documentId,
  value,
  onChange,
}: {
  base: string;
  documentId: string;
  value: string;
  onChange: (v: string) => void;
}) {
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<Revision[]>(`${base}/documents/${documentId}/revisions`)
      .then((r) => {
        if (active) setRevisions(r);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [base, documentId]);
  return (
    <label className="block text-xs text-slate-500">
      Source revision
      <select
        aria-label={`Revision for ${documentId}`}
        className="input mt-1"
        value={value}
        onChange={(e) => onChange(e.target.value)}
      >
        <option value="">Latest successful extraction</option>
        {revisions.map((r) => (
          <option key={r.id} value={r.id}>
            {r.created_at} · {r.current ? "current" : "historical"}
          </option>
        ))}
      </select>
      {error}
    </label>
  );
}

export function ReviewPanel({
  item,
  busy,
  onReview,
  sourceEvidence,
}: {
  item: Item;
  busy: boolean;
  sourceEvidence: Evidence | null;
  onReview: (payload: Record<string, unknown>) => Promise<void>;
}) {
  const [reason, setReason] = useState("");
  const [value, setValue] = useState("");
  const [action, setAction] = useState("approve");
  const [status, setStatus] = useState("in_progress");
  const [source, setSource] = useState("");
  return (
    <form
      className="mt-5 grid gap-3 rounded-lg border border-slate-200 p-4"
      onSubmit={(e) => {
        e.preventDefault();
        void onReview({
          action,
          reason,
          value: action === "correct" ? value : null,
          evidence:
            action === "correct" && source !== ""
              ? source === "coverage"
                ? sourceEvidence
                : item.evidence[Number(source)]
              : null,
          obligation_status: action === "obligation" ? status : null,
        });
      }}
    >
      <label className="text-xs font-semibold">
        Review action
        <select
          className="input mt-1"
          value={action}
          onChange={(e) => setAction(e.target.value)}
        >
          <option value="approve">Approve candidate</option>
          <option value="reject">Reject candidate</option>
          <option value="correct">Correct value</option>
          {item.kind === "obligation" && (
            <option value="obligation">Update obligation status</option>
          )}
        </select>
      </label>
      {action === "correct" && (
        <>
          <input
            aria-label="Corrected value"
            className="input"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Corrected literal value"
            required
            maxLength={10000}
          />
          <select
            aria-label="Correction evidence"
            className="input"
            value={source}
            onChange={(e) => setSource(e.target.value)}
          >
            <option value="">Manual assertion — not verified</option>
            {sourceEvidence && (
              <option value="coverage">
                Use selected coverage passage: {sourceEvidence.label}
              </option>
            )}
            {item.evidence.map((e, i) => (
              <option key={i} value={i}>
                Use passage {i + 1}: {e.label}
              </option>
            ))}
          </select>
          <p className="text-xs text-slate-500">
            A verified correction must occur literally in its source passage.
            Otherwise it remains an unverified manual assertion.
          </p>
        </>
      )}
      {action === "obligation" && (
        <select
          aria-label="Obligation status"
          className="input"
          value={status}
          onChange={(e) => setStatus(e.target.value)}
        >
          {["open", "in_progress", "completed", "dismissed"].map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>
      )}
      <input
        aria-label="Review reason"
        className="input"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Reason for this review (required)"
        required
        maxLength={1000}
      />
      <button
        className="btn-secondary justify-self-start"
        disabled={busy || !reason.trim()}
      >
        Save review
      </button>
    </form>
  );
}

function CoverageBrowser({
  base,
  detail,
  onEvidence,
}: {
  base: string;
  detail: Detail;
  onEvidence: (source: Evidence) => void;
}) {
  const [sections, setSections] = useState<Section[]>([]);
  const [revision, setRevision] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  async function load(id: string, next: number) {
    try {
      const data = await api<{ items: Section[]; total: number }>(
        `${base}/runs/${detail.run.id}/sections?revision_id=${id}&page=${next}`,
      );
      setSections(data.items);
      setTotal(data.total);
      setPage(next);
      setRevision(id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <details className="panel p-5">
      <summary className="cursor-pointer text-sm font-semibold">
        Inspect revision coverage & original sections
      </summary>
      <p className="mt-3 text-xs text-slate-500">
        For not-detected findings, inspect the evaluated source scope. No
        fabricated absence quotation is supplied.
      </p>
      <div className="my-3 flex flex-wrap gap-2">
        {detail.sources.map((s) => (
          <button
            className="btn-secondary"
            key={s.revision_id}
            onClick={() => void load(s.revision_id, 1)}
          >
            {s.filename} · {s.revision_id.slice(0, 6)}
          </button>
        ))}
      </div>
      {error && <p role="alert">{error}</p>}
      {sections.map((s) => (
        <article key={s.id} className="mt-3">
          <h4 className="text-xs font-semibold">{s.label}</h4>
          <pre className="mt-1 max-h-72 overflow-auto whitespace-pre-wrap text-xs leading-6">
            {s.text}
          </pre>
          {(detail.can_manage ||
            detail.items.some((item) => item.can_review)) && (
            <button
              className="mt-2 text-xs text-indigo-700"
              onMouseDown={(e) => e.preventDefault()}
              onClick={() => {
                const selectedText = window.getSelection()?.toString() ?? "";
                const quote =
                  selectedText && s.text.includes(selectedText)
                    ? selectedText.slice(0, 10000)
                    : s.text.slice(0, 10000);
                const start = s.text.indexOf(quote);
                if (quote)
                  onEvidence({
                    section_id: s.id,
                    revision_id: revision,
                    label: s.label,
                    page_number: s.page_number,
                    start,
                    end: start + quote.length,
                    quote,
                  });
              }}
            >
              Use selected text (or first 10000 characters) as correction
              evidence
            </button>
          )}
        </article>
      ))}
      {revision && (
        <div className="mt-3 flex gap-3">
          <button
            disabled={page <= 1}
            onClick={() => void load(revision, page - 1)}
          >
            Previous
          </button>
          <span className="text-xs">Page {page}</span>
          <button
            disabled={page * 5 >= total}
            onClick={() => void load(revision, page + 1)}
          >
            Next
          </button>
        </div>
      )}
    </details>
  );
}
