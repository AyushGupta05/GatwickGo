# ✈️ Gatwick GO!

Gatwick GO! is a mobile-first web experience that turns airport gate waiting time into a fun, interactive game. While waiting for their flight, passengers can spot and “capture” real planes outside the terminal windows, earn points, and unlock airport and airline sponsored rewards.

Designed specifically for **15–30 minutes of gate waiting**, Gatwick GO! makes the airport experience more engaging, memorable, and rewarding.

---

## 🧠 The Idea

Passengers already spend time looking out the window at planes while waiting to board. Gatwick GO! gamifies this natural behavior by letting users capture aircraft, collect points based on airline and destination rarity, and work toward rewards such as lounge perks, vouchers, or airline upgrades.

The experience is lightweight, fast to join, and requires **no app download**.

---

## 🚀 Features

- Mobile-first web app (no installation required)
- Email sign-in using Supabase
- Plane “capture” mechanic inspired by games like Pokemon GO
- Points and rarity system (common vs rare vs shiny flights)
- Reward progression system for airport & airline perks
- Built to scale with airline and airport partnerships

---

## 🛠️ How we built it

- **Frontend:** Next.js (App Router), React
- **Backend & Auth:** Supabase (email magic-link authentication)
- **Database:** Supabase Postgres (users, points, captures)
- **Hosting:** Local development (deployable to Vercel)

The system is designed so authentication and data storage are production-ready, while the game logic can be iterated on rapidly.
