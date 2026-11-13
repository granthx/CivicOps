"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "@/components/AuthProvider";
import { BrandMark } from "@/components/Icon";
import { initials } from "@/lib/format";

export function Header() {
  const { user, state, logout } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  const [signingOut, setSigningOut] = useState(false);

  const isOperations = user?.role === "operator" || user?.role === "admin";

  async function handleSignOut() {
    setSigningOut(true);
    await logout();
    setSigningOut(false);
    router.push("/");
    router.refresh();
  }

  return (
    <header className="site-header">
      <div className="shell header-inner">
        <Link className="brand" href="/" aria-label="CivicOps AI home">
          <BrandMark />
          <span>
            <strong>CivicOps</strong>
            <small>AI civic operations</small>
          </span>
        </Link>

        <nav className="primary-nav" aria-label="Primary navigation">
          <Link
            href="/report"
            className={pathname === "/report" ? "nav-link is-active" : "nav-link"}
          >
            Report an issue
          </Link>
          <Link
            href="/track"
            className={pathname === "/track" ? "nav-link is-active" : "nav-link"}
          >
            Track
          </Link>
          {isOperations && (
            <Link
              href="/dashboard"
              className={
                pathname.startsWith("/dashboard") || pathname.startsWith("/incidents")
                  ? "nav-link is-active"
                  : "nav-link"
              }
            >
              Operations
            </Link>
          )}
          {(isOperations || user?.role === "field_worker") && (
            <Link
              href="/field"
              className={pathname.startsWith("/field") ? "nav-link is-active" : "nav-link"}
            >
              Field tasks
            </Link>
          )}
        </nav>

        <div className="header-account">
          {state === "loading" ? (
            <span className="header-loading" aria-label="Loading account" />
          ) : user ? (
            <>
              <span className="account-chip" title={`${user.name} · ${user.role}`}>
                <span className="avatar">{initials(user.name)}</span>
                <span className="account-copy">
                  <strong>{user.name}</strong>
                  <small>{user.role.replace("_", " ")}</small>
                </span>
              </span>
              <button
                className="text-button"
                type="button"
                onClick={handleSignOut}
                disabled={signingOut}
              >
                {signingOut ? "Signing out…" : "Sign out"}
              </button>
            </>
          ) : (
            <Link
              className="button button-secondary"
              href={`/login?next=${encodeURIComponent(pathname)}`}
            >
              Staff sign in
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
