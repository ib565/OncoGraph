"use client";

import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";
import { useAppContext } from "../contexts/AppContext";

const tabs = [
  { href: "/", label: "Graph Q&A" },
  { href: "/hypotheses", label: "Functional Enrichment" },
  { href: "/voice", label: "Voice Agent" },
];

export default function TopBar() {
  const pathname = usePathname();
  const { clearAllState } = useAppContext();

  return (
    <div className="top-bar">
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <Image
          src="/icon.png"
          alt="OncoGraph"
          width={34}
          height={34}
          style={{ display: "block" }}
        />
        <h1 className="top-bar-title">OncoGraph</h1>
      </div>

      <nav className="top-bar-nav" aria-label="Primary">
        {tabs.map((tab) => {
          const isActive = pathname === tab.href;
          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={isActive ? "top-bar-tab active" : "top-bar-tab"}
            >
              {tab.label}
            </Link>
          );
        })}
      </nav>

      <div className="top-bar-actions">
        <a
          href="https://github.com/ib565/OncoGraph"
          target="_blank"
          rel="noopener noreferrer"
          className="top-bar-link"
          title="View on GitHub"
        >
          GitHub
        </a>
        <a
          href="mailto:ish.bhartiya@gmail.com"
          className="top-bar-link"
          title="Contact via email"
        >
          Contact
        </a>
        <button
          onClick={clearAllState}
          className="clear-button"
          title="Clear all data and start fresh"
        >
          Clear All
        </button>
        <div className="top-bar-status" aria-live="polite">
          Ready
        </div>
      </div>
    </div>
  );
}
