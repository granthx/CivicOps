import Link from "next/link";

export function Footer() {
  return (
    <footer className="site-footer">
      <div className="shell footer-inner">
        <div>
          <strong>CivicOps AI</strong>
          <p>
            Hackathon MVP for waste-management intake and accountable resolution.
            Seed records are synthetic; no municipality endorsement is implied.
          </p>
        </div>
        <div className="footer-links">
          <Link href="/report">Report an issue</Link>
          <Link href="/track">Track a report</Link>
          <a href="http://localhost:8000/api/docs" target="_blank" rel="noreferrer">
            API docs
          </a>
        </div>
      </div>
    </footer>
  );
}
