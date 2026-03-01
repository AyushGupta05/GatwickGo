"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  {
    label: "Collection",
    href: "/collection",
    icon: (active: boolean) => (
      <svg
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke={active ? "#003DA5" : "#9CA3AF"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
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
    href: "/",
    icon: (active: boolean) => (
      <div
        className={`w-14 h-14 rounded-full flex items-center justify-center -mt-6 shadow-lg ${
          active ? "bg-gatwick-blue" : "bg-gatwick-dark"
        }`}
      >
        <svg
          width="28"
          height="28"
          viewBox="0 0 24 24"
          fill="none"
          stroke="white"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M22 2L11 13" />
          <path d="M22 2L15 22L11 13L2 9L22 2Z" />
        </svg>
      </div>
    ),
    isCenter: true,
  },
  {
    label: "Shop",
    href: "/shop",
    icon: (active: boolean) => (
      <svg
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke={active ? "#003DA5" : "#9CA3AF"}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
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

  // Hide nav on full-screen camera page and auth pages
  if (
    pathname === "/camera" ||
    pathname.startsWith("/camera/") ||
    pathname === "/signin" ||
    pathname.startsWith("/auth/")
  ) {
    return null;
  }

  return (
    <nav className="fixed bottom-0 left-1/2 -translate-x-1/2 w-full max-w-[430px] bg-nav-bg border-t border-gray-200 safe-bottom z-50">
      <div className="flex items-center justify-around h-16">
        {tabs.map((tab) => {
          const isActive =
            tab.href === "/"
              ? pathname === "/"
              : pathname.startsWith(tab.href);

          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`flex flex-col items-center justify-center min-w-[64px] min-h-[44px] ${
                tab.isCenter ? "" : "gap-1"
              }`}
            >
              {tab.icon(isActive)}
              <span
                className={`text-[10px] font-medium ${
                  tab.isCenter
                    ? "mt-1"
                    : isActive
                    ? "text-gatwick-blue"
                    : "text-gray-400"
                }`}
              >
                {tab.label}
              </span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
