import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agave Field — Field Operations",
  description:
    "Premium field operations & traceability platform for agave production: work orders, evidence, carbon, and review.",
};

// Root layout is intentionally chrome-free. The admin app shell lives in the
// (app) route group; the public worker page (/complete/[token]) renders bare.
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans">{children}</body>
    </html>
  );
}
