import type { Metadata, Viewport } from "next";
import "leaflet/dist/leaflet.css";

import { AuthProvider } from "@/components/AuthProvider";
import { CivicChatbot } from "@/components/CivicChatbot";
import { Footer } from "@/components/Footer";
import { Header } from "@/components/Header";

import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "CivicOps AI · Waste operations",
    template: "%s · CivicOps AI",
  },
  description:
    "CivicOps AI turns fragmented citizen waste reports into reviewed incidents, assigned work orders and verified resolution.",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: "#245b43",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <a className="skip-link" href="#main-content">
          Skip to main content
        </a>
        <AuthProvider>
          <Header />
          <main id="main-content">{children}</main>
          <Footer />
          <CivicChatbot />
        </AuthProvider>
      </body>
    </html>
  );
}
