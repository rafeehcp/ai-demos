import type { Metadata, Viewport } from "next";
import { Newsreader, Schibsted_Grotesk } from "next/font/google";
import "./globals.css";

const serif = Newsreader({
  variable: "--font-serif",
  subsets: ["latin"],
  style: ["normal", "italic"],
  axes: ["opsz"],
});

const sans = Schibsted_Grotesk({
  variable: "--font-sans",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: {
    default: "AI features for your app | Mohamed Rafeeh Ibrahim",
    template: "%s | Mohamed Rafeeh Ibrahim",
  },
  description: "Working demos of AI features added to Python and JavaScript apps.",
};

export const viewport: Viewport = {
  colorScheme: "light dark",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable}`}>
      <body>{children}</body>
    </html>
  );
}
