"use client";

import { MOCK_TICKETS } from "@/lib/data";
import { QRCodeSVG } from "qrcode.react";
import { useRouter } from "next/navigation";

export default function TicketsPage() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-gatwick-dark p-4 pb-24">
      {/* Header */}
      <div className="safe-top pt-4 mb-6">
        <div className="flex items-center gap-3 mb-2">
          <button
            onClick={() => router.back()}
            className="text-white bg-white/10 px-3 py-1.5 rounded-full text-sm"
          >
            ← Back
          </button>
          <h1 className="text-white font-bold text-xl">🎫 Mock Boarding Passes</h1>
        </div>
        <p className="text-white/60 text-xs">
          Display one of these QR codes on another screen, then scan it with the
          camera to validate your ticket. Each scan starts a 30-minute session.
        </p>
      </div>

      {/* QR Code Grid */}
      <div className="grid grid-cols-1 gap-4">
        {MOCK_TICKETS.map((ticket) => (
          <div
            key={ticket.id}
            className="bg-white rounded-2xl p-4 flex flex-col items-center gap-3"
          >
            <QRCodeSVG
              value={JSON.stringify(ticket)}
              size={200}
              level="L"
              includeMargin={true}
            />
            <div className="w-full text-center">
              <p className="text-gray-800 font-bold text-sm">{ticket.passenger}</p>
              <div className="text-gray-500 text-xs space-y-0.5 mt-1">
                <p>✈️ {ticket.flight} → {ticket.destination}</p>
                <p>🚪 Gate {ticket.gate} · Seat {ticket.seat}</p>
                <p className="text-gray-400 font-mono text-[10px]">{ticket.id}</p>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Instructions */}
      <div className="mt-6 bg-white/5 rounded-2xl p-4">
        <h2 className="text-white font-bold text-sm mb-2">How to use</h2>
        <ol className="text-white/60 text-xs space-y-1 list-decimal list-inside">
          <li>Display one of these QR codes on another device or print it</li>
          <li>Go to the Camera page (tap the capture button on the home screen)</li>
          <li>Point your camera at the QR code — it auto-detects</li>
          <li>Once validated, you have <strong className="text-white/80">30 minutes</strong> to capture planes</li>
          <li>During the session, you can capture as many planes as you want without re-scanning</li>
        </ol>
      </div>
    </div>
  );
}
