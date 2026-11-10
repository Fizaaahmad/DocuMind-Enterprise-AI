"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "../lib/api";
import type { Member, Organization, User } from "../lib/types";

export function Dashboard({ user }: { user: User }) {
  const router = useRouter();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selected, setSelected] = useState("");
  const [members, setMembers] = useState<Member[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadedOrganization, setLoadedOrganization] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const membersLoading = Boolean(selected && loadedOrganization !== selected);
  const org = organizations.find((item) => item.id === selected);

  const handleError = useCallback(
    (error: unknown) => {
      if (error instanceof ApiError && error.status === 401) {
        router.replace("/login");
        return;
      }
      setError(
        error instanceof Error
          ? error.message
          : "Unable to complete the request.",
      );
    },
    [router],
  );

  const loadOrganizations = useCallback(async () => {
    const items = await api<Organization[]>("/organizations");
    setOrganizations(items);
    setSelected((current) =>
      items.some((item) => item.id === current)
        ? current
        : (items[0]?.id ?? ""),
    );
    return items;
  }, []);

  useEffect(() => {
    let active = true;
    api<Organization[]>("/organizations")
      .then((items) => {
        if (!active) return;
        setOrganizations(items);
        setSelected(items[0]?.id ?? "");
      })
      .catch((error) => {
        if (active) handleError(error);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [handleError]);

  useEffect(() => {
    let active = true;
    if (!selected) return;
    api<Member[]>(`/organizations/${selected}/members`)
      .then((items) => {
        if (active) {
          setMembers(items);
          setLoadedOrganization(selected);
        }
      })
      .catch((error) => {
        if (active) {
          setMembers([]);
          setLoadedOrganization(selected);
          handleError(error);
        }
      });
    return () => {
      active = false;
    };
  }, [selected, handleError]);

  async function mutate(action: () => Promise<void>, success: string) {
    if (pending) return;
    setPending(true);
    setError("");
    setNotice("");
    try {
      await action();
      setNotice(success);
    } catch (error) {
      handleError(error);
    } finally {
      setPending(false);
    }
  }

  async function reloadMembers(id: string) {
    const organizations = await loadOrganizations();
    if (!organizations.some((item) => item.id === id)) {
      setMembers([]);
      setLoadedOrganization("");
      return;
    }
    const items = await api<Member[]>(`/organizations/${id}/members`);
    setMembers(items);
    setLoadedOrganization(id);
  }

  function createOrganization(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const name = new FormData(form).get("name");
    void mutate(async () => {
      const created = await api<Organization>("/organizations", {
        method: "POST",
        body: JSON.stringify({ name }),
      });
      await loadOrganizations();
      setSelected(created.id);
      form.reset();
    }, "Organization created. You are its Admin.");
  }

  function addMember(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    void mutate(async () => {
      await api(`/organizations/${selected}/members`, {
        method: "POST",
        body: JSON.stringify({
          email: data.get("email"),
          role: data.get("role"),
        }),
      });
      await reloadMembers(selected);
      form.reset();
    }, "Member added.");
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-6 py-5">
          <Link href="/dashboard" className="text-xl font-bold tracking-tight">
            DocuMind<span className="text-indigo-600">.</span>
          </Link>
          <div className="flex items-center gap-4">
            <Link
              className="btn-primary"
              href={
                selected ? `/documents?organization=${selected}` : "/documents"
              }
            >
              Documents
            </Link>
            <Link
              className="text-sm text-slate-500 hover:text-indigo-600"
              href="/"
            >
              System status
            </Link>
            <button
              className="btn-secondary"
              disabled={pending}
              onClick={() =>
                void mutate(async () => {
                  await api("/auth/logout", { method: "POST" });
                  router.replace("/login");
                  router.refresh();
                }, "Signed out.")
              }
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-6 py-10">
        <p className="eyebrow">Workspace overview</p>
        <h1 className="mt-3 text-3xl font-semibold tracking-tight">
          Welcome, {user.name}
        </h1>
        <p className="mt-3 text-sm text-slate-500">
          Manage your organizations and the people who belong to them.
        </p>
        {error && (
          <p role="alert" className="error-box mt-6">
            {error}
          </p>
        )}
        {notice && (
          <p
            role="status"
            className="mt-6 rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-800"
          >
            {notice}
          </p>
        )}
        <div className="mt-8 grid gap-8 lg:grid-cols-[280px_1fr]">
          <aside className="space-y-6">
            <section className="panel p-5">
              <h2 className="text-sm font-semibold">Your organizations</h2>
              {loading ? (
                <p role="status" className="mt-4 text-sm text-slate-500">
                  Loading organizations…
                </p>
              ) : organizations.length === 0 ? (
                <p className="mt-4 text-sm leading-6 text-slate-500">
                  No organizations yet. Create your first workspace below, or
                  ask an Admin to add your registered email.
                </p>
              ) : (
                <label className="field-label mt-4">
                  Active organization
                  <select
                    aria-label="Active organization"
                    className="input"
                    value={selected}
                    disabled={pending}
                    onChange={(event) => {
                      setSelected(event.target.value);
                      setError("");
                      setNotice("");
                    }}
                  >
                    {organizations.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </label>
              )}
            </section>
            <section className="panel p-5">
              <h2 className="text-sm font-semibold">Create an organization</h2>
              <form onSubmit={createOrganization} className="mt-4 space-y-4">
                <label className="field-label">
                  Organization name
                  <input
                    className="input"
                    name="name"
                    maxLength={100}
                    required
                    disabled={pending}
                    placeholder="e.g. Acme Research"
                  />
                </label>
                <button
                  className="btn-primary w-full"
                  disabled={pending || loading}
                >
                  Create organization
                </button>
              </form>
            </section>
            <p className="break-all px-1 text-xs leading-5 text-slate-400">
              Signed in as
              <br />
              <span className="text-slate-600">{user.email}</span>
            </p>
          </aside>
          <section className="panel overflow-hidden">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-6 py-6">
              <div>
                <p className="eyebrow">People & access</p>
                <h2 className="mt-2 text-xl font-semibold">
                  {org?.name ?? "Your team starts here"}
                </h2>
              </div>
              {org && (
                <span className="badge">
                  {org.role === "admin" ? "Organization Admin" : "Member"}
                </span>
              )}
            </div>
            {!org ? (
              <div className="px-6 py-16 text-center">
                <div
                  aria-hidden="true"
                  className="mx-auto mb-5 grid h-14 w-14 place-items-center rounded-2xl bg-indigo-50 text-2xl text-indigo-600"
                >
                  ◎
                </div>
                <h3 className="font-medium">
                  A dedicated space for every team
                </h3>
                <p className="mx-auto mt-3 max-w-sm text-sm leading-6 text-slate-500">
                  Create or select an organization to view its members. Each
                  organization has its own roles and access boundaries.
                </p>
              </div>
            ) : (
              <>
                {org.role === "admin" ? (
                  <form
                    onSubmit={addMember}
                    className="grid gap-4 border-b border-slate-100 bg-slate-50/60 p-6 sm:grid-cols-[1fr_130px_auto] sm:items-end"
                  >
                    <label className="field-label">
                      Add a registered user
                      <input
                        className="input"
                        type="email"
                        name="email"
                        placeholder="colleague@company.com"
                        required
                        disabled={pending}
                      />
                    </label>
                    <label className="field-label">
                      Role
                      <select name="role" className="input" disabled={pending}>
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                      </select>
                    </label>
                    <button className="btn-primary" disabled={pending}>
                      Add member
                    </button>
                    <p className="text-xs text-slate-500 sm:col-span-3">
                      The user must create an account first. No invitation email
                      is sent.
                    </p>
                  </form>
                ) : (
                  <p className="border-b border-slate-100 bg-slate-50 px-6 py-4 text-sm text-slate-500">
                    You can view this team. Only organization Admins can manage
                    membership.
                  </p>
                )}
                {membersLoading ? (
                  <p role="status" className="p-6 text-sm text-slate-500">
                    Loading team members…
                  </p>
                ) : (
                  <ul className="divide-y divide-slate-100">
                    {members.map((member) => (
                      <li
                        key={member.user_id}
                        className="flex flex-wrap items-center justify-between gap-4 px-6 py-5"
                      >
                        <div className="flex min-w-0 items-center gap-3">
                          <span
                            aria-hidden="true"
                            className="grid h-10 w-10 shrink-0 place-items-center rounded-full bg-indigo-50 font-semibold text-indigo-600"
                          >
                            {member.name.slice(0, 1).toUpperCase()}
                          </span>
                          <div className="min-w-0">
                            <p className="font-medium">
                              {member.name}
                              {member.user_id === user.id && (
                                <span className="ml-2 text-xs text-slate-400">
                                  You
                                </span>
                              )}
                            </p>
                            <p className="break-all text-sm text-slate-500">
                              {member.email}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-3">
                          {org.role === "admin" ? (
                            <>
                              <select
                                aria-label={`Role for ${member.name}`}
                                className="input mt-0 w-28"
                                value={member.role}
                                disabled={pending}
                                onChange={(event) => {
                                  const role = event.target.value;
                                  void mutate(async () => {
                                    await api(
                                      `/organizations/${selected}/members/${member.user_id}`,
                                      {
                                        method: "PATCH",
                                        body: JSON.stringify({ role }),
                                      },
                                    );
                                    await reloadMembers(selected);
                                  }, "Role updated.");
                                }}
                              >
                                <option value="member">Member</option>
                                <option value="admin">Admin</option>
                              </select>
                              <button
                                className="rounded-md px-2 py-2 text-xs font-medium text-rose-600 hover:bg-rose-50 disabled:opacity-50"
                                disabled={pending}
                                onClick={() => {
                                  if (
                                    window.confirm(
                                      `Remove ${member.name} from ${org.name}?`,
                                    )
                                  )
                                    void mutate(async () => {
                                      await api(
                                        `/organizations/${selected}/members/${member.user_id}`,
                                        { method: "DELETE" },
                                      );
                                      await reloadMembers(selected);
                                    }, "Member removed.");
                                }}
                              >
                                Remove
                              </button>
                            </>
                          ) : (
                            <span className="badge">
                              {member.role === "admin" ? "Admin" : "Member"}
                            </span>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </section>
        </div>
      </main>
    </div>
  );
}
