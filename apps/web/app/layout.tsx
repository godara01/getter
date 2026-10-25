import type { Metadata } from "next";
import Link from "next/link";

import { AuthProvider } from "@/components/AuthProvider";
import { Monitoring } from "@/components/Monitoring";

import "./globals.css";

export const metadata: Metadata = {
  title: "Getter: practice technical interviews",
  description:
    "Realistic practice interviews for backend and DevOps engineers, with honest, evidence-based feedback.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <AuthProvider>
        <header className="border-b border-line">
          <nav className="mx-auto flex max-w-4xl items-center justify-between px-4 py-3">
            <Link href="/" className="text-lg font-semibold tracking-tight">
              Getter
            </Link>
            <div className="flex gap-5 text-sm text-muted">
              <Link href="/practice/" className="hover:text-fg">
                Practice
              </Link>
              <Link href="/progress/" className="hover:text-fg">
                Progress
              </Link>
              <Link href="/pricing/" className="hover:text-fg">
                Pricing
              </Link>
              <Link href="/consents/" className="hover:text-fg">My consents</Link>
              <Link href="/sessions/" className="hover:text-fg">
                My interviews
              </Link>
            </div>
          </nav>
        </header>
        <main className="mx-auto max-w-4xl px-4 py-8">{children}</main>
        <footer className="mx-auto flex max-w-4xl gap-5 px-4 pb-8 text-sm text-muted">
          <Link href="/terms/" className="hover:text-fg">
            Terms
          </Link>
          <Link href="/privacy/" className="hover:text-fg">
            Privacy
          </Link>
          <Link href="/pricing/" className="hover:text-fg">
            Pricing
          </Link>
        </footer>
        <Monitoring />
        </AuthProvider>
      </body>
    </html>
  );
}
