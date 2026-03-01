"use client";

import { useEffect, useState } from "react";
import { supabase } from "@/lib/supabaseClient";
import { useRouter } from "next/navigation";

export default function SignInPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loadingAction, setLoadingAction] = useState<"signin" | "signup" | null>(null);
  const router = useRouter();

  useEffect(() => {
    const check = async () => {
      const { data } = await supabase.auth.getSession();
      if (data.session) {
        router.replace("/home");
      }
    };
    void check();
  }, [router]);

  const handleAuth = async (isSignup: boolean) => {
    const normalizedEmail = email.trim();
    if (!normalizedEmail || !password) {
      setError("Enter email and password.");
      return;
    }

    setError(null);
    setLoadingAction(isSignup ? "signup" : "signin");

    try {
      if (isSignup) {
        const { error: signUpError } = await supabase.auth.signUp({
          email: normalizedEmail,
          password,
        });
        if (signUpError) {
          throw signUpError;
        }
      }

      const { error: signInError } = await supabase.auth.signInWithPassword({
        email: normalizedEmail,
        password,
      });
      if (signInError) {
        throw signInError;
      }

      router.replace("/home");
    } catch (authError) {
      const message =
        authError instanceof Error ? authError.message : "Authentication failed.";
      setError(message);
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-dvh px-6">
      <div className="flex items-center gap-2 mb-2">
        <div className="w-2 h-10 bg-gatwick-red rounded-full" />
        <h1 className="text-3xl font-bold text-gatwick-dark tracking-tight">
          GATWICK GO!
        </h1>
      </div>
      <p className="text-sm text-gray-500 mb-8">
        Spot planes, collect cards, earn rewards
      </p>

      <div className="w-full max-w-sm bg-white rounded-2xl shadow-lg p-6">
        <h2 className="text-lg font-bold text-gatwick-dark mb-1">Log in</h2>
        <p className="text-sm text-gray-500 mb-4">
          Use your email and password.
        </p>

        <div className="flex flex-col gap-3">
          <input
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="you@example.com"
            inputMode="email"
            autoComplete="email"
            className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-gatwick-blue/40 focus:border-gatwick-blue transition"
          />

          <input
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                void handleAuth(false);
              }
            }}
            placeholder="Password"
            autoComplete="current-password"
            className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-gatwick-blue/40 focus:border-gatwick-blue transition"
          />
        </div>

        <div className="mt-3 grid grid-cols-2 gap-3">
          <button
            onClick={() => void handleAuth(false)}
            disabled={loadingAction !== null}
            className="py-3 rounded-xl bg-gatwick-blue text-white font-semibold text-sm disabled:opacity-50 transition active:scale-[0.98]"
          >
            {loadingAction === "signin" ? "Logging in..." : "Log in"}
          </button>
          <button
            onClick={() => void handleAuth(true)}
            disabled={loadingAction !== null}
            className="py-3 rounded-xl border border-gatwick-blue text-gatwick-blue font-semibold text-sm disabled:opacity-50 transition active:scale-[0.98]"
          >
            {loadingAction === "signup" ? "Creating..." : "Sign up"}
          </button>
        </div>

        {error && (
          <p className="mt-3 text-sm text-gatwick-red text-center">{error}</p>
        )}
      </div>
    </div>
  );
}
