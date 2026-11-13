import type { SVGProps } from "react";

type IconName =
  | "arrow"
  | "pin"
  | "camera"
  | "check"
  | "alert"
  | "clock"
  | "trash"
  | "chevron-left"
  | "chevron-right"
  | "refresh"
  | "upload"
  | "shield"
  | "lock"
  | "layers"
  | "copy"
  | "clipboard"
  | "users"
  | "spark"
  | "search"
  | "close"
  | "route"
  | "external";

const paths: Record<IconName, React.ReactNode> = {
  arrow: <path d="M5 12h14m-6-6 6 6-6 6" />,
  pin: (
    <>
      <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.6" />
    </>
  ),
  camera: (
    <>
      <path d="M4 7h3l1.5-2h7L17 7h3v11H4Z" />
      <circle cx="12" cy="12.5" r="3.3" />
    </>
  ),
  check: <path d="m5 12 4.2 4.2L19 6.5" />,
  alert: (
    <>
      <path d="M12 3 2.8 20h18.4Z" />
      <path d="M12 9v5m0 3.1v.1" />
    </>
  ),
  clock: (
    <>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5.3l3.5 2" />
    </>
  ),
  trash: (
    <>
      <path d="M4 7h16M9 7V4h6v3m-9 0 1 14h10l1-14M10 11v6m4-6v6" />
    </>
  ),
  "chevron-left": <path d="m15 18-6-6 6-6" />,
  "chevron-right": <path d="m9 18 6-6-6-6" />,
  refresh: <path d="M20 6v5h-5M4 18v-5h5m9.5-1A7.5 7.5 0 0 0 6 6.5L4 11m16 2-2 4.5a7.5 7.5 0 0 1-12.5-1.5" />,
  upload: <path d="M12 16V4m-5 5 5-5 5 5M4 16v4h16v-4" />,
  shield: <path d="M12 3 5 6v5c0 4.7 2.8 8 7 10 4.2-2 7-5.3 7-10V6Z" />,
  lock: (
    <>
      <rect x="4.5" y="10" width="15" height="10.5" rx="2" />
      <path d="M8 10V7a4 4 0 0 1 8 0v3M12 14v3" />
    </>
  ),
  layers: <path d="m12 3 9 5-9 5-9-5Zm-9 9 9 5 9-5M3 17l9 5 9-5" />,
  copy: (
    <>
      <rect x="8" y="8" width="12" height="12" rx="2" />
      <path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" />
    </>
  ),
  clipboard: (
    <>
      <path d="M9 4h6v3H9zM7 5H4v16h16V5h-3" />
      <path d="M8 12h8M8 16h6" />
    </>
  ),
  users: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 20c0-3.3 2.7-6 6-6s6 2.7 6 6M16 5.5a3 3 0 0 1 0 5.7M18 14.5c2 .7 3 2.6 3 5.5" />
    </>
  ),
  spark: <path d="m12 3 1.7 5.3L19 10l-5.3 1.7L12 17l-1.7-5.3L5 10l5.3-1.7Zm6 11 .8 2.2L21 17l-2.2.8L18 20l-.8-2.2L15 17l2.2-.8Z" />,
  search: (
    <>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m16 16 5 5" />
    </>
  ),
  close: <path d="m6 6 12 12M18 6 6 18" />,
  route: (
    <>
      <circle cx="5" cy="6" r="2.5" />
      <circle cx="19" cy="18" r="2.5" />
      <path d="M7.5 6h5a4 4 0 0 1 0 8h-2a4 4 0 0 0 0 8h6" />
    </>
  ),
  external: <path d="M14 4h6v6m0-6-9 9M19 14v5H5V5h5" />,
};

export function Icon({
  name,
  size = 20,
  ...props
}: SVGProps<SVGSVGElement> & { name: IconName; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {paths[name]}
    </svg>
  );
}

export function BrandMark({ size = 34 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 40 40"
      fill="none"
      aria-hidden="true"
      focusable="false"
    >
      <rect width="40" height="40" rx="10" fill="#245b43" />
      <path
        d="M20 7.5c-5.8 0-10.4 4.5-10.4 10.2 0 7.2 10.4 15 10.4 15s10.4-7.8 10.4-15C30.4 12 25.8 7.5 20 7.5Z"
        fill="#f5f4ee"
      />
      <path
        d="m15.8 17.8 2.8 2.8 5.8-6"
        stroke="#245b43"
        strokeWidth="2.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
