"use client";

import { RARITY_LABELS, type PlaneCard } from "@/lib/data";

function rarityClass(rarity: PlaneCard["rarity"]): string {
  if (rarity === "shiny") return "card-shiny";
  if (rarity === "rare") return "card-rare";
  return "card-common";
}

export default function FlightCollectionCard({ card }: { card: PlaneCard }) {
  return (
    <article
      className={`overflow-hidden rounded-[24px] text-white ${rarityClass(card.rarity)}`}
    >
      <div className="relative h-28 bg-black/20">
        {card.imageUrl ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={card.imageUrl}
            alt={`${card.airline.name} ${card.planeType}`}
            className="h-full w-full object-cover"
          />
        ) : (
          <div className="flex h-full w-full items-center justify-center bg-black/15 text-3xl font-black tracking-[0.18em]">
            {card.airline.logo}
          </div>
        )}
        <div className="absolute inset-0 bg-gradient-to-t from-black/55 via-black/10 to-transparent" />
        <span className="absolute right-3 top-3 rounded-full bg-black/35 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-white">
          {RARITY_LABELS[card.rarity]}
        </span>
      </div>

      <div className="px-4 py-4">
        <p className="text-sm font-black leading-tight">{card.airline.name}</p>
        <p className="mt-1 text-xs text-white/80">{card.planeType}</p>
        <div className="mt-4 flex items-center justify-between text-[11px] text-white/72">
          <span>{card.flightNumber}</span>
          <span>
            {new Date(card.capturedAt).toLocaleTimeString("en-GB", {
              hour: "2-digit",
              minute: "2-digit",
            })}
          </span>
        </div>
      </div>
    </article>
  );
}
