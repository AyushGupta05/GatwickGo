"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuth, AUTH_ON } from "@/lib/auth";

const PUBLIC_PATHS = ["/signin", "/auth/callback"];

export default function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  if (!AUTH_ON) {
    return <>{children}</>;
  }

  const isPublic = PUBLIC_PATHS.some(
    (path) => pathname === path || pathname.startsWith(path + "/")
  );

  useEffect(() => {
    if (!loading && user && isPublic) {
      router.replace("/home");
      return;
    }

    if (!loading && !user && !isPublic) {
      router.replace("/signin");
    }
  }, [isPublic, loading, router, user]);

  if (isPublic) {
    return <>{children}</>;
  }

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 animate-spin rounded-full border-4 border-gatwick-blue border-t-transparent" />
          <p className="text-sm font-medium text-gray-500">Loading...</p>
        </div>
      </div>
    );
  }

  if (!user && !isPublic) {
    return null;
  }

  return <>{children}</>;
}
