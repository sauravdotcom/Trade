import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trade Signal AI",
  description: "Live options trading signal dashboard for NIFTY and BANKNIFTY"
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
