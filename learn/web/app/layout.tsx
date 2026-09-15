import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "Aave V3 USDC, read from raw state · defi-sec-lab",
  description:
    "Interactive walkthrough: verify an Arbitrum fork, then read Aave V3's native-USDC reserve down to raw storage slots.",
  icons: { icon: "/icon.svg" },
};

export const viewport: Viewport = {
  colorScheme: "dark light",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f5f7fa" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0f15" },
  ],
};

// Applies a saved theme choice before first paint (no flash). With no saved choice, CSS follows the browser's
// prefers-color-scheme. Dark is the fallback only where that media feature is unsupported: current browsers
// always report light or dark (Chromium reports light when the OS has no preference).
const themeBootstrap =
  'try{var t=localStorage.getItem("theme");if(t==="light"||t==="dark"){document.documentElement.dataset.theme=t}}catch(e){}';

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeBootstrap }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
