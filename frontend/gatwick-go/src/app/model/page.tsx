"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getTicketSession,
  getSessionTimeRemaining,
  clearTicketSession,
  TicketSession,
} from "@/lib/store";

function formatTime(ms: number): string {
  if (ms <= 0) return "0:00";
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, "0")}`;
}

export default function ModelPage() {
  const [session, setSession] = useState<TicketSession | null>(null);
  const [remaining, setRemaining] = useState(0);
  const modelUrl = "http://localhost:5000/";

  useEffect(() => {
    const sync = () => {
      const current = getTicketSession();
      setSession(current);
      setRemaining(getSessionTimeRemaining());
    };

    sync();
    const timer = setInterval(sync, 1000);
    return () => clearInterval(timer);
  }, []);

  const endSession = () => {
    clearTicketSession();
    setSession(null);
    setRemaining(0);
  };

  return (
    <div className="min-h-screen bg-gatwick-dark text-white pb-24">
      <div className="safe-top px-4 pt-4 flex items-center justify-between">
        <div>
          <p className="text-xs text-white/60">Model workspace</p>
          <h1 className="text-2xl font-bold">/model</h1>
        </div>
        <Link
          href="/home"
          className="text-sm font-medium bg-white/10 px-3 py-1.5 rounded-full"
        >
          Home
        </Link>
      </div>

      <div className="px-4 mt-4">
        <div className="flex items-center justify-between bg-white/5 border border-white/10 rounded-2xl p-3">
          <div>
            <p className="text-sm font-semibold text-white/90">
              Session status
            </p>
            {session ? (
              <p className="text-white/60 text-xs mt-0.5">
                Flight {session.ticket.flight} · Gate {session.ticket.gate} · Seat {session.ticket.seat}
              </p>
            ) : (
              <p className="text-white/60 text-xs mt-0.5">
                Scan a boarding pass in /camera to start a 5-minute window.
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            {session && (
              <span className="text-green-400 text-sm font-bold bg-green-500/20 px-3 py-1 rounded-full">
                {formatTime(remaining)} left
              </span>
            )}
            <Link
              href="/camera"
              className="text-xs bg-gatwick-blue text-white px-3 py-1.5 rounded-full font-semibold"
            >
              Open /camera
            </Link>
          </div>
        </div>

        <div className="mt-3 flex gap-2">
          <Link
            href="/collection"
            className="flex-1 text-center bg-white/5 border border-white/10 rounded-xl py-2 text-sm font-semibold"
          >
            Collection
          </Link>
          <Link
            href="/shop"
            className="flex-1 text-center bg-white/5 border border-white/10 rounded-xl py-2 text-sm font-semibold"
          >
            Shop
          </Link>
          <button
            onClick={endSession}
            className="text-xs px-3 py-2 rounded-xl bg-white/10 font-semibold"
          >
            End
          </button>
        </div>
      </div>

      <div className="mt-4 bg-black/40 border-t border-white/10">
        <iframe
          title="Model UI"
          src={modelUrl}
          className="w-full h-[70vh] border-0"
          allow="clipboard-write; clipboard-read; camera; microphone; fullscreen; display-capture"
        />
      </div>
    </div>
  );
}
