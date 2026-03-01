"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ALL_PLANE_SLOTS,
  AIRLINE_MODELS,
  RARITY_LABELS,
  airlines,
  canonicalizePlaneType,
  resolveAirline,
  type PlaneCard,
  type PlaneSlot,
} from "@/lib/data";
import { getCollection, subscribeToProgressStore } from "@/lib/store";

type RarityFilter = "all" | "common" | "rare" | "shiny";
type SortMode = "airline" | "alpha" | "collected";

function slotKey(airlineId: string, planeType: string) {
  return `${airlineId}::${planeType}`;
}

function getAirlineAccent(airlineId: string): string {
  return AIRLINE_MODELS[airlineId]?.length ? "border-white/12" : "border-white/8";
}

function rarityClass(rarity: PlaneCard["rarity"] | null): string {
  if (rarity === "shiny") return "card-shiny";
  if (rarity === "rare") return "card-rare";
  if (rarity === "common") return "card-common";
  return "card-uncollected";
}

function slotMatchesCard(slot: PlaneSlot, card: PlaneCard): boolean {
  const cardAirline = resolveAirline(card.airline);
  if (!cardAirline || cardAirline.id !== slot.airlineId) {
    return false;
  }

  const slotType = slot.planeType;
  const cardType = canonicalizePlaneType(card.planeType);

  if (slotType === cardType) {
    return true;
  }

  if (slotType === "A320-family") {
    return ["A319", "A320", "A320neo", "A321", "A320-family"].includes(cardType);
  }

  return slotType === cardType;
}

export default function CollectionPage() {
  const [collection, setCollection] = useState<PlaneCard[]>([]);
  const [filter, setFilter] = useState<RarityFilter>("all");
  const [sort, setSort] = useState<SortMode>("collected");

  useEffect(() => {
    const sync = () => {
      setCollection(getCollection());
    };

    sync();
    return subscribeToProgressStore(sync);
  }, []);

  const slotState = useMemo(() => {
    const latestCardBySlot = new Map<string, PlaneCard>();

    for (const card of collection) {
      const matchingSlot = ALL_PLANE_SLOTS.find((slot) => slotMatchesCard(slot, card));
      if (!matchingSlot) continue;

      const key = slotKey(matchingSlot.airlineId, matchingSlot.planeType);
      const current = latestCardBySlot.get(key);
      if (!current || new Date(card.capturedAt).getTime() > new Date(current.capturedAt).getTime()) {
        latestCardBySlot.set(key, card);
      }
    }

    return ALL_PLANE_SLOTS.map((slot) => {
      const airline = airlines.find((item) => item.id === slot.airlineId) ?? airlines[0];
      const collectedCard = latestCardBySlot.get(slotKey(slot.airlineId, slot.planeType)) ?? null;

      return {
        slot,
        airline,
        collected: Boolean(collectedCard),
        card: collectedCard,
      };
    });
  }, [collection]);

  const filteredSlots = useMemo(() => {
    const next = slotState.filter((entry) => {
      if (filter === "all") return true;
      return entry.card?.rarity === filter;
    });

    next.sort((left, right) => {
      if (sort === "collected") {
        if (left.collected !== right.collected) {
          return left.collected ? -1 : 1;
        }
        const leftTime = left.card ? new Date(left.card.capturedAt).getTime() : 0;
        const rightTime = right.card ? new Date(right.card.capturedAt).getTime() : 0;
        return rightTime - leftTime || left.airline.name.localeCompare(right.airline.name);
      }

      if (sort === "alpha") {
        return left.slot.planeType.localeCompare(right.slot.planeType) ||
          left.airline.name.localeCompare(right.airline.name);
      }

      return left.airline.name.localeCompare(right.airline.name) ||
        left.slot.planeType.localeCompare(right.slot.planeType);
    });

    return next;
  }, [filter, slotState, sort]);

  const stats = useMemo(() => {
    const collectedSlots = slotState.filter((entry) => entry.collected);
    const shiny = collectedSlots.filter((entry) => entry.card?.rarity === "shiny").length;
    const rare = collectedSlots.filter((entry) => entry.card?.rarity === "rare").length;
    const common = collectedSlots.filter((entry) => entry.card?.rarity === "common").length;

    return {
      totalSlots: slotState.length,
      collectedSlots: collectedSlots.length,
      completion: slotState.length > 0 ? Math.round((collectedSlots.length / slotState.length) * 100) : 0,
      totalCaptures: collection.length,
      shiny,
      rare,
      common,
    };
  }, [collection.length, slotState]);

  return (
    <div className="flex flex-col gap-5 px-4 pt-4 pb-8">
      <header className="rounded-[28px] bg-gatwick-dark px-5 py-5 text-white shadow-[0_16px_40px_rgba(0,27,77,0.18)]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.32em] text-white/55">
              Gemini Collection
            </p>
            <h1 className="mt-2 text-3xl font-black tracking-tight">
              /collection
            </h1>
            <p className="mt-2 max-w-[20rem] text-sm text-white/70">
              Every session capture from Gemini lands here. Collected aircraft stay lit, the rest remain hidden.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/8 px-4 py-3 text-right backdrop-blur">
            <p className="text-[11px] uppercase tracking-[0.22em] text-white/55">
              Completion
            </p>
            <p className="mt-1 text-3xl font-black">{stats.completion}%</p>
          </div>
        </div>

        <div className="mt-5 h-3 overflow-hidden rounded-full bg-white/10">
          <div
            className="progress-fill h-full rounded-full bg-gradient-to-r from-gatwick-gold via-white to-gatwick-red"
            style={{ width: `${stats.completion}%` }}
          />
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-2xl border border-white/10 bg-white/6 px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-white/55">Collected</p>
            <p className="mt-1 text-2xl font-bold">{stats.collectedSlots}</p>
            <p className="text-xs text-white/60">of {stats.totalSlots} fleet slots</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/6 px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-white/55">Captures</p>
            <p className="mt-1 text-2xl font-bold">{stats.totalCaptures}</p>
            <p className="text-xs text-white/60">session cards saved</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/6 px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-white/55">Rare</p>
            <p className="mt-1 text-2xl font-bold">{stats.rare}</p>
            <p className="text-xs text-white/60">mid-tier finds</p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/6 px-4 py-3">
            <p className="text-[11px] uppercase tracking-[0.16em] text-white/55">Shiny</p>
            <p className="mt-1 text-2xl font-bold">{stats.shiny}</p>
            <p className="text-xs text-white/60">top rarity pulls</p>
          </div>
        </div>
      </header>

      <section className="grid grid-cols-2 gap-3">
        {(["all", "common", "rare", "shiny"] as const).map((value) => (
          <button
            key={value}
            onClick={() => setFilter(value)}
            className={`rounded-2xl px-4 py-3 text-left transition ${
              filter === value
                ? "bg-gatwick-blue text-white shadow-[0_10px_24px_rgba(0,61,165,0.22)]"
                : "bg-white text-gatwick-dark ring-1 ring-black/5"
            }`}
          >
            <p className="text-xs uppercase tracking-[0.16em] opacity-70">Filter</p>
            <p className="mt-1 text-sm font-bold">
              {value === "all" ? "All Slots" : RARITY_LABELS[value]}
            </p>
          </button>
        ))}
      </section>

      <section className="rounded-[24px] bg-white p-4 shadow-sm ring-1 ring-black/5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] uppercase tracking-[0.22em] text-gray-400">Sort</p>
            <h2 className="text-lg font-bold text-gatwick-dark">Fleet Grid</h2>
          </div>
          <div className="flex gap-2">
            {([
              { id: "collected", label: "Newest" },
              { id: "airline", label: "Airline" },
              { id: "alpha", label: "Model" },
            ] as const).map((option) => (
              <button
                key={option.id}
                onClick={() => setSort(option.id)}
                className={`rounded-full px-3 py-2 text-xs font-semibold transition ${
                  sort === option.id
                    ? "bg-gatwick-dark text-white"
                    : "bg-gatwick-light text-gatwick-dark"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3">
          {filteredSlots.map(({ slot, airline, collected, card }) => {
            const displayFlight = card?.flightNumber || "LOCKED";
            const displayDate = card
              ? new Date(card.capturedAt).toLocaleDateString("en-GB", {
                  day: "numeric",
                  month: "short",
                })
              : "Uncollected";

            return (
              <article
                key={slotKey(slot.airlineId, slot.planeType)}
                className={`relative min-h-[188px] overflow-hidden rounded-[26px] p-4 text-white ${rarityClass(card?.rarity ?? null)}`}
              >
                <div className="absolute inset-x-0 top-0 h-24 bg-[radial-gradient(circle_at_top,rgba(255,255,255,0.22),transparent_68%)]" />
                <div className="relative flex h-full flex-col">
                  <div className="flex items-start justify-between gap-3">
                    <div
                      className={`flex h-12 w-12 items-center justify-center rounded-2xl border bg-white/10 text-sm font-black tracking-[0.14em] text-white ${getAirlineAccent(airline.id)}`}
                      style={{ boxShadow: `0 0 0 1px ${airline.color}40 inset` }}
                    >
                      {airline.logo}
                    </div>
                    <span className="rounded-full bg-black/25 px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.16em] text-white/80">
                      {collected ? (card ? RARITY_LABELS[card.rarity] : "Collected") : "Hidden"}
                    </span>
                  </div>

                  <div className="mt-4">
                    <p className="text-sm font-black leading-tight">
                      {airline.name}
                    </p>
                    <p className="mt-1 text-xs text-white/74">{slot.planeType}</p>
                  </div>

                  <div className="mt-auto pt-5">
                    {collected && card ? (
                      <>
                        <div className="flex items-center justify-between text-[11px] text-white/72">
                          <span>{displayFlight}</span>
                          <span>{displayDate}</span>
                        </div>
                        <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-white/55">
                          Session capture saved
                        </p>
                      </>
                    ) : (
                      <>
                        <div className="flex items-center justify-between text-[11px] text-white/55">
                          <span>{displayFlight}</span>
                          <span>{displayDate}</span>
                        </div>
                        <p className="mt-2 text-[11px] uppercase tracking-[0.18em] text-white/45">
                          Capture this aircraft to reveal it
                        </p>
                      </>
                    )}
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      </section>
    </div>
  );
}
