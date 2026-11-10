"use client";

import { useEffect, useState } from "react";
import { api } from "../../lib/api";
import {
  DocumentContent,
  DocumentRecord,
  downloadDocument,
  formatBytes,
} from "../../lib/documents";

export function DocumentDetails({
  initial,
  organizationId,
  canManage,
  onClose,
  onChange,
}: {
  initial: DocumentRecord;
  organizationId: string;
  canManage: boolean;
  onClose: () => void;
  onChange: () => void;
}) {
  const [record, setRecord] = useState(initial);
  const [content, setContent] = useState<DocumentContent | null>(null);
  const [page, setPage] = useState(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pollVersion, setPollVersion] = useState(0);
  const base = `/organizations/${organizationId}/documents/${initial.id}`;
  useEffect(() => {
    let active = true;
    const load = () =>
      api<DocumentRecord>(base)
        .then((item) => {
          if (active) {
            setRecord(item);
            if (["completed", "failed"].includes(item.status))
              clearInterval(timer);
          }
        })
        .catch((error) => {
          if (active) {
            setError(error.message);
            clearInterval(timer);
          }
        });
    const timer = setInterval(() => void load(), 3000);
    void load();
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, [base, pollVersion]);
  useEffect(() => {
    let active = true;
    if (record.status === "completed")
      api<DocumentContent>(`${base}/content?page=${page}`)
        .then((item) => {
          if (active) setContent(item);
        })
        .catch((error) => {
          if (active) setError(error.message);
        });
    return () => {
      active = false;
    };
  }, [base, record.status, page]);

  async function action(operation: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await operation();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Request failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      className="panel mt-6 overflow-hidden"
      aria-labelledby="document-details-title"
    >
      <div className="flex items-start justify-between gap-4 border-b border-slate-100 p-6">
        <div className="min-w-0">
          <p className="eyebrow">Document details</p>
          <h2
            id="document-details-title"
            className="mt-2 break-words text-lg font-semibold"
          >
            {record.filename}
          </h2>
          <p className="mt-2 text-xs text-slate-500">
            {record.format.toUpperCase()} · {formatBytes(record.size_bytes)} ·{" "}
            {record.status}
          </p>
        </div>
        <button className="btn-secondary shrink-0" onClick={onClose}>
          Close details
        </button>
      </div>
      <div className="p-6">
        {error && (
          <p role="alert" className="error-box mb-4">
            {error}
          </p>
        )}
        {record.error && (
          <p role="alert" className="error-box mb-4">
            {record.error}
          </p>
        )}
        <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
          {[
            ["Source sections", record.section_count],
            ["Text chunks", record.chunk_count],
            ["Characters", record.character_count.toLocaleString()],
            [
              "Chunk / overlap",
              `${record.chunk_size} / ${record.chunk_overlap}`,
            ],
          ].map(([label, value]) => (
            <div key={label}>
              <p className="text-xs text-slate-400">{label}</p>
              <p className="mt-1 font-medium">{value}</p>
            </div>
          ))}
        </div>
        {Object.entries(record.source_metadata).some(
          ([, value]) => value !== "",
        ) && (
          <dl className="mt-5 grid gap-2 border-t border-slate-100 pt-4 text-xs text-slate-500">
            {Object.entries(record.source_metadata)
              .filter(([, value]) => value !== "")
              .map(([key, value]) => (
                <div key={key} className="flex gap-3">
                  <dt className="min-w-20 font-medium">{key}</dt>
                  <dd className="break-all">{String(value)}</dd>
                </div>
              ))}
          </dl>
        )}
        <p className="mt-5 break-all text-xs text-slate-400">
          Document ID: {record.id}
        </p>
        <div className="mt-5 flex flex-wrap gap-3">
          <button
            className="btn-secondary"
            disabled={busy || !record.storage_ready}
            onClick={() =>
              void action(() => downloadDocument(organizationId, record))
            }
          >
            Download original
          </button>
          {canManage && record.status === "failed" && record.storage_ready && (
            <button
              className="btn-primary"
              disabled={busy}
              onClick={() =>
                void action(async () => {
                  setRecord(
                    await api<DocumentRecord>(`${base}/retry`, {
                      method: "POST",
                    }),
                  );
                  setPollVersion((value) => value + 1);
                  onChange();
                })
              }
            >
              Retry processing
            </button>
          )}
          {canManage && (
            <button
              className="rounded-lg border border-rose-200 px-4 py-2.5 text-sm font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50"
              disabled={busy}
              onClick={() => {
                if (
                  window.confirm(
                    `Delete ${record.filename}? This removes the original and extracted content.`,
                  )
                )
                  void action(async () => {
                    await api(base, { method: "DELETE" });
                    onChange();
                    onClose();
                  });
              }}
            >
              Delete document
            </button>
          )}
        </div>
        {record.status === "completed" ? (
          <div className="mt-8 border-t border-slate-100 pt-5">
            <h3 className="font-semibold">Extracted text</h3>
            {content?.page === page ? (
              <>
                <div className="mt-4 space-y-5">
                  {content.sections.map((section) => (
                    <article key={section.id}>
                      <h4 className="mb-2 text-xs font-semibold text-indigo-600">
                        {section.label}
                      </h4>
                      <pre className="max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-lg bg-slate-50 p-4 font-sans text-sm leading-7 text-slate-600">
                        {section.text.slice(0, 10000) ||
                          "No text on this page."}
                      </pre>
                      {section.text.length > 10000 && (
                        <p className="mt-1 text-xs text-slate-400">
                          Preview limited to the first 10,000 characters of this
                          source section.
                        </p>
                      )}
                    </article>
                  ))}
                </div>
                <div className="mt-4 flex items-center gap-4 text-xs text-slate-500">
                  <button
                    className="btn-secondary"
                    disabled={page === 1}
                    onClick={() => setPage(page - 1)}
                  >
                    Previous sections
                  </button>
                  <span>
                    Page {page} of{" "}
                    {Math.max(1, Math.ceil(content.total / content.page_size))}
                  </span>
                  <button
                    className="btn-secondary"
                    disabled={page * content.page_size >= content.total}
                    onClick={() => setPage(page + 1)}
                  >
                    Next sections
                  </button>
                </div>
              </>
            ) : (
              <p role="status" className="mt-4 text-sm text-slate-500">
                Loading extracted text…
              </p>
            )}
          </div>
        ) : (
          record.status !== "failed" && (
            <p
              role="status"
              className="mt-6 rounded-lg bg-indigo-50 p-4 text-sm text-indigo-700"
            >
              {record.status === "pending"
                ? "Waiting for the document worker. Processing starts automatically when it is running."
                : "Extracting and organizing source text. This view updates automatically."}
            </p>
          )
        )}
      </div>
    </section>
  );
}
