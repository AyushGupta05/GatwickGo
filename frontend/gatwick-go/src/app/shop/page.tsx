"use client";

import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { getAvailableRewards, type Reward } from "@/lib/data";
import {
  applyManualShopCreditTopUp,
  getPoints,
  getRedeemedRewards,
  redeemReward,
  subscribeToProgressStore,
} from "@/lib/store";
import { readProgressSnapshot, subscribeToProgressPolling } from "@/lib/progressSync";
import { useAuth } from "@/lib/auth";

const PRESET_REWARDS = getAvailableRewards();

interface ActiveReward {
  id: string;
  name: string;
  icon: string;
  code: string;
}

export default function ShopPage() {
  const [points, setPoints] = useState(0);
  const [redeemed, setRedeemed] = useState<Record<string, string>>({});
  const [justRedeemed, setJustRedeemed] = useState<string | null>(null);
  const [activeReward, setActiveReward] = useState<ActiveReward | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { signOut } = useAuth();
  const rewards = PRESET_REWARDS;

  useEffect(() => {
    applyManualShopCreditTopUp();

    const sync = () => {
      const snapshot = readProgressSnapshot();
      setPoints(snapshot.points);
      setRedeemed(snapshot.redeemed);
    };

    sync();
    const unsubscribeStore = subscribeToProgressStore(sync);
    const unsubscribePolling = subscribeToProgressPolling(sync);
    return () => {
      unsubscribeStore();
      unsubscribePolling();
    };
  }, []);

  const openRewardModal = (reward: Reward, promoCode: string) => {
    setActiveReward({
      id: reward.id,
      name: reward.name,
      icon: reward.icon,
      code: promoCode,
    });
  };

  const handleRedeem = async (reward: Reward) => {
    setError(null);
    const promoCode = redeemReward(reward.id, reward.pointsCost);
    if (!promoCode) {
      setError("Not enough points to redeem this reward.");
      return;
    }

    const nextPoints = getPoints();
    const nextRedeemed = getRedeemedRewards();

    setPoints(nextPoints);
    setRedeemed(nextRedeemed);
    setJustRedeemed(reward.id);
    window.setTimeout(() => setJustRedeemed(null), 2000);
    openRewardModal(reward, promoCode);
  };

  const handleViewCode = (reward: Reward) => {
    const promoCode = redeemed[reward.id];
    if (promoCode) {
      openRewardModal(reward, promoCode);
    }
  };

  return (
    <div className="flex flex-col gap-4 px-4 pt-4">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gatwick-dark">Rewards Shop</h1>
        <div className="flex items-center gap-3">
          <div className="bg-gatwick-blue text-white px-3 py-1.5 rounded-full text-sm font-bold">
            {points} pts
          </div>
          <button
            onClick={signOut}
            className="text-xs text-gatwick-red font-medium"
          >
            Sign out
          </button>
        </div>
      </header>

      <p className="text-gray-500 text-sm">
        Spend your hard-earned points on exclusive rewards!
      </p>

      {error && (
        <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-xs text-gatwick-red">
          {error}
        </p>
      )}

      <div className="flex flex-col gap-3 pb-4">
        {rewards.map((reward) => {
          const promoCode = redeemed[reward.id];
          const isRedeemed = Boolean(promoCode);
          const canAfford = points >= reward.pointsCost;
          const wasJustRedeemed = justRedeemed === reward.id;

          return (
            <div
              key={reward.id}
              className={`bg-card-bg rounded-2xl p-4 shadow-sm border transition-all ${
                isRedeemed
                  ? "border-green-200 bg-green-50 cursor-pointer"
                  : "border-gray-100"
              }`}
              onClick={isRedeemed ? () => handleViewCode(reward) : undefined}
            >
              <div className="flex items-start gap-4">
                <div className="w-14 h-14 rounded-xl bg-gatwick-light flex items-center justify-center text-2xl shrink-0">
                  {reward.icon}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <p className="font-bold text-gatwick-dark text-sm">
                        {reward.name}
                      </p>
                      <p className="text-gray-500 text-xs mt-0.5">
                        {reward.description}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center justify-between mt-3">
                    <span className="text-gatwick-blue font-bold text-sm">
                      {reward.pointsCost} pts
                    </span>
                    {isRedeemed ? (
                      <span className="text-green-600 font-bold text-xs bg-green-100 px-3 py-1.5 rounded-full">
                        {wasJustRedeemed ? "Redeemed!" : "View Code"}
                      </span>
                    ) : (
                      <button
                        onClick={(event) => {
                          event.stopPropagation();
                          handleRedeem(reward);
                        }}
                        disabled={!canAfford}
                        className={`px-4 py-1.5 rounded-full text-xs font-bold transition-colors ${
                          canAfford
                            ? "bg-gatwick-red text-white active:bg-red-700"
                            : "bg-gray-200 text-gray-400 cursor-not-allowed"
                        }`}
                      >
                        Redeem
                      </button>
                    )}
                  </div>
                </div>
              </div>
              <div className="mt-2">
                <span className="text-[10px] bg-gatwick-light text-gatwick-blue px-2 py-0.5 rounded-full font-medium">
                  {reward.category}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {activeReward && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-6"
          onClick={() => setActiveReward(null)}
        >
          <div
            className="bg-white rounded-2xl w-full max-w-sm p-6 flex flex-col items-center gap-5 shadow-2xl animate-in"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gatwick-light flex items-center justify-center text-2xl">
                {activeReward.icon}
              </div>
              <div>
                <p className="font-bold text-gatwick-dark text-base">
                  {activeReward.name}
                </p>
                <p className="text-green-600 text-xs font-medium">Claimed</p>
              </div>
            </div>

            <div className="w-full h-px bg-gray-200" />

            <div className="bg-white p-4 rounded-xl border-2 border-dashed border-gray-200">
              <QRCodeSVG
                value={activeReward.code}
                size={180}
                level="M"
                bgColor="#FFFFFF"
                fgColor="#001B4D"
              />
            </div>

            <div className="text-center">
              <p className="text-[11px] text-gray-400 font-medium uppercase tracking-wider mb-1.5">
                Your Promo Code
              </p>
              <p className="font-mono text-2xl font-bold text-gatwick-dark tracking-[0.2em] select-all">
                {activeReward.code}
              </p>
            </div>

            <p className="text-[11px] text-gray-400 text-center leading-relaxed">
              Show this QR code or provide the promo code at the counter to
              claim your reward.
            </p>

            <button
              onClick={() => setActiveReward(null)}
              className="w-full bg-gatwick-blue text-white py-3 rounded-xl font-bold text-sm active:bg-blue-800 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
