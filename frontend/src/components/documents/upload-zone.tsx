"use client";

import { useEffect, useRef, useState } from "react";
import { formatBytes, uploadDocument } from "../../lib/documents";

type Transfer = {
  name: string;
  percent: number;
  state: "uploading" | "queued" | "failed" | "canceled";
  error?: string;
};

export function UploadZone({
  organizationId,
  limit,
  onUploaded,
}: {
  organizationId: string;
  limit: number | null;
  onUploaded: () => void;
}) {
  const input = useRef<HTMLInputElement>(null);
  const controller = useRef<AbortController | null>(null);
  const [transfers, setTransfers] = useState<Transfer[]>([]);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => () => controller.current?.abort(), []);

  async function accept(files: File[]) {
    if (busy || !limit) return;
    if (files.length > 10) {
      setError("Choose up to 10 files at a time.");
      return;
    }
    setError("");
    setBusy(true);
    const abort = new AbortController();
    controller.current = abort;
    setTransfers(
      files.map((file) => ({
        name: file.name,
        percent: 0,
        state: "uploading",
      })),
    );
    const update = (index: number, patch: Partial<Transfer>) =>
      setTransfers((items) =>
        items.map((item, i) => (i === index ? { ...item, ...patch } : item)),
      );
    for (const [index, file] of files.entries()) {
      if (abort.signal.aborted) {
        update(index, { state: "canceled" });
        continue;
      }
      if (
        !/\.(pdf|docx|txt)$/i.test(file.name) ||
        file.size === 0 ||
        file.size > limit
      ) {
        update(index, {
          state: "failed",
          error: `Choose a non-empty PDF, DOCX, or TXT up to ${formatBytes(limit)}.`,
        });
        continue;
      }
      try {
        await uploadDocument(
          organizationId,
          file,
          (percent) => update(index, { percent }),
          abort.signal,
        );
        update(index, { percent: 100, state: "queued" });
        onUploaded();
      } catch (error) {
        update(
          index,
          error instanceof DOMException && error.name === "AbortError"
            ? { state: "canceled" }
            : {
                state: "failed",
                error: error instanceof Error ? error.message : "Upload failed",
              },
        );
      }
    }
    setBusy(false);
    controller.current = null;
    if (input.current) input.current.value = "";
  }

  return (
    <section aria-label="Upload documents" className="panel overflow-hidden">
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          void accept(Array.from(event.dataTransfer.files));
        }}
        className={`flex flex-wrap items-center justify-between gap-5 border-2 border-dashed p-6 transition sm:p-8 ${dragging ? "border-indigo-400 bg-indigo-50" : "border-transparent bg-slate-50/50"}`}
      >
        <div className="flex items-center gap-4">
          <span
            aria-hidden="true"
            className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-indigo-50 text-2xl text-indigo-600"
          >
            ↑
          </span>
          <div>
            <h2 className="font-semibold">Bring your documents together</h2>
            <p className="mt-1 text-sm text-slate-500">
              Drop files here, or browse your device.
            </p>
            <p className="mt-2 text-xs text-slate-400">
              PDF, DOCX, TXT ·{" "}
              {limit
                ? `${formatBytes(limit)} maximum per file`
                : "Checking upload limits…"}
            </p>
          </div>
        </div>
        <input
          ref={input}
          aria-label="Document files"
          type="file"
          accept=".pdf,.docx,.txt"
          multiple
          className="sr-only"
          disabled={busy || !limit}
          onChange={(event) =>
            void accept(Array.from(event.target.files ?? []))
          }
        />
        <button
          className="btn-primary"
          disabled={busy || !limit}
          onClick={() => input.current?.click()}
        >
          {busy ? "Uploading…" : "Choose files"}
        </button>
      </div>
      {error && (
        <p role="alert" className="error-box m-4">
          {error}
        </p>
      )}
      {transfers.length > 0 && (
        <div className="border-t border-slate-100 px-6 py-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-medium">Upload activity</h3>
            {busy && (
              <button
                className="text-xs font-medium text-slate-500"
                onClick={() => controller.current?.abort()}
              >
                Cancel uploads
              </button>
            )}
          </div>
          <ul className="space-y-3">
            {transfers.map((transfer, index) => (
              <li key={index} className="text-sm">
                <div className="flex justify-between gap-4">
                  <span className="truncate">{transfer.name}</span>
                  <span
                    role="status"
                    className={
                      transfer.state === "failed"
                        ? "text-rose-600"
                        : "text-slate-500"
                    }
                  >
                    {transfer.state === "uploading"
                      ? transfer.percent === 100
                        ? "Saving…"
                        : `${transfer.percent}%`
                      : transfer.state === "queued"
                        ? "Queued for processing"
                        : transfer.state === "canceled"
                          ? "Canceled"
                          : "Failed"}
                  </span>
                </div>
                {transfer.state === "uploading" && (
                  <progress
                    className="mt-2 h-1.5 w-full accent-indigo-600"
                    max={100}
                    value={transfer.percent}
                    aria-label={`Upload progress for ${transfer.name}`}
                  />
                )}
                {transfer.error && (
                  <p role="alert" className="mt-1 text-xs text-rose-600">
                    {transfer.error}
                  </p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
