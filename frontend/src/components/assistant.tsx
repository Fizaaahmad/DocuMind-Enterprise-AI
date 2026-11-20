"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Organization } from "../lib/types";

type Source = {
  source_id: string;
  document_id: string;
  filename: string;
  page_number: number | null;
  label: string;
  text?: string;
  quote?: string;
  similarity: number;
};
type Message = {
  id: string;
  question: string;
  answer: string;
  state: string;
  citations: Source[];
  is_mock: boolean;
  provider?: string;
  usage?: {
    model: string;
    input_tokens: number | null;
    output_tokens: number | null;
    estimated_cost_usd: string | null;
  } | null;
};
type Conversation = { id: string; title: string };
type Status = {
  embeddings_enabled: boolean;
  provider: string;
  is_mock: boolean;
  documents: {
    id: string;
    filename: string;
    status: string;
    index_status: string;
    index_error: string | null;
  }[];
};

export function Assistant() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [organization, setOrganization] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    api<Organization[]>("/organizations")
      .then((items) => {
        if (active) {
          setOrganizations(items);
          setOrganization(items[0]?.id ?? "");
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
    <main className="mx-auto max-w-7xl p-4 sm:p-8">
      <header className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-indigo-600">
            DOCUMIND / INTELLIGENCE
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-slate-900">
            Knowledge assistant
          </h1>
          <p className="mt-2 text-slate-500">
            Find evidence. Explore your organization’s documents.
          </p>
        </div>
        <nav className="flex gap-4 text-sm font-medium text-indigo-700">
          <Link href="/dashboard">Dashboard</Link>
          <Link href="/documents">Documents</Link>
        </nav>
      </header>
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
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
      {!organization ? (
        <p>Create an organization in the dashboard to get started.</p>
      ) : (
        <Workspace key={organization} organization={organization} />
      )}
    </main>
  );
}

function Workspace({ organization }: { organization: string }) {
  const base = `/organizations/${organization}/intelligence`;
  const [status, setStatus] = useState<Status | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversation, setConversation] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [selection, setSelection] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState<Source[] | null>(null);
  const [source, setSource] = useState<Source | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [refresh, setRefresh] = useState(0);
  const loadConversations = useCallback(async () => {
    setConversations(await api<Conversation[]>(`${base}/conversations`));
  }, [base]);
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const [next, history] = await Promise.all([
          api<Status>(`${base}/status`),
          api<Conversation[]>(`${base}/conversations`),
        ]);
        if (active) {
          setStatus(next);
          setConversations(history);
        }
      } catch (e) {
        if (active) setError((e as Error).message);
      }
    };
    void load();
    const timer = setInterval(() => {
      if (!document.hidden) void load();
    }, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [base, refresh]);
  useEffect(() => {
    if (!conversation) return;
    let active = true;
    api<Message[]>(`${base}/conversations/${conversation}/messages`)
      .then((items) => {
        if (active) {
          setMessages(items);
          setHistoryLoading(false);
        }
      })
      .catch((e) => {
        if (active) {
          setError(e.message);
          setHistoryLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [base, conversation]);

  async function submit(mode: "search" | "answer") {
    if (!question.trim() || busy) return;
    setBusy(true);
    setError("");
    setSource(null);
    try {
      const body = JSON.stringify({
        question: question.trim(),
        document_ids: selection,
      });
      const options = {
        method: "POST",
        body,
        signal: AbortSignal.timeout(120000),
      };
      if (mode === "search") {
        const data = await api<{ sources: Source[] }>(
          `${base}/search`,
          options,
        );
        setResults(data.sources);
      } else {
        let id = conversation;
        if (!id) {
          const created = await api<Conversation>(`${base}/conversations`, {
            method: "POST",
          });
          id = created.id;
        }
        await api<Message>(`${base}/conversations/${id}/messages`, options);
        setConversation(id);
        setMessages(
          await api<Message[]>(`${base}/conversations/${id}/messages`),
        );
        setQuestion("");
        setResults(null);
        await loadConversations();
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function index(id: string) {
    setBusy(true);
    setError("");
    try {
      await api(`${base}/documents/${id}/index`, { method: "POST" });
      setRefresh((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[260px_1fr]">
      <aside className="space-y-6">
        <section className="panel p-5">
          <h2 className="font-semibold">Conversations</h2>
          <button
            className="btn-secondary my-3 w-full"
            disabled={busy}
            onClick={() => {
              setConversation("");
              setMessages([]);
              setSource(null);
              setError("");
            }}
          >
            New conversation
          </button>
          <div className="max-h-64 space-y-1 overflow-y-auto">
            {conversations.map((item) => (
              <button
                key={item.id}
                disabled={busy || historyLoading}
                aria-pressed={conversation === item.id}
                className={`w-full truncate rounded-lg px-3 py-2 text-left text-sm ${conversation === item.id ? "bg-indigo-50 text-indigo-700" : "hover:bg-slate-50"}`}
                onClick={() => {
                  if (item.id !== conversation) {
                    setMessages([]);
                    setSource(null);
                    setHistoryLoading(true);
                    setConversation(item.id);
                  }
                }}
              >
                {item.title}
              </button>
            ))}
          </div>
          {conversation && (
            <button
              className="mt-3 text-sm text-red-700"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                try {
                  await api(`${base}/conversations/${conversation}`, {
                    method: "DELETE",
                  });
                  setConversation("");
                  setMessages([]);
                  setSource(null);
                  await loadConversations();
                } catch (e) {
                  setError((e as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              Delete conversation
            </button>
          )}
        </section>
        <section className="panel p-5">
          <h2 className="font-semibold">Document scope</h2>
          <p className="my-2 text-xs text-slate-500">
            No selection searches all indexed documents. Indexing controls
            require uploader or Admin permission.
          </p>
          <div className="max-h-96 space-y-4 overflow-y-auto">
            {status?.documents.map((d) => (
              <div key={d.id} className="text-sm">
                <label className="flex items-start gap-2">
                  <input
                    type="checkbox"
                    className="mt-1"
                    checked={selection.includes(d.id)}
                    disabled={busy}
                    onChange={(e) =>
                      setSelection((ids) =>
                        e.target.checked
                          ? [...ids, d.id]
                          : ids.filter((id) => id !== d.id),
                      )
                    }
                  />
                  <span className="break-all">{d.filename}</span>
                </label>
                <p className="ml-5 mt-1 text-xs text-slate-500">
                  {d.status === "completed" ? d.index_status : d.status}
                </p>
                {d.index_error && (
                  <p className="mt-1 text-xs text-red-700">{d.index_error}</p>
                )}
                {d.status === "completed" &&
                  ["unindexed", "failed"].includes(d.index_status) && (
                    <button
                      className="ml-5 mt-1 text-xs text-indigo-700"
                      disabled={busy || !status.embeddings_enabled}
                      onClick={() => void index(d.id)}
                    >
                      Index document
                    </button>
                  )}
              </div>
            ))}
          </div>
        </section>
      </aside>
      <section className="panel flex min-h-[650px] flex-col overflow-hidden">
        <div className="border-b border-slate-100 p-5">
          <h2 className="font-semibold">Document intelligence</h2>
          {status?.is_mock && (
            <p className="mt-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
              Development mock — extractive preview. These are selected source
              passages, not real AI answers.
            </p>
          )}
          {status && !status.embeddings_enabled && (
            <p className="mt-2 text-sm text-amber-800">
              Local embeddings are disabled. Configure and prepare the model,
              then index your documents.
            </p>
          )}
          {status?.provider === "disabled" && (
            <p className="mt-2 text-sm text-slate-500">
              Answer provider is disabled. Semantic search is available when
              documents are indexed.
            </p>
          )}
        </div>
        <div className="flex-1 space-y-6 p-5 sm:p-7" aria-live="polite">
          {!messages.length && results === null && (
            <div className="py-16 text-center">
              <h3 className="text-xl font-medium text-slate-800">
                Your documents, with evidence
              </h3>
              <p className="mx-auto mt-3 max-w-md text-sm leading-6 text-slate-500">
                Search for a policy, fact, or topic. Open a source reference to
                inspect the exact supporting passage.
              </p>
            </div>
          )}
          {historyLoading && <p role="status">Loading conversation…</p>}
          {messages.map((m) => (
            <article key={m.id} className="space-y-3">
              <p className="ml-auto max-w-xl rounded-xl bg-indigo-50 p-4 text-slate-900">
                {m.question}
              </p>
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                {m.is_mock
                  ? "Development mock · extractive preview"
                  : m.provider === "openai"
                    ? "OpenAI GPT · verify source evidence"
                    : "Assistant"}{" "}
                · {m.state}
              </p>
              <p className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
                {m.answer}
              </p>
              {m.usage && (
                <p className="text-xs text-slate-500">
                  {m.usage.model} · Input {m.usage.input_tokens ?? "unknown"} / output{" "}
                  {m.usage.output_tokens ?? "unknown"} tokens · Estimated USD{" "}
                  {m.usage.estimated_cost_usd ?? "unknown"}
                </p>
              )}
              <div className="flex flex-wrap gap-2">
                {m.citations.map((s, i) => (
                  <button
                    key={`${s.source_id}-${i}`}
                    className="rounded-lg border border-slate-200 px-3 py-2 text-left text-xs hover:border-indigo-400"
                    onClick={() => setSource(s)}
                  >
                    [{i + 1}] {s.filename} · {s.label}
                  </button>
                ))}
              </div>
            </article>
          ))}
          {results !== null && (
            <div>
              <h3 className="mb-3 font-semibold">Search results</h3>
              {!results.length && (
                <p>
                  No relevant indexed passages found. Try another question or
                  index more documents.
                </p>
              )}
              {results.map((s) => (
                <button
                  key={s.source_id}
                  className="mb-3 block w-full rounded-xl border border-slate-200 p-4 text-left hover:border-indigo-400"
                  onClick={() => setSource(s)}
                >
                  <span className="text-sm font-semibold">
                    {s.filename} · {s.label}
                  </span>
                  <p className="mt-2 line-clamp-3 text-sm text-slate-600">
                    {s.text}
                  </p>
                </button>
              ))}
            </div>
          )}
          {source && (
            <aside
              className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-5"
              aria-label="Source passage"
            >
              <div className="flex justify-between gap-4">
                <h3 className="font-semibold">
                  {source.filename} · {source.label}
                </h3>
                <button
                  aria-label="Close source"
                  onClick={() => setSource(null)}
                >
                  ×
                </button>
              </div>
              <p className="mt-3 whitespace-pre-wrap text-sm leading-7">
                {source.quote ?? source.text}
              </p>
              <Link
                className="mt-4 inline-block text-sm text-indigo-700"
                href={`/documents?organization=${organization}`}
              >
                Open document library
              </Link>
            </aside>
          )}
          {busy && (
            <p role="status" className="text-sm text-indigo-700">
              Working with your documents…
            </p>
          )}
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
        </div>
        <form
          className="border-t border-slate-100 p-5"
          onSubmit={(e) => {
            e.preventDefault();
            void submit("answer");
          }}
        >
          <label className="sr-only" htmlFor="question">
            Ask your documents
          </label>
          <textarea
            id="question"
            className="input min-h-24"
            maxLength={4000}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            disabled={busy || historyLoading}
            placeholder="Ask your documents a question…"
          />
          <div className="mt-3 flex flex-wrap justify-end gap-3">
            <button
              type="button"
              className="btn-secondary"
              disabled={busy || !question.trim() || !status?.embeddings_enabled}
              onClick={() => void submit("search")}
            >
              Semantic search
            </button>
            <button
              className="btn-primary"
              disabled={
                busy ||
                historyLoading ||
                !question.trim() ||
                !status?.embeddings_enabled ||
                status.provider === "disabled"
              }
            >
              {status?.is_mock ? "Preview mock answer" : "Ask assistant"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
