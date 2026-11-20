import Link from "next/link";
import { Brand, Icon } from "../components/ui";

export default function NotFound() {
  return (
    <main className="recovery-page">
      <Link href="/" aria-label="DocuMind home">
        <Brand />
      </Link>
      <section className="panel">
        <span className="empty-icon">
          <Icon name="search" />
        </span>
        <p className="eyebrow">PAGE NOT FOUND</p>
        <h1>Let’s find your way back.</h1>
        <p>
          This page may have moved, or the address may be incomplete. Your
          workspace is still here.
        </p>
        <div>
          <Link className="btn-primary" href="/dashboard">
            Open workspace <Icon name="arrow" />
          </Link>
          <Link className="btn-secondary" href="/">
            Go home
          </Link>
        </div>
      </section>
    </main>
  );
}
