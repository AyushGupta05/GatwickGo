"use client";

import type { ReactNode } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

type Tab = {
  label: string;
  href: string;
  icon: (active: boolean) => ReactNode;
  isCenter?: boolean;
  external?: boolean;
  isActive?: (pathname: string) => boolean;
};

const tabs: Tab[] = [
  {
    label: "Camera",
    href: "/camera",
    isActive: (pathname: string) =>
      pathname === "/camera" || pathname.startsWith("/camera"),
    icon: (active: boolean) => (
      <svg
        className="block h-6 w-6 shrink-0"
        viewBox="0 0 24 24"
        fill="none"
        stroke={active ? "#003DA5" : "#9CA3AF"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        preserveAspectRatio="xMidYMid meet"
        aria-hidden="true"
      >
        <circle cx="12" cy="12" r="8" />
        <circle cx="12" cy="12" r="2" />
        <line x1="12" y1="4" x2="12" y2="7" />
        <line x1="12" y1="17" x2="12" y2="20" />
        <line x1="4" y1="12" x2="7" y2="12" />
        <line x1="17" y1="12" x2="20" y2="12" />
      </svg>
    ),
  },
  {
    label: "Collection",
    href: "/collection",
    icon: (active: boolean) => (
      <svg
        className="block h-6 w-6 shrink-0"
        viewBox="0 0 24 24"
        fill="none"
        stroke={active ? "#003DA5" : "#9CA3AF"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        preserveAspectRatio="xMidYMid meet"
        aria-hidden="true"
      >
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </svg>
    ),
  },
  {
    label: "Home",
    href: "/home",
    isActive: (pathname: string) =>
      pathname === "/home" || pathname === "/" || pathname.startsWith("/home"),
    icon: (active: boolean) => (
      <svg
        className="block h-6 w-6 shrink-0"
        viewBox="0 0 24 24"
        fill="none"
        stroke={active ? "#003DA5" : "#9CA3AF"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        preserveAspectRatio="xMidYMid meet"
        aria-hidden="true"
      >
        <path d="M3 12L12 3l9 9" />
        <path d="M5 10v10h14V10" />
        <path d="M9 21V12h6v9" />
      </svg>
    ),
  },
  {
    label: "Shop",
    href: "/shop",
    icon: (active: boolean) => (
      <svg
        className="block h-6 w-6 shrink-0"
        viewBox="0 0 24 24"
        fill="none"
        stroke={active ? "#003DA5" : "#9CA3AF"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        preserveAspectRatio="xMidYMid meet"
        aria-hidden="true"
      >
        <path d="M6 2L3 6v14a2 2 0 002 2h14a2 2 0 002-2V6l-3-4z" />
        <line x1="3" y1="6" x2="21" y2="6" />
        <path d="M16 10a4 4 0 01-8 0" />
      </svg>
    ),
  },
];

export default function BottomNav() {
  const pathname = usePathname();

  // Hide nav on auth pages only
  if (
    pathname === "/signin" ||
    pathname.startsWith("/auth/")
  ) {
    return null;
  }

  return (
    <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[430px] bg-nav-bg/95 border-t border-gray-200 shadow-[0_-4px_12px_rgba(0,0,0,0.05)] safe-bottom z-50">
      <div className="flex items-center justify-around h-14 px-4">
        {tabs.map((tab) => {
          const isActive = tab.isActive
            ? tab.isActive(pathname)
            : tab.href === "/"
            ? pathname === "/"
            : pathname.startsWith(tab.href);

          const linkClasses =
            "flex flex-col items-center justify-center min-w-[56px] min-h-[44px] gap-1 leading-none shrink-0";

          const labelClasses = `text-[10px] font-medium ${
            isActive ? "text-gatwick-blue" : "text-gray-400"
          }`;

          if (tab.external) {
            return (
              <a
                key={tab.label}
                href={tab.href}
                className={linkClasses}
              >
                {tab.icon(isActive)}
                <span className={labelClasses}>{tab.label}</span>
              </a>
            );
          }

          return (
            <Link key={tab.href} href={tab.href} className={linkClasses}>
              {tab.icon(isActive)}
              <span className={labelClasses}>{tab.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
