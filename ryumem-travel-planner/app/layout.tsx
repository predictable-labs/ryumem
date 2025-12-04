import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { MemoryStoreProvider } from "@/lib/memory-store-context";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Ryumem Travel Planner Demo",
  description: "Interactive demo showcasing Ryumem's memory and tool tracking capabilities",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <MemoryStoreProvider>{children}</MemoryStoreProvider>
      </body>
    </html>
  );
}
