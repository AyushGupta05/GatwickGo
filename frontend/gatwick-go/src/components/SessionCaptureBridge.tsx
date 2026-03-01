"use client";

import { useEffect, useRef } from "react";
import { syncSessionCapture, type SessionCapturePayload } from "@/lib/store";

function buildCaptureEventKey(payload: SessionCapturePayload): string {
  const cardId =
    payload.card && typeof payload.card.id === "string" ? payload.card.id : "";
  if (cardId) return cardId;

  return [
    payload.capturedAt,
    payload.capturedAirline,
    payload.capturedModel,
    payload.flightNumber,
  ]
    .filter((value): value is string => typeof value === "string" && value.length > 0)
    .join("::");
}

export default function SessionCaptureBridge() {
  const seenEventsRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      const message = event.data;
      if (!message || message.type !== "gatwick-go-session-progress") {
        return;
      }

      const payload = (message.payload ?? {}) as SessionCapturePayload;
      const eventKey = buildCaptureEventKey(payload);
      if (eventKey && seenEventsRef.current.has(eventKey)) {
        return;
      }

      if (eventKey) {
        seenEventsRef.current.add(eventKey);
      }

      syncSessionCapture(payload);
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  return null;
}
