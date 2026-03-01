"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { supabase } from "@/lib/supabaseClient";

export default function AuthCallback() {
  const router = useRouter();

  useEffect(() => {
    const run = async () => {
      const { data } = await supabase.auth.getSession();
      if (data.session) {
        router.replace("/home");
      } else {
        router.replace("/signin");
      }
    };
    run();
  }, [router]);

  return (
    <div className="flex items-center justify-center min-h-dvh">
      <div className="flex flex-col items-center gap-3">
        <div className="w-10 h-10 border-4 border-gatwick-blue border-t-transparent rounded-full animate-spin" />
        <p className="text-sm text-gray-500 font-medium">Signing you in…</p>
      </div>
    </div>
  );
}
