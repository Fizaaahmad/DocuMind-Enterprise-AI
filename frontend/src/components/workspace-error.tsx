"use client";

import Link from "next/link";
import { Brand, Icon } from "./ui";

export function WorkspaceError({ reset }: { reset: () => void }) {
  return (
    <main className="recovery-page">
      <Link href="/" aria-label="DocuMind home">
        <Brand />
      </Link>
      <section className="panel">
        <span className="empty-icon">
          <Icon name="activity" />
        </span>
        <p className="eyebrow">LET’S GET YOU BACK ON TRACK</p>
        <h1>Workspace temporarily unavailable</h1>
        <p>
          Your information has not been changed. Please retry, or check service
          availability if the problem continues.
        </p>
        <div>
          <button className="btn-primary" onClick={reset}>
            Try again <Icon name="arrow" />
          </button>
          <Link className="btn-secondary" href="/">
            System status
          </Link>
        </div>
        <Link className="text-xs text-indigo-600" href="/login">
          Return to sign in
        </Link>
      </section>
    </main>
  );
}
