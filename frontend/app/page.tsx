import Link from "next/link";

import { Icon } from "@/components/Icon";
import { PublicMapSection } from "@/components/PublicMapSection";

const trail = [
  {
    title: "Citizen report received",
    detail: "Location, description and optional photo are persisted before AI enrichment.",
    tag: "Intake",
    state: "done",
    icon: "camera" as const,
  },
  {
    title: "AI triage suggestion recorded",
    detail: "Category, severity, visible indicators and confidence, with a rule-based fallback.",
    tag: "AI advisory",
    state: "done",
    icon: "spark" as const,
  },
  {
    title: "Nearby report flagged",
    detail: "58 m away · 74% text similarity · same suggested category. No automatic merge.",
    tag: "Human review",
    state: "current",
    icon: "copy" as const,
  },
  {
    title: "Operator assigns a crew",
    detail: "Priority is explained, and dispatch requires a human-approved work order.",
    tag: "Human decision",
    state: "upcoming",
    icon: "clipboard" as const,
  },
  {
    title: "Resolution independently verified",
    detail: "After-photo and field note are checked before the incident is closed.",
    tag: "Evidence",
    state: "upcoming",
    icon: "shield" as const,
  },
];

const steps = [
  {
    title: "Report",
    owner: "Citizen",
    body: "Photo, description and a map pin. The report is stored before any model call.",
  },
  {
    title: "Interpret",
    owner: "AI, advisory",
    body: "Typed classification, visible indicators and explicit uncertainty. Never a final decision.",
  },
  {
    title: "Consolidate",
    owner: "Operator",
    body: "Nearby reports are suggested, never auto-merged. Every source report is preserved.",
  },
  {
    title: "Resolve",
    owner: "Field crew",
    body: "A human-approved work order carries instructions, due date and before-photo evidence.",
  },
  {
    title: "Verify",
    owner: "Operator",
    body: "After-photo and notes are reviewed. Rejection reopens the work through an audited transition.",
  },
];

const principles = [
  {
    icon: "spark" as const,
    title: "AI advises. People decide.",
    body: "Classification, duplicate suggestions and priority rationale are transparent recommendations. An operator confirms triage, merges, dispatch and resolution.",
  },
  {
    icon: "layers" as const,
    title: "One hotspot, every source report.",
    body: "Duplicate confirmation links a report to an existing incident and archives an empty source incident. Original text, photos and reporter context remain intact.",
  },
  {
    icon: "shield" as const,
    title: "Evidence before closure.",
    body: "Field completion requires an after-photo. Only an operator or administrator can verify the outcome, and every transition is written to the audit trail.",
  },
];

const accounts = [
  {
    label: "Operator",
    email: "demo.operator@civicops.local",
    note: "Triage, merge, assign, verify",
  },
  {
    label: "Field crew lead",
    email: "demo.field@civicops.local",
    note: "Accept, work, upload evidence",
  },
  {
    label: "Administrator",
    email: "demo.admin@civicops.local",
    note: "Full operations access",
  },
  {
    label: "Citizen",
    email: "demo.citizen@civicops.local",
    note: "Report and track an issue",
  },
];

export default function HomePage() {
  return (
    <div className="home">
      <section className="home-hero">
        <div className="shell hero-grid">
          <div className="hero-copy">
            <span className="eyebrow eyebrow-light">
              Code for India Hackathon 2026 · Waste management
            </span>
            <h1>
              From scattered complaints to <em>verified action.</em>
            </h1>
            <p className="hero-lede">
              CivicOps AI turns citizen waste reports into reviewed incidents,
              explainable priorities and accountable field work. Built around a
              simple rule: the model can suggest, but a person must decide.
            </p>
            <div className="hero-actions">
              <Link className="button button-primary button-large" href="/report">
                Report a waste issue
                <Icon name="arrow" size={18} />
              </Link>
              <Link className="button button-ghost button-large" href="/dashboard">
                Open operations workspace
              </Link>
            </div>
            <div className="hero-meta">
              <span>
                <Icon name="shield" size={17} />
                Human-approved workflow
              </span>
              <span>
                <Icon name="pin" size={17} />
                Ward-level hotspot view
              </span>
              <span>
                <Icon name="camera" size={17} />
                Evidence-backed closure
              </span>
            </div>
          </div>

          <aside className="hero-panel" aria-label="Illustrative resolution trail">
            <div className="hero-panel-head">
              <span className="live-dot" aria-hidden="true" />
              <span>Resolution trail</span>
              <span className="demo-badge">Synthetic demo</span>
            </div>
            <ol className="trail">
              {trail.map((item) => (
                <li
                  key={item.title}
                  className={
                    item.state === "done"
                      ? "is-done"
                      : item.state === "current"
                        ? "is-current"
                        : undefined
                  }
                >
                  <span className="trail-icon">
                    <Icon name={item.icon} size={16} />
                  </span>
                  <div className="trail-copy">
                    <strong>{item.title}</strong>
                    <span>{item.detail}</span>
                    <span
                      className={
                        item.tag.includes("Human")
                          ? "trail-tag human"
                          : "trail-tag"
                      }
                    >
                      {item.tag}
                    </span>
                  </div>
                </li>
              ))}
            </ol>
            <div className="hero-panel-foot">
              <span>Every decision recorded</span>
              <span className="mono">INC-2026-••••</span>
            </div>
          </aside>
        </div>
      </section>

      <section className="home-section">
        <div className="shell">
          <div className="section-heading">
            <div>
              <span className="eyebrow">The operating loop</span>
              <h2>One civic task, closed properly.</h2>
              <p>
                The MVP is deliberately narrow: waste-management complaints.
                Every screen exists to move one report toward a verified
                outcome — not to inflate a dashboard.
              </p>
            </div>
          </div>
          <div className="workflow-steps">
            {steps.map((step, index) => (
              <article className="workflow-step" key={step.title}>
                <span className="workflow-step-number">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <h3>{step.title}</h3>
                <p>{step.body}</p>
                <span className="step-owner">{step.owner}</span>
              </article>
            ))}
          </div>
        </div>
      </section>

      <PublicMapSection />

      <section className="home-section home-section-tinted">
        <div className="shell">
          <div className="section-heading">
            <div>
              <span className="eyebrow">Accountability by design</span>
              <h2>Trust is a workflow property.</h2>
              <p>
                The system separates what a model observed from what an
                authorised person approved. That distinction stays visible in
                the interface and in the audit history.
              </p>
            </div>
          </div>
          <div className="principles-grid">
            {principles.map((principle) => (
              <article className="principle-card" key={principle.title}>
                <span className="principle-icon">
                  <Icon name={principle.icon} size={21} />
                </span>
                <h3>{principle.title}</h3>
                <p>{principle.body}</p>
              </article>
            ))}
          </div>
        </div>
      </section>

      <section className="home-section">
        <div className="shell">
          <div className="demo-band">
            <div>
              <span className="eyebrow">Explore the workflow</span>
              <h2>A complete demo dataset, clearly labelled.</h2>
              <p>
                Four synthetic accounts, three wards, six incidents and four
                work orders. Open two nearby reports, confirm the duplicate,
                assign a crew and verify the resolution. No real municipal
                data is used or claimed.
              </p>
              <div className="button-row">
                <Link className="button button-primary" href="/login">
                  Sign in to the demo
                  <Icon name="arrow" size={17} />
                </Link>
                <Link className="button button-ghost" href="/report">
                  Submit a test report
                </Link>
              </div>
            </div>
            <div>
              <div className="demo-accounts">
                {accounts.map((account) => (
                  <Link
                    className="demo-account"
                    href={`/login?email=${encodeURIComponent(account.email)}`}
                    key={account.email}
                  >
                    <strong>{account.label}</strong>
                    <span>{account.email}</span>
                    <small>{account.note}</small>
                  </Link>
                ))}
              </div>
              <p className="small" style={{ margin: "14px 0 0", color: "#9bb7a4" }}>
                Shared demo password:{" "}
                <span className="mono" style={{ color: "#dbe8dd" }}>
                  CivicOps!2026
                </span>
              </p>
            </div>
          </div>
        </div>
      </section>

      <section className="shell" style={{ paddingBottom: 8 }}>
        <div className="cta-band">
          <div>
            <h2>See something that needs attention?</h2>
            <p>
              Submit a waste report with a map pin and optional photo. You can
              track its status without creating an account.
            </p>
          </div>
          <Link className="button button-primary" href="/report">
            Start a report
            <Icon name="arrow" size={17} />
          </Link>
        </div>
      </section>
    </div>
  );
}
