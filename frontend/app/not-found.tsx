import Link from "next/link";

import { Icon } from "@/components/Icon";

export default function NotFound() {
  return (
    <div className="not-found">
      <span className="not-found-code">404 · NOT FOUND</span>
      <h1>That page is not on the route sheet.</h1>
      <p>
        The link may be outdated, or the record may have been moved. Start from
        the citizen intake or the operations queue.
      </p>
      <div className="button-row">
        <Link className="button button-primary" href="/dashboard">
          Operations queue
          <Icon name="arrow" size={17} />
        </Link>
        <Link className="button button-secondary" href="/report">
          Report a waste issue
        </Link>
      </div>
    </div>
  );
}
