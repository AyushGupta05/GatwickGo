"use client";

import { useEffect, useState } from "react";
import { getCollection } from "@/lib/store";
import { RARITY_COLORS, RARITY_LABELS } from "@/lib/data";
import type { PlaneCard } from "@/lib/data";

export default function CollectionPage() {
  const [collection, setCollection] = useState<PlaneCard[]>([]);
  const [filter, setFilter] = useState<"all" | "common" | "rare" | "shiny">(
    "all"
  );

  useEffect(() => {
    setCollection(getCollection());
  }, []);

  const filtered =
    filter === "all" ? collection : collection.filter((c) => c.rarity === filter);

  const stats = {
    total: collection.length,
    common: collection.filter((c) => c.rarity === "common").length,
    rare: collection.filter((c) => c.rarity === "rare").length,
    shiny: collection.filter((c) => c.rarity === "shiny").length,
  };

  return (
    <div className="flex flex-col gap-4 px-4 pt-4">
      {/* Header */}
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gatwick-dark">Collection</h1>
        <div className="flex items-center gap-2 text-xs text-gray-500">
          <span>{stats.total} cards</span>
        </div>
      </header>

      {/* Stats Row */}
      <div className="flex gap-2">
        <div className="flex-1 bg-gray-100 rounded-xl p-3 text-center">
          <p className="text-2xl font-bold text-gray-600">{stats.common}</p>
          <p className="text-[10px] text-gray-400 font-medium">Common</p>
        </div>
        <div className="flex-1 bg-blue-50 rounded-xl p-3 text-center">
          <p className="text-2xl font-bold text-blue-500">{stats.rare}</p>
          <p className="text-[10px] text-blue-400 font-medium">Rare</p>
        </div>
        <div className="flex-1 bg-amber-50 rounded-xl p-3 text-center">
          <p className="text-2xl font-bold text-amber-500">{stats.shiny}</p>
          <p className="text-[10px] text-amber-400 font-medium">Shiny</p>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="flex gap-2">
        {(["all", "common", "rare", "shiny"] as const).map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`px-4 py-2 rounded-full text-xs font-medium transition-colors ${
              filter === f
                ? "bg-gatwick-blue text-white"
                : "bg-white text-gray-500 border border-gray-200"
            }`}
          >
            {f === "all" ? "All" : RARITY_LABELS[f]}
          </button>
        ))}
      </div>

      {/* Cards Grid */}
      {filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-center">
          <span className="text-5xl mb-4">✈️</span>
          <p className="text-gray-500 font-medium">
            {filter === "all"
              ? "No planes captured yet!"
              : `No ${filter} planes yet!`}
          </p>
          <p className="text-gray-400 text-sm mt-1">
            Head to the camera to start spotting
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 pb-4">
          {filtered.map((card) => (
            <div
              key={card.id}
              className={`rounded-2xl p-3 bg-card-bg shadow-sm border border-gray-100 overflow-hidden relative ${
                card.rarity === "shiny"
                  ? "shiny-card"
                  : card.rarity === "rare"
                  ? "rare-card"
                  : ""
              }`}
            >
              {/* Rarity badge */}
              <span
                className="absolute top-2 right-2 px-2 py-0.5 rounded-full text-[10px] font-bold text-white"
                style={{ backgroundColor: RARITY_COLORS[card.rarity] }}
              >
                {RARITY_LABELS[card.rarity]}
              </span>

              {/* Airline logo */}
              <div
                className={`w-12 h-12 rounded-xl flex items-center justify-center text-2xl mb-2 ${
                  card.rarity === "shiny" ? "bg-white/30" : "bg-gatwick-light"
                }`}
              >
                {card.airline.logo}
              </div>

              {/* Info */}
              <p
                className={`font-bold text-sm leading-tight ${
                  card.rarity === "shiny" ? "text-white" : "text-gatwick-dark"
                }`}
              >
                {card.airline.name}
              </p>
              <p
                className={`text-xs mt-0.5 ${
                  card.rarity === "shiny" ? "text-white/80" : "text-gray-500"
                }`}
              >
                {card.planeType}
              </p>
              <div className="flex items-center justify-between mt-2">
                <span
                  className={`text-[10px] font-mono ${
                    card.rarity === "shiny" ? "text-white/60" : "text-gray-400"
                  }`}
                >
                  {card.flightNumber}
                </span>
                <span
                  className={`text-[10px] ${
                    card.rarity === "shiny" ? "text-white/60" : "text-gray-400"
                  }`}
                >
                  {new Date(card.capturedAt).toLocaleDateString("en-GB", {
                    day: "numeric",
                    month: "short",
                  })}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
