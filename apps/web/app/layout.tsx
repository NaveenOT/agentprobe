import type { Metadata } from "next";
import "./globals.css";
import "./tokens.css";

export const metadata: Metadata = {
  title: "AgentProbe Control Room",
  description: "Authorized prompt injection testing dashboard",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
