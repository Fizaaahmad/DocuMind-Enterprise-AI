"use client";

import Link from "next/link";
import { AnswerText, UsageDetails } from "./answer-text";
import { Dialog, EmptyState, Icon, Skeleton, useConfirmation } from "./ui";
import { WorkspaceShell } from "./workspace-shell";
import { preferredOrganization } from "../lib/organization-preference";
import { useCallback, useEffect, useState } from "react";
import { api } from "../lib/api";
import type { Organization, User } from "../lib/types";

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
  model?: string | null;
  is_mock: boolean;
  documents: {
    id: string;
    filename: string;
    status: string;
    index_status: string;
    index_error: string | null;
  }[];
};

export function Assistant({ user }: { user?: User } = {}) {
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
      active="assistant"
      title="Knowledge assistant"
      description="Ask better questions. Get answers grounded in your documents."
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

      {!organization ? (
        <p>Create an organization in the dashboard to get started.</p>
      ) : (
        <Workspace key={organization} organization={organization} />
      )}
    </WorkspaceShell>
  );
}

function Workspace({ organization }: { organization: string }) {
  const base = `/organizations/${organization}/intelligence`;
  const { confirm, confirmation } = useConfirmation();
  const [documentQuery, setDocumentQuery] = useState("");
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
    <div className="assistant-grid">
      {confirmation}
      <aside className="assistant-sidebar">
        <section className="panel assistant-conversations">
          <div className="assistant-section-title">
            <Icon name="assistant" />
            <h2>Conversations</h2>
            <span>{conversations.length}</span>
          </div>
          <button
            className="btn-primary w-full"
            disabled={busy}
            onClick={() => {
              setConversation("");
              setMessages([]);
              setSource(null);
              setError("");
            }}
          >
            <Icon name="plus" />
            New conversation
          </button>
          <div className="conversation-list">
            {conversations.map((item) => (
              <button
                key={item.id}
                disabled={busy || historyLoading}
                aria-pressed={conversation === item.id}
                className={`conversation-link ${conversation === item.id ? "conversation-active" : ""}`}
                onClick={() => {
                  if (item.id !== conversation) {
                    setMessages([]);
                    setSource(null);
                    setHistoryLoading(true);
                    setConversation(item.id);
                  }
                }}
              >
                <Icon name="quote" />
                <span>{item.title}</span>
              </button>
            ))}
            {!conversations.length && (
              <p className="sidebar-empty">
                A place for every question.
                <br />
                Start your first conversation.
              </p>
            )}
          </div>
          {conversation && (
            <button
              className="conversation-delete"
              disabled={busy}
              onClick={async () => {
                if (
                  !(await confirm(
                    "Delete conversation",
                    "Remove this conversation and its message history? Your documents will be preserved.",
                  ))
                )
                  return;
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
        <section className="panel assistant-documents">
          <div className="assistant-section-title">
            <Icon name="documents" />
            <h2>Document scope</h2>
          </div>
          <p className="sidebar-help">
            {selection.length
              ? `${selection.length} selected`
              : "All indexed documents"}
            . Only your organization’s sources are searched.
          </p>
          <label className="document-scope-search">
            <Icon name="search" />
            <input
              aria-label="Find a document in scope"
              placeholder="Find a document…"
              value={documentQuery}
              onChange={(e) => setDocumentQuery(e.target.value)}
            />
          </label>
          <div className="scope-list">
            {status?.documents
              .filter((d) =>
                d.filename.toLowerCase().includes(documentQuery.toLowerCase()),
              )
              .map((d) => (
                <div
                  key={d.id}
                  className={`scope-file ${selection.includes(d.id) ? "scope-selected" : ""}`}
                >
                  <label>
                    <input
                      type="checkbox"
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
                    <span>
                      <strong>{d.filename}</strong>
                      <span className="scope-status">
                        {d.status === "completed"
                          ? d.index_status === "completed"
                            ? "Indexed · ready to search"
                            : d.index_status
                          : d.status}
                      </span>
                    </span>
                  </label>
                  {d.index_error && (
                    <p className="mt-2 text-xs text-rose-700">
                      {d.index_error}
                    </p>
                  )}
                  {d.status === "completed" &&
                    ["unindexed", "failed"].includes(d.index_status) && (
                      <button
                        className="scope-index"
                        disabled={busy || !status.embeddings_enabled}
                        onClick={() => void index(d.id)}
                      >
                        Index document
                      </button>
                    )}
                </div>
              ))}
            {!status && !error && <Skeleton rows={3} />}
            {!status && error && (
              <p className="sidebar-empty">
                Sources are temporarily unavailable. Refresh the workspace to
                reconnect.
              </p>
            )}
            {status && !status.documents.length && (
              <p className="sidebar-empty">
                Upload and index documents to build your knowledge workspace.
              </p>
            )}
            {status &&
              status.documents.length > 0 &&
              !status.documents.some((d) =>
                d.filename.toLowerCase().includes(documentQuery.toLowerCase()),
              ) && (
                <p className="sidebar-empty">No documents match this filter.</p>
              )}
          </div>
          <p className="scope-footnote">
            <Icon name="shield" />
            Indexing requires uploader or Admin permission.
          </p>
        </section>
      </aside>
      <section className="panel assistant-chat">
        <div className="chat-topbar">
          <div className="chat-identity">
            <span className="chat-icon">
              <Icon name="assistant" />
            </span>
            <div>
              <h2>Document intelligence</h2>
              <p>Grounded in your knowledge. Connected to your sources.</p>
            </div>
          </div>
          <span className="badge">
            {status?.is_mock
              ? "Development mock"
              : status?.provider === "openai"
                ? "OpenAI GPT"
                : "Evidence workspace"}
          </span>
        </div>
        {status?.is_mock && (
          <p className="mock-banner">
            Development mock — extractive preview. These are selected source
            passages, not real AI answers.
          </p>
        )}
        {status && !status.embeddings_enabled && (
          <p className="mock-banner">
            Local embeddings are disabled. Configure and prepare the model, then
            index your documents.
          </p>
        )}
        {status?.provider === "disabled" && (
          <p className="mock-banner">
            Answer provider is disabled. Semantic search is available when
            documents are indexed.
          </p>
        )}
        <div className="chat-transcript" aria-live="polite">
          {!messages.length && results === null && !historyLoading && (
            <div className="assistant-welcome">
              <span className="welcome-spark">
                <Icon name="assistant" />
              </span>
              <p className="eyebrow">A CLEARER PICTURE STARTS HERE</p>
              <h3>Your documents, with evidence</h3>
              <p>
                Explore what matters. Connect the details.
                <br />
                Every answer comes back to the source.
              </p>
              <div className="question-starters">
                {[
                  "What are the key obligations?",
                  "What are the payment terms?",
                  "Find the important deadlines",
                ].map((prompt) => (
                  <button
                    key={prompt}
                    type="button"
                    onClick={() => {
                      setQuestion(prompt);
                      document.getElementById("question")?.focus();
                    }}
                  >
                    <Icon name="quote" />
                    <span>{prompt}</span>
                    <Icon name="arrow" />
                  </button>
                ))}
              </div>
              <span className="welcome-disclaimer">
                Questions are suggestions. Answers depend on your available
                documents.
              </span>
            </div>
          )}
          {historyLoading && <Skeleton rows={4} />}
          {messages.map((m) => (
            <article key={m.id} className="chat-exchange">
              <div className="question-row">
                <span className="question-label">YOU</span>
                <p>{m.question}</p>
              </div>
              <div className="answer-row">
                <span className="answer-avatar">
                  <Icon name="assistant" />
                </span>
                <div className="answer-body">
                  <div className="answer-heading">
                    <strong>DocuMind</strong>
                    <span>
                      {m.is_mock
                        ? "Development mock · extractive preview"
                        : m.provider === "openai"
                          ? "OpenAI GPT · verify source evidence"
                          : "Assistant"}{" "}
                      · {m.state}
                    </span>
                  </div>
                  <AnswerText
                    text={m.answer}
                    sourceCount={m.citations.length}
                    onSource={(index) => setSource(m.citations[index])}
                  />
                  {m.citations.length > 0 && (
                    <div className="answer-sources">
                      <p className="section-label">SUPPORTING SOURCES</p>
                      <div>
                        {m.citations.map((source, i) => (
                          <button
                            key={`${source.source_id}-${i}`}
                            className="source-chip"
                            onClick={() => setSource(source)}
                          >
                            <span>{i + 1}</span>
                            <Icon name="documents" />
                            <span>
                              {source.filename}
                              <small>{source.label}</small>
                            </span>
                            <Icon name="arrow" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                  {m.usage && <UsageDetails usage={m.usage} />}
                </div>
              </div>
            </article>
          ))}
          {results !== null && (
            <section className="search-evidence">
              <div className="flex items-center gap-2">
                <Icon name="search" />
                <h3>Search results</h3>
                <span className="badge">{results.length} passages</span>
              </div>
              {!results.length && (
                <EmptyState icon="search" title="No relevant passages found">
                  <p>
                    No relevant indexed passages found. Try another question or
                    index more documents.
                  </p>
                </EmptyState>
              )}
              {results.map((s) => (
                <button
                  key={s.source_id}
                  className="search-evidence-card"
                  onClick={() => setSource(s)}
                >
                  <span>
                    <Icon name="documents" />
                    {s.filename} · {s.label}
                  </span>
                  <p>{s.text}</p>
                  <small>
                    Inspect source passage <span aria-hidden="true">↗</span>
                  </small>
                </button>
              ))}
            </section>
          )}
          {busy && (
            <p role="status" className="working-indicator">
              <span />
              <span />
              <span />
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
          className="chat-composer"
          onSubmit={(e) => {
            e.preventDefault();
            void submit("answer");
          }}
        >
          <label className="sr-only" htmlFor="question">
            Ask your documents
          </label>
          <div className="composer-input">
            <textarea
              id="question"
              maxLength={4000}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              disabled={busy || historyLoading}
              placeholder="Ask a question about your documents…"
            />
            <div className="composer-toolbar">
              <span>
                <Icon name="shield" />
                {selection.length
                  ? `${selection.length} selected documents`
                  : "Organization knowledge"}
              </span>
              <div>
                <button
                  type="button"
                  className="btn-secondary"
                  disabled={
                    busy || !question.trim() || !status?.embeddings_enabled
                  }
                  onClick={() => void submit("search")}
                >
                  <Icon name="search" />
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
                  <Icon name="arrow" />
                </button>
              </div>
            </div>
          </div>
          <p className="composer-disclaimer">
            AI can make mistakes. Inspect the supporting evidence before relying
            on an answer.
          </p>
        </form>
      </section>
      {source && (
        <Dialog title="Source evidence" onClose={() => setSource(null)} wide>
          <aside aria-label="Source passage" className="evidence-view">
            <span className="evidence-label">
              <Icon name="quote" />
              ORIGINAL SOURCE PASSAGE
            </span>
            <h3>{source.filename}</h3>
            <p className="evidence-location">
              {source.label}
              {source.page_number ? ` · PDF page ${source.page_number}` : ""}
            </p>
            <blockquote>{source.quote ?? source.text}</blockquote>
            <div className="flex flex-wrap justify-between gap-3">
              <Link
                className="btn-secondary"
                href={`/documents?organization=${organization}&document=${source.document_id}`}
              >
                <Icon name="documents" />
                Open document library
              </Link>
              <button
                className="btn-secondary"
                aria-label="Close source"
                onClick={() => setSource(null)}
              >
                Close source
              </button>
            </div>
          </aside>
        </Dialog>
      )}
    </div>
  );
}
