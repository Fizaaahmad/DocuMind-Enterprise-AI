"use client";

import Link from "next/link";

export default function DashboardError({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto max-w-lg px-6 py-24">
      <h1 className="text-2xl font-semibold">
        Workspace temporarily unavailable
      </h1>
      <p className="my-5 text-slate-500">
        Check that the backend is running, then try again.
      </p>
      <div className="flex gap-4">
        <button className="btn-primary" onClick={reset}>
          Try again
        </button>
        <Link className="btn-secondary" href="/">
          System status
        </Link>
      </div>
    </main>
  );
}
