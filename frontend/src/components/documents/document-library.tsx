"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../../lib/api";
import { DocumentList, DocumentRecord, formatBytes } from "../../lib/documents";
import type { Organization, User } from "../../lib/types";
import { DocumentDetails } from "./document-details";
import { UploadZone } from "./upload-zone";

const statusColors = {
  pending: "bg-slate-100 text-slate-600",
  processing: "bg-indigo-50 text-indigo-700",
  completed: "bg-emerald-50 text-emerald-700",
  failed: "bg-rose-50 text-rose-700",
};

function DocumentWorkspace({
  organization,
  user,
}: {
  organization: Organization;
  user: User;
}) {
  const [data, setData] = useState<DocumentList | null>(null);
  const [limit, setLimit] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState("");
  const [status, setStatus] = useState("");
  const [format, setFormat] = useState("");
  const [sort, setSort] = useState("newest");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<DocumentRecord | null>(null);
  const base = `/organizations/${organization.id}/documents`;
  const params = new URLSearchParams({
    q: query,
    sort,
    page: String(page),
    ...(status ? { status } : {}),
    ...(format ? { format } : {}),
  }).toString();
  const [loadedQuery, setLoadedQuery] = useState("");
  const loading = loadedQuery !== params;
  const router = useRouter();
  const report = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 401) {
        router.replace("/login");
        return;
      }
      setError(
        error instanceof Error ? error.message : "Unable to load documents",
      );
    },
    [router],
  );
  const refresh = useCallback(() => {
    void api<DocumentList>(`${base}?${params}`)
      .then((items) => {
        setData(items);
        setLoadedQuery(params);
      })
      .catch(report);
  }, [base, params, report]);

  useEffect(() => {
    let active = true;
    api<{ upload_max_bytes: number }>(`${base}/config`)
      .then((config) => {
        if (active) setLimit(config.upload_max_bytes);
      })
      .catch((error) => {
        if (active) report(error);
      });
    return () => {
      active = false;
    };
  }, [base, report]);
  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    const load = () =>
      api<DocumentList>(`${base}?${params}`, { signal: controller.signal })
        .then((items) => {
          if (active) {
            setData(items);
            setLoadedQuery(params);
          }
        })
        .catch((error) => {
          if (active) {
            setLoadedQuery(params);
            report(error);
          }
        });
    void load();
    const timer = setInterval(() => {
      if (document.visibilityState !== "hidden") void load();
    }, 3000);
    return () => {
      active = false;
      controller.abort();
      clearInterval(timer);
    };
  }, [base, params, report]);

  return (
    <>
      <UploadZone
        organizationId={organization.id}
        limit={limit}
        onUploaded={refresh}
      />
      <section
        className="panel mt-6 overflow-hidden"
        aria-labelledby="library-title"
      >
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 p-6">
          <div>
            <h2 id="library-title" className="text-lg font-semibold">
              Document library
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              {data?.total ?? 0} documents · {organization.name}
            </p>
          </div>
          <button
            className="btn-secondary"
            onClick={() => {
              setError("");
              refresh();
            }}
          >
            Refresh library
          </button>
        </div>
        <div className="flex flex-wrap items-end gap-3 border-b border-slate-100 bg-slate-50/50 p-4 sm:px-6">
          <form
            className="flex min-w-48 flex-1 gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              setQuery(draft);
              setPage(1);
            }}
          >
            <label className="sr-only" htmlFor="document-search">
              Search documents
            </label>
            <input
              id="document-search"
              className="input mt-0"
              value={draft}
              maxLength={180}
              placeholder="Search by filename…"
              onChange={(event) => setDraft(event.target.value)}
            />
            <button className="btn-secondary">Search</button>
          </form>
          <select
            aria-label="Filter by status"
            className="input mt-0 w-auto"
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
          <select
            aria-label="Filter by file type"
            className="input mt-0 w-auto"
            value={format}
            onChange={(event) => {
              setFormat(event.target.value);
              setPage(1);
            }}
          >
            <option value="">All types</option>
            <option value="pdf">PDF</option>
            <option value="docx">DOCX</option>
            <option value="txt">TXT</option>
          </select>
          <select
            aria-label="Sort documents"
            className="input mt-0 w-auto"
            value={sort}
            onChange={(event) => {
              setSort(event.target.value);
              setPage(1);
            }}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="name">Filename</option>
          </select>
        </div>
        {error && (
          <p role="alert" className="error-box m-5">
            {error}
          </p>
        )}
        {loading ? (
          <p role="status" className="p-10 text-center text-sm text-slate-500">
            Loading documents…
          </p>
        ) : !data?.items.length ? (
          <div className="px-6 py-14 text-center">
            <div
              aria-hidden="true"
              className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl bg-slate-100 text-xl text-slate-400"
            >
              ▤
            </div>
            <h3 className="font-medium">
              {query || status || format
                ? "No matching documents"
                : "Your library is ready"}
            </h3>
            <p className="mt-2 text-sm text-slate-500">
              {query || status || format
                ? "Adjust your search or filters to see more files."
                : "Upload your first document to extract and organize its text."}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-slate-100 text-xs text-slate-400">
                <tr>
                  <th className="px-6 py-3 font-medium">Document</th>
                  <th className="px-4 py-3 font-medium">Status</th>
                  <th className="px-4 py-3 font-medium">Size</th>
                  <th className="px-4 py-3 font-medium">Sources / chunks</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-50/70">
                    <td className="max-w-xs px-6 py-4">
                      <button
                        className="flex items-center gap-3 text-left focus-visible:outline-indigo-600"
                        onClick={() => setSelected(item)}
                      >
                        <span
                          aria-hidden="true"
                          className="rounded-lg bg-indigo-50 px-2.5 py-3 text-[10px] font-bold text-indigo-600"
                        >
                          {item.format.toUpperCase()}
                        </span>
                        <span className="min-w-0">
                          <span className="block break-words font-medium text-slate-900">
                            {item.filename}
                          </span>
                          <span className="mt-1 block text-xs text-slate-400">
                            View details & extracted text
                          </span>
                        </span>
                      </button>
                    </td>
                    <td className="px-4 py-4">
                      <span
                        className={`rounded-full px-2.5 py-1 text-xs font-medium capitalize ${statusColors[item.status]}`}
                      >
                        {item.status === "processing" && (
                          <span className="mr-1 inline-block animate-pulse">
                            ●
                          </span>
                        )}
                        {item.status}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-4 py-4 text-slate-500">
                      {formatBytes(item.size_bytes)}
                    </td>
                    <td className="px-4 py-4 text-slate-500">
                      {item.section_count} / {item.chunk_count}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className="flex items-center justify-between border-t border-slate-100 px-6 py-4 text-xs text-slate-500">
          <span>
            Page {page} of {Math.max(1, Math.ceil((data?.total ?? 0) / 20))}
          </span>
          <div className="flex gap-2">
            <button
              className="btn-secondary"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </button>
            <button
              className="btn-secondary"
              disabled={page * 20 >= (data?.total ?? 0)}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </div>
      </section>
      {selected && (
        <DocumentDetails
          key={selected.id}
          initial={selected}
          organizationId={organization.id}
          canManage={
            organization.role === "admin" || selected.uploader_id === user.id
          }
          onClose={() => setSelected(null)}
          onChange={refresh}
        />
      )}
    </>
  );
}

export function DocumentLibrary({
  user,
  initialOrganization,
}: {
  user: User;
  initialOrganization?: string;
}) {
  const [organizations, setOrganizations] = useState<Organization[] | null>(
    null,
  );
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
      .catch((error) => {
        if (active) setError(error.message);
      });
    return () => {
      active = false;
    };
  }, [initialOrganization]);
  const organization = organizations?.find((item) => item.id === selected);
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <Link href="/dashboard" className="text-xl font-bold tracking-tight">
            DocuMind<span className="text-indigo-600">.</span>
          </Link>
          <div className="flex items-center gap-4">
            <Link className="text-sm text-slate-500" href="/">
              System status
            </Link>
            <Link className="btn-secondary" href="/dashboard">
              Team & access
            </Link>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-10">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-5">
          <div>
            <p className="eyebrow">Organization knowledge</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight">
              Your documents, organized.
            </h1>
            <p className="mt-3 text-sm text-slate-500">
              A secure home for source files and extracted content.
            </p>
          </div>
          {organizations && organizations.length > 0 && (
            <label className="field-label min-w-56">
              Active organization
              <select
                aria-label="Active organization"
                className="input"
                value={selected}
                onChange={(event) => setSelected(event.target.value)}
              >
                {organizations.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          )}
        </div>
        {error && (
          <p role="alert" className="error-box mb-6">
            {error}
          </p>
        )}
        {organization ? (
          <DocumentWorkspace
            key={organization.id}
            organization={organization}
            user={user}
          />
        ) : organizations?.length === 0 ? (
          <section className="panel p-10 text-center">
            <h2 className="text-lg font-semibold">Create a workspace first</h2>
            <p className="my-4 text-sm text-slate-500">
              Documents belong to an organization. Create one or ask an Admin to
              add you.
            </p>
            <Link className="btn-primary" href="/dashboard">
              Manage organizations
            </Link>
          </section>
        ) : (
          !error && (
            <p role="status" className="text-slate-500">
              Loading your organizations…
            </p>
          )
        )}
      </main>
    </div>
  );
}
