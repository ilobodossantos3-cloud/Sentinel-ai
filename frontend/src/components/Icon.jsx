const PATHS = {
  dashboard: "M3 3h7v7H3zM14 3h7v7h-7zM3 14h7v7H3zM14 14h7v7h-7z",
  threats: "M12 3l9 16H3zM12 10v4M12 16.5v.5",
  assets: "M12 2l8 4.5v9L12 20l-8-4.5v-9zM12 11l8-4.5M12 11v9M12 11L4 6.5",
  audits: "M6 2h9l4 4v16H6zM15 2v4h4M9 12h7M9 16h7",
  vulns: "M12 3a9 9 0 100 18 9 9 0 000-18zM12 8v5M12 16v.5",
  network: "M12 3v5M12 16v5M5 12h5M14 12h5M12 10a2 2 0 110 4 2 2 0 010-4M5 10a2 2 0 110 4 2 2 0 010-4M19 10a2 2 0 110 4 2 2 0 010-4",
  logs: "M4 4h16M4 9h16M4 14h16M4 19h10",
  reports: "M4 20V10M10 20V4M16 20v-8M22 20H2",
  skills: "M12 2l2.5 6H21l-5 4 2 7-6-4.5L6 19l2-7-5-4h6.5z",
  admin: "M12 8a4 4 0 100 8 4 4 0 000-8zM12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9L17 7M7 17l-2.1 2.1",
};

export default function Icon({ name, size = 16 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d={PATHS[name] || PATHS.dashboard} />
    </svg>
  );
}
