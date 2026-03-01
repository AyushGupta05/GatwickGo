"use client";

import { useState } from "react";
import { supabase } from "@/lib/supabaseClient";

export default function SignInPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const sendLink = async () => {
    if (!email.trim()) return;
    setError(null);
    setLoading(true);

    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: {
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      },
    });

    setLoading(false);
    if (error) setError(error.message);
    else setSent(true);
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-dvh px-6">
      {/* Logo / Branding */}
      <div className="flex items-center gap-2 mb-2">
        <div className="w-2 h-10 bg-gatwick-red rounded-full" />
        <h1 className="text-3xl font-bold text-gatwick-dark tracking-tight">
          GATWICK GO!
        </h1>
      </div>
      <p className="text-sm text-gray-500 mb-8">
        Spot planes, collect cards, earn rewards
      </p>

      {/* Card */}
      <div className="w-full max-w-sm bg-white rounded-2xl shadow-lg p-6">
        {sent ? (
          <div className="flex flex-col items-center text-center gap-3">
            <div className="w-16 h-16 rounded-full bg-gatwick-light flex items-center justify-center text-3xl">
              ✉️
            </div>
            <h2 className="text-lg font-bold text-gatwick-dark">
              Check your email
            </h2>
            <p className="text-sm text-gray-500">
              We sent a sign-in link to <strong>{email}</strong>. Tap the link
              in the email to continue.
            </p>
            <button
              onClick={() => {
                setSent(false);
                setEmail("");
              }}
              className="mt-2 text-sm text-gatwick-blue underline"
            >
              Use a different email
            </button>
          </div>
        ) : (
          <>
            <h2 className="text-lg font-bold text-gatwick-dark mb-1">
              Sign in
            </h2>
            <p className="text-sm text-gray-500 mb-4">
              We&apos;ll email you a one-tap sign-in link.
            </p>

            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && sendLink()}
              placeholder="you@example.com"
              inputMode="email"
              autoComplete="email"
              className="w-full px-4 py-3 rounded-xl border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-gatwick-blue/40 focus:border-gatwick-blue transition"
            />

            <button
              onClick={sendLink}
              disabled={loading || !email.trim()}
              className="w-full mt-3 py-3 rounded-xl bg-gatwick-blue text-white font-semibold text-sm disabled:opacity-50 transition active:scale-[0.98]"
            >
              {loading ? "Sending…" : "Send magic link"}
            </button>

            {error && (
              <p className="mt-3 text-sm text-gatwick-red text-center">
                {error}
              </p>
            )}
          </>
        )}
      </div>

      <p className="text-xs text-gray-400 mt-6">
        No password required — just your email ✈️
      </p>
    </div>
  );
}
