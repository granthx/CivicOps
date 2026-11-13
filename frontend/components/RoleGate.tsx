"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/components/AuthProvider";
import { Icon } from "@/components/Icon";
import type { Role } from "@/lib/types";

const labels: Record<Role, string> = {
  citizen: "resident",
  field_worker: "field worker",
  operator: "municipal operator",
  admin: "administrator",
};

export function RoleGate({
  roles,
  children,
}: {
  roles: Role[];
  children: React.ReactNode;
}) {
  const { user, state } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (state === "signed_out") {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [state, router, pathname]);

  if (state === "loading") {
    return (
      <div className="shell page-loading" role="status">
        <span className="spinner" />
        <p>Checking your session…</p>
      </div>
    );
  }

  if (!user) {
    return (
      <div className="shell page-loading" role="status">
        <p>Redirecting to sign in…</p>
      </div>
    );
  }

  if (!roles.includes(user.role)) {
    return (
      <div className="shell narrow-page">
        <section className="surface empty-state">
          <span className="empty-icon">
            <Icon name="shield" size={26} />
          </span>
          <h1>This workspace is restricted</h1>
          <p>
            You are signed in as a {labels[user.role]}. This area requires a different
            operational role. The backend enforces the same permission boundary.
          </p>
          <div className="button-row">
            <Link className="button button-primary" href="/">
              Return home
            </Link>
            <Link className="button button-secondary" href="/report">
              Report an issue
            </Link>
          </div>
        </section>
      </div>
    );
  }

  return <>{children}</>;
}
