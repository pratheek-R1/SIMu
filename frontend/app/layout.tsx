import type { Metadata } from "next";
import "./globals.css";
import { StoreProvider } from "@/lib/store";
import Toasts from "@/components/Toasts";

// Fonts are vendored in public/fonts and declared with @font-face at the top of
// globals.css. next/font/google was fetching from the Google Fonts CDN at build
// time; behind a TLS-intercepting proxy that fetch fails, and Next degrades
// silently to metric-override fallbacks -- which meant the whole app rendered in
// Arial and Times without saying so. next/font/local cannot express
// unicode-range, and the rupee sign lives in the latin-ext subset, so the faces
// are declared by hand.

export const metadata: Metadata = {
  title: "Meridian Partners — Analyst Terminal",
  description:
    "A decision simulation for business analytics students. Build an investment thesis from portfolio history, then meet the half of the record you were never shown.",
};

// The latin subsets carry everything on a cold first paint. latin-ext is only
// reached for the rupee sign, which is never in the first frame.
const PRELOAD = ["/fonts/Geist-latin.woff2", "/fonts/GeistMono-latin.woff2"];

// Applied before first paint, so the page never flashes the dark default and
// then repaints light. Dark is the default because the Myelin platform's is;
// an explicit stored choice wins, and `system` follows the OS.
const THEME_BOOTSTRAP = `(function(){try{
var s=localStorage.getItem("meridian.theme");
if(s==="light"||(s==="system"&&window.matchMedia("(prefers-color-scheme: light)").matches)){
document.documentElement.setAttribute("data-theme","light");}
}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  // suppressHydrationWarning on <html> is required, not cosmetic:
  // THEME_BOOTSTRAP stamps data-theme before React hydrates, so the server
  // markup legitimately differs from what the client first reads back.
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        {PRELOAD.map((href) => (
          <link key={href} rel="preload" href={href} as="font" type="font/woff2" crossOrigin="anonymous" />
        ))}
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP }} />
      </head>
      <body>
        <StoreProvider>
          {children}
          <Toasts />
        </StoreProvider>
      </body>
    </html>
  );
}
