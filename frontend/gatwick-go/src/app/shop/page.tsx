"use client";

import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { getAvailableRewards } from "@/lib/data";
import type { Reward } from "@/lib/data";
import { getPoints, redeemReward, getRedeemedRewards } from "@/lib/store";
import { useAuth, AUTH_ON } from "@/lib/auth";

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
  const { signOut, email } = useAuth();
  const rewards = getAvailableRewards();

  useEffect(() => {
    setPoints(getPoints());
    setRedeemed(getRedeemedRewards());
  }, []);

  const handleRedeem = (reward: Reward) => {
    const code = redeemReward(reward.id, reward.pointsCost);
    if (code) {
      setPoints(getPoints());
      setRedeemed(getRedeemedRewards());
      setJustRedeemed(reward.id);
      setTimeout(() => setJustRedeemed(null), 2000);
      setActiveReward({
        id: reward.id,
        name: reward.name,
        icon: reward.icon,
        code,
      });
    }
  };

  const handleViewCode = (reward: Reward) => {
    const code = redeemed[reward.id];
    if (code) {
      setActiveReward({
        id: reward.id,
        name: reward.name,
        icon: reward.icon,
        code,
      });
    }
  };

  return (
    <div className="flex flex-col gap-4 px-4 pt-4">
      {/* Header */}
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

      {/* Info */}
      <p className="text-gray-500 text-sm">
        Spend your hard-earned points on exclusive rewards!
      </p>

      {/* Rewards List */}
      <div className="flex flex-col gap-3 pb-4">
        {rewards.map((reward) => {
          const isRedeemed = reward.id in redeemed;
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
                        {wasJustRedeemed ? "🎉 Redeemed!" : "📱 View Code"}
                      </span>
                    ) : (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
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
              {/* Category tag */}
              <div className="mt-2">
                <span className="text-[10px] bg-gatwick-light text-gatwick-blue px-2 py-0.5 rounded-full font-medium">
                  {reward.category}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* QR Code / Promo Code Modal */}
      {activeReward && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-6"
          onClick={() => setActiveReward(null)}
        >
          <div
            className="bg-white rounded-2xl w-full max-w-sm p-6 flex flex-col items-center gap-5 shadow-2xl animate-in"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Reward header */}
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-xl bg-gatwick-light flex items-center justify-center text-2xl">
                {activeReward.icon}
              </div>
              <div>
                <p className="font-bold text-gatwick-dark text-base">
                  {activeReward.name}
                </p>
                <p className="text-green-600 text-xs font-medium">
                  ✅ Redeemed
                </p>
              </div>
            </div>

            {/* Divider */}
            <div className="w-full h-px bg-gray-200" />

            {/* QR Code */}
            <div className="bg-white p-4 rounded-xl border-2 border-dashed border-gray-200">
              <QRCodeSVG
                value={activeReward.code}
                size={180}
                level="M"
                bgColor="#FFFFFF"
                fgColor="#001B4D"
              />
            </div>

            {/* Promo Code */}
            <div className="text-center">
              <p className="text-[11px] text-gray-400 font-medium uppercase tracking-wider mb-1.5">
                Your Promo Code
              </p>
              <p className="font-mono text-2xl font-bold text-gatwick-dark tracking-[0.2em] select-all">
                {activeReward.code}
              </p>
            </div>

            {/* Hint */}
            <p className="text-[11px] text-gray-400 text-center leading-relaxed">
              Show this QR code or provide the promo code at the counter to
              claim your reward.
            </p>

            {/* Close button */}
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
