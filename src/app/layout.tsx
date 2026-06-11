import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "QVeris Social Studio",
  description: "Review and publish data-driven social content from QVeris.",
  icons: {
    icon: "/logo-color.avif",
  },
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
