import Link from "next/link";
import { SystemStatus } from "../components/system-status";

export default function Home() {
  return (
    <div className="min-h-screen text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-5">
          <Link
            href="/"
            className="flex items-center gap-3 text-xl font-bold tracking-tight"
          >
            <span
              aria-hidden="true"
              className="grid h-9 w-9 place-items-center rounded-lg bg-indigo-600 text-lg text-white"
            >
              D
            </span>
            DocuMind
          </Link>
          <div className="flex items-center gap-3">
            <Link className="text-sm font-medium text-slate-600" href="/login">
              Sign in
            </Link>
            <Link className="btn-primary" href="/dashboard">
              Workspace
            </Link>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-6 py-12 sm:py-16">
        <p className="text-xs font-semibold uppercase tracking-widest text-indigo-600">
          Development workspace
        </p>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
          Your foundation, connected.
        </h1>
        <p className="mb-10 mt-4 max-w-2xl leading-7 text-slate-500">
          The starting point for document intelligence. Check the services
          powering your DocuMind workspace before building the next layer.
        </p>
        <SystemStatus />
        <div className="mt-8 flex flex-wrap justify-between gap-3 text-xs text-slate-500">
          <p>Next.js + FastAPI + PostgreSQL</p>
          <p>Secure organizations and team access · Phase 2</p>
        </div>
      </main>
    </div>
  );
}
