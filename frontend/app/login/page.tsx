"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { Icon } from "@/components/Icon";
import { errorMessage } from "@/lib/api";
import type { User } from "@/lib/types";

const DEMO_PASSWORD = "CivicOps!2026";

const demoAccounts = [
  {
    role: "Operator",
    email: "demo.operator@civicops.local",
    detail: "Review incidents, merge duplicates, assign and verify",
  },
  {
    role: "Field crew lead",
    email: "demo.field@civicops.local",
    detail: "Update assigned work and upload before/after evidence",
  },
  {
    role: "Administrator",
    email: "demo.admin@civicops.local",
    detail: "Full operator access with administrative oversight",
  },
  {
    role: "Citizen",
    email: "demo.citizen@civicops.local",
    detail: "Submit and follow a citizen report",
  },
];

function defaultDestination(user: User): string {
  if (user.role === "operator" || user.role === "admin") return "/dashboard";
  if (user.role === "field_worker") return "/field";
  return "/";
}

function safeDestination(raw: string | null, user: User): string {
  if (raw && raw.startsWith("/") && !raw.startsWith("//")) return raw;
  return defaultDestination(user);
}

function LoginContent() {
  const { user, state, login } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState(() => searchParams.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestedNext = searchParams.get("next");

  useEffect(() => {
    if (state === "signed_in" && user) {
      router.replace(safeDestination(requestedNext, user));
    }
  }, [state, user, router, requestedNext]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const signedIn = await login(email.trim(), password);
      router.replace(safeDestination(requestedNext, signedIn));
    } catch (caught) {
      setError(errorMessage(caught));
      setSubmitting(false);
    }
  }

  function chooseAccount(accountEmail: string) {
    setEmail(accountEmail);
    setPassword(DEMO_PASSWORD);
    setError(null);
  }

  return (
    <div className="shell auth-page">
      <div className="auth-intro">
        <span className="eyebrow">Staff &amp; demo access</span>
        <h1>A calm place to run a messy job.</h1>
        <p>
          Civic operations need a shared, auditable record. Sign in to review
          citizen reports, confirm duplicate relationships, assign work and
          verify evidence — with the same permission rules enforced by the API.
        </p>
        <ul className="auth-points">
          <li>
            <Icon name="spark" size={17} />
            <span>
              AI triage suggests categories and priorities; authorised operators
              make every final decision.
            </span>
          </li>
          <li>
            <Icon name="layers" size={17} />
            <span>
              Nearby reports are grouped into spatial hotspots and linked
              without deleting source evidence.
            </span>
          </li>
          <li>
            <Icon name="clipboard" size={17} />
            <span>
              Work orders track deterministic SLA deadlines, before/after photos
              and full audit history.
            </span>
          </li>
          <li>
            <Icon name="shield" size={17} />
            <span>
              Role permissions are enforced by the API, keeping citizen contact
              details out of field views.
            </span>
          </li>
        </ul>
      </div>

      <section className="surface auth-card" aria-labelledby="login-heading">
        <h2 id="login-heading">Sign in</h2>
        <p>
          Use a synthetic demo account or your issued credentials. Accounts
          prefixed with <span className="mono">demo.</span> are not real people.
        </p>

        {error && (
          <div className="notice notice-error" role="alert" style={{ marginBottom: 16 }}>
            <Icon name="alert" size={18} />
            <div>
              <strong>Sign-in failed</strong>
              <p>{error}</p>
            </div>
          </div>
        )}

        <form className="stack-form" onSubmit={handleSubmit}>
          <div className="field">
            <label htmlFor="login-email">Email address</label>
            <input
              id="login-email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              placeholder="name@civicops.local"
            />
          </div>
          <div className="field">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              type="password"
              autoComplete="current-password"
              required
              minLength={8}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="At least 8 characters"
            />
          </div>
          <button
            className="button button-primary button-block"
            type="submit"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <span className="spinner spinner-small" />
                Signing in…
              </>
            ) : (
              <>
                Sign in
                <Icon name="arrow" size={17} />
              </>
            )}
          </button>
        </form>

        <div className="divider">
          <span>Demo accounts</span>
        </div>

        <div className="demo-account-grid">
          {demoAccounts.map((account) => (
            <button
              className="demo-account-button"
              type="button"
              key={account.email}
              onClick={() => chooseAccount(account.email)}
              title={account.detail}
            >
              <strong>{account.role}</strong>
              <span>{account.email}</span>
            </button>
          ))}
        </div>

        <p className="auth-note">
          Shared demo password: <strong className="mono">{DEMO_PASSWORD}</strong>
          <br />
          Selecting an account fills the form. The dataset is synthetic and the
          demo runs locally; do not enter real personal information.
        </p>

        <div className="button-row" style={{ marginTop: 18 }}>
          <Link className="text-button" href="/report">
            Continue as a citizen without signing in
          </Link>
        </div>
      </section>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="shell page-loading" role="status">
          <span className="spinner" />
          <p>Loading sign in…</p>
        </div>
      }
    >
      <LoginContent />
    </Suspense>
  );
}
