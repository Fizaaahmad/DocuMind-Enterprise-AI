"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import type { User } from "../lib/types";
import { Brand, Dialog, Icon, type IconName } from "./ui";
import { api } from "../lib/api";

const navigation: {
  id: IconName;
  label: string;
  href: string;
  group: string;
}[] = [
  { id: "overview", label: "Overview", href: "/dashboard", group: "Workspace" },
  {
    id: "documents",
    label: "Documents",
    href: "/documents",
    group: "Workspace",
  },
  {
    id: "assistant",
    label: "AI Assistant",
    href: "/assistant",
    group: "Workspace",
  },
  {
    id: "intelligence",
    label: "Document Intelligence",
    href: "/intelligence",
    group: "Intelligence & workflows",
  },
  {
    id: "operations",
    label: "Enterprise Operations",
    href: "/operations",
    group: "Intelligence & workflows",
  },
  {
    id: "team",
    label: "Team & access",
    href: "/dashboard#team",
    group: "Administration",
  },
];

export function WorkspaceShell({
  active,
  title,
  description,
  organizationId,
  organizationSelector,
  user,
  actions,
  children,
}: {
  active: IconName;
  title: string;
  description: string;
  organizationId?: string;
  organizationSelector?: ReactNode;
  user?: User;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const [menu, setMenu] = useState(false);
  const router = useRouter();
  const [account, setAccount] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [accountError, setAccountError] = useState("");
  useEffect(() => {
    if (organizationId) {
      try {
        sessionStorage.setItem("documind.organization", organizationId);
      } catch {
        /* Private browsing can disable storage. */
      }
    }
  }, [organizationId]);
  function href(path: string) {
    const [base, anchor] = path.split("#");
    return `${base}${organizationId ? `?organization=${encodeURIComponent(organizationId)}` : ""}${anchor ? `#${anchor}` : ""}`;
  }
  const links = (
    <>
      {navigation.map((item, i) => (
        <div key={item.id}>
          {navigation[i - 1]?.group !== item.group && (
            <p className="nav-group-label">{item.group}</p>
          )}
          <Link
            className={`nav-link ${active === item.id ? "nav-link-active" : ""}`}
            aria-current={active === item.id ? "page" : undefined}
            href={href(item.href)}
            onClick={() => setMenu(false)}
          >
            <Icon name={item.id} />
            <span>{item.label}</span>
            {item.id === "assistant" && <span className="nav-ai">AI</span>}
          </Link>
        </div>
      ))}
    </>
  );
  return (
    <div className={`workspace-shell workspace-${active}`}>
      <a className="skip-link" href="#workspace-content">
        Skip to main content
      </a>
      <aside className="app-sidebar">
        <Link href={href("/dashboard")} aria-label="DocuMind overview">
          <Brand />
        </Link>
        <nav aria-label="Main navigation">{links}</nav>
        <div className="sidebar-bottom">
          <div className="sidebar-note">
            <Icon name="shield" />
            <span>
              Evidence first.
              <br />
              <strong>Decisions with confidence.</strong>
            </span>
          </div>
          <Link href="/" className="nav-link">
            <Icon name="activity" />
            System status
          </Link>
        </div>
      </aside>
      <div className="workspace-body">
        <header className="app-topbar">
          <div className="flex min-w-0 items-center gap-3">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMenu(true)}
            >
              <Icon name="menu" />
            </button>
            <span className="topbar-breadcrumb">
              Workspace <span>/</span> <strong>{title}</strong>
            </span>
          </div>
          <div className="topbar-controls">
            {organizationSelector}
            <button
              type="button"
              className="user-avatar"
              title={user?.email ?? "Your account"}
              aria-label="Open account menu"
              onClick={() => setAccount(true)}
            >
              {user?.name.slice(0, 1).toUpperCase() ?? <Icon name="shield" />}
            </button>
          </div>
        </header>
        <main id="workspace-content" className="workspace-content">
          <div className="page-heading">
            <div>
              <p className="eyebrow">DOCUMIND WORKSPACE</p>
              <h1>{title}</h1>
              <p className="page-description">{description}</p>
            </div>
            {actions && <div className="page-actions">{actions}</div>}
          </div>
          {children}
        </main>
        <footer className="workspace-footer">
          <span>DocuMind · Document intelligence & operations</span>
          <span>Source-grounded. Human-reviewed.</span>
        </footer>
      </div>
      {menu && (
        <Dialog title="Workspace navigation" onClose={() => setMenu(false)}>
          <Link href={href("/dashboard")}>
            <Brand />
          </Link>
          <nav className="mobile-navigation" aria-label="Mobile navigation">
            {links}
          </nav>
          <button
            className="btn-secondary mt-5 w-full"
            onClick={() => {
              setMenu(false);
              setAccount(true);
            }}
          >
            Your account
          </button>
        </Dialog>
      )}
      {account && (
        <Dialog title="Your account" onClose={() => setAccount(false)}>
          <p className="text-lg font-semibold">
            {user?.name ?? "Your workspace"}
          </p>
          {user?.email && (
            <p className="mt-1 break-all text-sm text-slate-500">
              {user.email}
            </p>
          )}
          <p className="mt-4 text-xs leading-6 text-slate-500">
            Organization access is managed by your team Admin. Switching
            organizations keeps their documents and workflows separate.
          </p>
          {accountError && (
            <p role="alert" className="error-box mt-4">
              {accountError}
            </p>
          )}
          <div className="dialog-actions">
            <Link
              className="btn-secondary"
              href={href("/dashboard#team")}
              onClick={() => setAccount(false)}
            >
              Team & access
            </Link>
            <button
              className="btn-primary"
              disabled={signingOut}
              onClick={async () => {
                setSigningOut(true);
                setAccountError("");
                try {
                  await api("/auth/logout", { method: "POST" });
                  try {
                    sessionStorage.removeItem("documind.organization");
                  } catch {
                    /* UI preference only. */
                  }
                  router.replace("/login");
                  router.refresh();
                } catch {
                  setAccountError("Unable to sign out. Please try again.");
                  setSigningOut(false);
                }
              }}
            >
              {signingOut ? "Signing out…" : "Sign out"}
              <Icon name="logout" />
            </button>
          </div>
        </Dialog>
      )}
    </div>
  );
}
