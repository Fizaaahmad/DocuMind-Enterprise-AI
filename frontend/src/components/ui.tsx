"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

export type IconName =
  | "overview"
  | "documents"
  | "assistant"
  | "intelligence"
  | "operations"
  | "team"
  | "arrow"
  | "upload"
  | "search"
  | "check"
  | "close"
  | "menu"
  | "shield"
  | "clock"
  | "activity"
  | "quote"
  | "plus"
  | "logout";
const paths: Record<IconName, ReactNode> = {
  overview: (
    <>
      <rect x="3" y="3" width="7" height="7" rx="1.5" />
      <rect x="14" y="3" width="7" height="7" rx="1.5" />
      <rect x="3" y="14" width="7" height="7" rx="1.5" />
      <rect x="14" y="14" width="7" height="7" rx="1.5" />
    </>
  ),
  documents: (
    <>
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z" />
      <path d="M14 3v6h6M8 13h8M8 17h5" />
    </>
  ),
  assistant: (
    <>
      <path d="m12 3 2.5 6.5L21 12l-6.5 2.5L12 21l-2.5-6.5L3 12l6.5-2.5Z" />
      <path d="m20 2 1 3 3 1-3 1-1 3-1-3-3-1 3-1Z" />
    </>
  ),
  intelligence: (
    <>
      <path d="M9 3H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-4M8 8h4M8 12h3M8 16h8" />
      <path d="m16 3 5 5-5 5-5-5Z" />
    </>
  ),
  operations: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 5V3h8v2M3 11h18M9 11v3h6v-3" />
    </>
  ),
  team: (
    <>
      <circle cx="9" cy="7" r="3" />
      <path d="M3 21v-3a6 6 0 0 1 12 0v3M16 4a3 3 0 0 1 0 6M21 21v-3a6 6 0 0 0-4-5" />
    </>
  ),
  arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
  upload: <path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5" />,
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 5 5" />
    </>
  ),
  check: <path d="m5 12 4 4L19 6" />,
  close: <path d="m6 6 12 12M6 18 18 6" />,
  menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  shield: (
    <>
      <path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z" />
      <path d="m8 12 3 3 5-6" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </>
  ),
  activity: <path d="M2 12h5l3-8 4 16 3-8h5" />,
  quote: (
    <>
      <path d="M4 5h6v7H4ZM14 5h6v7h-6ZM10 12c0 5-3 7-6 7M20 12c0 5-3 7-6 7" />
    </>
  ),
  plus: <path d="M12 5v14M5 12h14" />,
  logout: (
    <>
      <path d="M9 4H4v16h5M10 12h11m-4-4 4 4-4 4" />
    </>
  ),
};

export function Icon({
  name,
  className = "",
}: {
  name: IconName;
  className?: string;
}) {
  return (
    <svg
      className={`icon ${className}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {paths[name]}
    </svg>
  );
}

export function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <span className="brand">
      <span className="brand-symbol">
        <svg viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <path
            d="m7 8 9-4 9 4-9 4-9-4Zm0 7 9 4 9-4M7 22l9 4 9-4"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </span>
      {!compact && (
        <span>
          Docu<span className="brand-accent">Mind</span>
        </span>
      )}
    </span>
  );
}

export function StatusBadge({ value }: { value: string }) {
  const tone =
    /completed|approved|valid$/.test(value) && !/invalid/.test(value)
      ? "success"
      : /failed|rejected|high|overdue/.test(value)
        ? "danger"
        : /pending|processing|medium|candidate|corrected/.test(value)
          ? "warning"
          : "neutral";
  return (
    <span className={`status-badge status-${tone}`}>
      <span className="status-dot" />
      {value.replaceAll("_", " ")}
    </span>
  );
}

export function EmptyState({
  icon = "documents",
  title,
  children,
}: {
  icon?: IconName;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty-state">
      <span className="empty-icon">
        <Icon name={icon} />
      </span>
      <h3>{title}</h3>
      <div className="empty-description">{children}</div>
    </div>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="skeleton-group" role="status" aria-label="Loading content">
      <span className="sr-only">Loading…</span>
      {Array.from({ length: rows }, (_, i) => (
        <div
          key={i}
          className="skeleton"
          style={{ width: `${100 - (i % 3) * 12}%` }}
        />
      ))}
    </div>
  );
}

export function Dialog({
  title,
  children,
  onClose,
  wide = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const close = useRef(onClose);
  useEffect(() => {
    close.current = onClose;
  }, [onClose]);
  useEffect(() => {
    const node = ref.current;
    const previous =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : null;
    if (typeof node?.showModal === "function") node.showModal();
    else node?.setAttribute("open", "");
    return () => {
      node?.close?.();
      previous?.focus();
    };
  }, []);
  return (
    <dialog
      ref={ref}
      className={`workspace-dialog ${wide ? "dialog-wide" : ""}`}
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        close.current();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          const rect = e.currentTarget.getBoundingClientRect();
          if (
            e.clientX < rect.left ||
            e.clientX > rect.right ||
            e.clientY < rect.top ||
            e.clientY > rect.bottom
          )
            close.current();
        }
      }}
    >
      <div className="dialog-header">
        <h2>{title}</h2>
        <button
          type="button"
          className="icon-button"
          aria-label={`Close ${title}`}
          onClick={onClose}
        >
          <Icon name="close" />
        </button>
      </div>
      <div className="dialog-body">{children}</div>
    </dialog>
  );
}

export function useConfirmation() {
  const [request, setRequest] = useState<{
    title: string;
    message: string;
    resolve: (result: boolean) => void;
  } | null>(null);
  const pending = useRef<((result: boolean) => void) | null>(null);
  useEffect(() => () => pending.current?.(false), []);
  function finish(result: boolean) {
    pending.current?.(result);
    pending.current = null;
    setRequest(null);
  }
  return {
    confirm: (title: string, message: string) =>
      new Promise<boolean>((resolve) => {
        pending.current = resolve;
        setRequest({ title, message, resolve });
      }),
    confirmation: request && (
      <Dialog title={request.title} onClose={() => finish(false)}>
        <p className="text-sm leading-6 text-slate-600">{request.message}</p>
        <div className="dialog-actions">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => finish(false)}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn-danger"
            onClick={() => finish(true)}
          >
            Confirm removal
          </button>
        </div>
      </Dialog>
    ),
  };
}

export function displayValue(value: unknown): string {
  if (value == null || value === "") return "Not established";
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (Array.isArray(value)) return value.map(displayValue).join(" · ");
  if (typeof value === "object") {
    const data = value as Record<string, unknown>;
    if ("currency" in data && "amount" in data) {
      const [integer, fraction] = String(data.amount).split(".");
      const formatted =
        integer.replace(/\B(?=(\d{3})+(?!\d))/g, ",") +
        (fraction === undefined ? "" : `.${fraction}`);
      return `${String(data.currency)} ${formatted}`;
    }
    return Object.entries(data)
      .filter(([key]) => key !== "evidence")
      .map(
        ([key, item]) => `${key.replaceAll("_", " ")}: ${displayValue(item)}`,
      )
      .join("; ");
  }
  return String(value);
}

export function BusinessValues({
  value,
  corrected = false,
}: {
  value: Record<string, unknown>;
  corrected?: boolean;
}) {
  const visible = Object.entries(value).filter(
    ([key]) =>
      ![
        "evidence",
        "type",
        "required",
        "provenance",
        "review_required",
        "rule",
      ].includes(key),
  );
  return (
    <div className={`business-values ${corrected ? "values-corrected" : ""}`}>
      <dl>
        {visible.map(([key, item]) => (
          <div key={key}>
            <dt>
              {key === "value"
                ? "Extracted value"
                : key === "note"
                  ? "Review note"
                  : key === "raw"
                    ? "Original text"
                    : key === "candidates"
                      ? "Possible values"
                      : key.replaceAll("_", " ")}
            </dt>
            <dd>{displayValue(item)}</dd>
          </div>
        ))}
      </dl>
      {value.provenance === "configured_rule" && (
        <span className="status-badge status-neutral">Configured rule</span>
      )}
      <details className="technical-details">
        <summary>Original data & provenance</summary>
        <pre>{JSON.stringify(value, null, 2)}</pre>
      </details>
    </div>
  );
}
