import Link from "next/link";
import { SystemStatus } from "../components/system-status";
import { Brand, Icon } from "../components/ui";

export default function Home() {
  return (
    <div className="public-home">
      <header className="public-header">
        <Link href="/" aria-label="DocuMind home">
          <Brand />
        </Link>
        <nav aria-label="Public navigation">
          <a href="#system-status" className="public-status-link">
            System status
          </a>
          <Link href="/login" className="btn-secondary">
            Sign in
          </Link>
          <Link href="/dashboard" className="btn-primary">
            Open workspace <Icon name="arrow" />
          </Link>
        </nav>
      </header>
      <main>
        <section className="public-hero">
          <div>
            <p className="eyebrow">ENTERPRISE DOCUMENT INTELLIGENCE</p>
            <h1>
              Your knowledge.
              <br />
              <span>Your next advantage.</span>
            </h1>
            <p>
              Turn complex documents into grounded answers, clear insights and
              accountable action. One workspace for the information your
              business runs on.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link href="/signup" className="btn-primary">
                Create your workspace <Icon name="arrow" />
              </Link>
              <Link href="/login" className="btn-secondary">
                Sign in to DocuMind
              </Link>
            </div>
            <p className="public-hero-note">
              <Icon name="shield" />
              Source-grounded intelligence. Human-reviewed decisions.
            </p>
          </div>
          <div
            className="knowledge-map"
            aria-label="Document intelligence workflow"
          >
            <div className="knowledge-map-center">
              <Brand compact />
              <strong>Connected knowledge</strong>
              <span>Your documents, working together</span>
            </div>
            {[
              {
                icon: "documents" as const,
                title: "Collect",
                text: "PDF, DOCX & text",
              },
              {
                icon: "assistant" as const,
                title: "Understand",
                text: "Answers with evidence",
              },
              {
                icon: "intelligence" as const,
                title: "Review",
                text: "Facts, risks & obligations",
              },
              {
                icon: "operations" as const,
                title: "Act",
                text: "Ownership & follow-through",
              },
            ].map((step, i) => (
              <div className={`knowledge-step step-${i}`} key={step.title}>
                <Icon name={step.icon} />
                <span>
                  <strong>{step.title}</strong>
                  <small>{step.text}</small>
                </span>
              </div>
            ))}
          </div>
        </section>
        <section
          className="public-value-grid"
          aria-label="Platform capabilities"
        >
          <article>
            <Icon name="quote" />
            <h2>Trust the evidence</h2>
            <p>
              Trace answers and findings to their original document passages.
            </p>
          </article>
          <article>
            <Icon name="intelligence" />
            <h2>See the important details</h2>
            <p>
              Review structured fields, document changes and potential risks in
              context.
            </p>
          </article>
          <article>
            <Icon name="operations" />
            <h2>Keep work moving</h2>
            <p>
              Bring obligations, reviews and accountability into one
              organization workspace.
            </p>
          </article>
        </section>
        <section id="system-status" className="public-system">
          <div>
            <p className="eyebrow">PLATFORM AVAILABILITY</p>
            <h2>A clear view of your services.</h2>
            <p>
              Live connectivity checks for the services behind your workspace.
            </p>
          </div>
          <SystemStatus />
        </section>
      </main>
      <footer className="public-footer">
        <Brand />
        <span>Document intelligence & operations · Built for teams</span>
      </footer>
    </div>
  );
}
