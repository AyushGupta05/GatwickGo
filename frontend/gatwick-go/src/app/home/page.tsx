"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import {
  getTodaysShiny,
  RARITY_LABELS,
} from "@/lib/data";
import {
  getPoints,
  getPointsToNextMilestone,
  getMilestoneProgress,
  getCollection,
} from "@/lib/store";
import { useAuth, AUTH_ON } from "@/lib/auth";

export default function Home() {
  const [points, setPoints] = useState(0);
  const [pointsToNext, setPointsToNext] = useState(100);
  const [progress, setProgress] = useState(0);
  const [collectionCount, setCollectionCount] = useState(0);
  const todaysShiny = getTodaysShiny();
  const { email, signOut } = useAuth();

  useEffect(() => {
    setPoints(getPoints());
    setPointsToNext(getPointsToNextMilestone());
    setProgress(getMilestoneProgress());
    setCollectionCount(getCollection().length);
  }, []);

  return (
    <div className="flex flex-col gap-4 px-4 pt-4">
      {/* User bar */}
      {AUTH_ON && email && (
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs text-gray-500 truncate max-w-[200px]">
            {email}
          </span>
          <button
            onClick={signOut}
            className="text-xs text-gatwick-red font-medium"
          >
            Sign out
          </button>
        </div>
      )}

      {/* Header */}
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-2 h-8 bg-gatwick-red rounded-full" />
          <h1 className="text-2xl font-bold text-gatwick-dark tracking-tight">
            GATWICK GO!
          </h1>
        </div>
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gatwick-light flex items-center justify-center text-gatwick-blue font-bold text-sm border-2 border-gatwick-blue">
            ✈️
          </div>
        </div>
      </header>

      {/* Progress Bar Section */}
      <div className="bg-card-bg rounded-2xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs text-gray-500 font-medium">
            Points to next milestone
          </span>
          <span className="text-sm font-bold text-gatwick-blue">
            {pointsToNext}
          </span>
        </div>
        <div className="w-full h-3 bg-gatwick-light rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-gatwick-blue to-gatwick-red rounded-full progress-fill transition-all duration-700"
            style={{ width: `${progress * 100}%` }}
          />
        </div>
        <div className="flex items-center justify-between mt-2">
          <div className="flex items-center gap-1">
            <span className="text-lg">✈️</span>
          </div>
          <div className="flex items-center gap-1">
            <span className="text-lg">🏆</span>
          </div>
        </div>
      </div>

      {/* Current Points */}
      <div className="bg-gradient-to-r from-gatwick-blue to-gatwick-dark rounded-2xl p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-white/70 text-xs font-medium">Current Points</p>
            <p className="text-4xl font-bold text-white">{points}</p>
          </div>
          <div className="text-right">
            <p className="text-white/70 text-xs font-medium">Cards Collected</p>
            <p className="text-2xl font-bold text-white">{collectionCount}</p>
          </div>
        </div>
      </div>

      {/* Enter Camera - Photo Mode Button */}
      <Link href="/camera" className="block">
        <div className="flex flex-col items-center py-6">
          <div className="relative">
            <div className="absolute inset-0 rounded-full bg-gatwick-blue/20 pulse-ring" />
            <div className="w-40 h-40 rounded-full bg-gradient-to-br from-gatwick-blue to-gatwick-dark flex flex-col items-center justify-center shadow-xl border-4 border-white">
              <span className="text-3xl mb-1">📸</span>
              <p className="text-white font-bold text-sm text-center leading-tight px-4">
                Enter the
                <br />
                world of
                <br />
                aircrafts
              </p>
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-3 font-medium">
            Tap to open camera
          </p>
        </div>
      </Link>

      {/* Today&apos;s Shiny */}
      <div className="bg-card-bg rounded-2xl p-4 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <h2 className="text-lg font-bold text-gatwick-dark">
            Today&apos;s Shiny ✨
          </h2>
          <span className="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded-full font-medium">
            {RARITY_LABELS.shiny}
          </span>
        </div>
        <div className="shiny-card rounded-xl p-4 flex items-center gap-4">
          <div className="w-16 h-16 bg-white/30 rounded-xl flex items-center justify-center text-3xl backdrop-blur-sm">
            {todaysShiny.airline.logo}
          </div>
          <div>
            <p className="font-bold text-white text-lg">
              {todaysShiny.airline.name}
            </p>
            <p className="text-white/80 text-sm">{todaysShiny.planeType}</p>
            <p className="text-white/70 text-xs mt-1">
              Arriving from {todaysShiny.country}
            </p>
            <p className="text-white/60 text-xs mt-0.5">
              Spot this plane today for bonus points!
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
