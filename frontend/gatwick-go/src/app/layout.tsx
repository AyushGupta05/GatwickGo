import type { Metadata, Viewport } from "next";
import "./globals.css";
import BottomNav from "@/components/BottomNav";
import { AuthProvider } from "@/lib/auth";
import AuthGuard from "@/components/AuthGuard";

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  viewportFit: "cover",
  themeColor: "#003DA5",
};

export const metadata: Metadata = {
  title: "Gatwick GO!",
  description: "Spot planes, collect cards, earn rewards at Gatwick Airport",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Gatwick GO!",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="antialiased">
        <AuthProvider>
          <AuthGuard>
            <div className="mx-auto max-w-[430px] min-h-dvh relative bg-background">
              <main className="pb-24 safe-top">
                {children}
              </main>
              <BottomNav />
            </div>
          </AuthGuard>
        </AuthProvider>
      </body>
    </html>
  );
}
