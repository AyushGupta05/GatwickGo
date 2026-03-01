"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth, AUTH_ON } from "@/lib/auth";

const PUBLIC_PATHS = ["/signin", "/auth/callback"];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  // Skip all auth checks when auth is off
  if (!AUTH_ON) {
    return <>{children}</>;
  }

  const isPublic = PUBLIC_PATHS.some(
    (p) => pathname === p || pathname.startsWith(p + "/")
  );

  useEffect(() => {
    if (!loading && !user && !isPublic) {
      router.replace("/signin");
    }
  }, [loading, user, isPublic, router]);

  // Show loading spinner while checking auth
  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-dvh">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 border-4 border-gatwick-blue border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-gray-500 font-medium">Loading…</p>
        </div>
      </div>
    );
  }

  // If not authenticated and not on a public page, show nothing (redirect in effect)
  if (!user && !isPublic) {
    return null;
  }

  return <>{children}</>;
}
