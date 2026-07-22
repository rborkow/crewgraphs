import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Archivo, Public_Sans, Spline_Sans_Mono } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { SiteHeader } from "@/components/site-header";
import { SiteFooter } from "@/components/site-footer";

// Display: Archivo, with the width axis so eyebrows/wordmarks can run expanded.
const archivo = Archivo({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-archivo",
  axes: ["wdth"]
});

// Body: Public Sans (variable weight).
const publicSans = Public_Sans({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-public-sans"
});

// Data numerals: Spline Sans Mono (monospace → naturally tabular).
const splineMono = Spline_Sans_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-spline-mono"
});

export const metadata: Metadata = {
  title: "CrewGraphs — rowing club reference",
  description:
    "A trusted reference for US rowing organizations: canonical identity and IRS financial context, every displayed number carrying its source."
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" className={`${archivo.variable} ${publicSans.variable} ${splineMono.variable}`}>
      <body className="flex min-h-screen flex-col">
        <Providers>
          <SiteHeader />
          <div className="flex-1">{children}</div>
          <SiteFooter />
        </Providers>
      </body>
    </html>
  );
}
