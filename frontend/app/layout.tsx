import type { Metadata } from "next";
import Link from "next/link";
import { Inter } from "next/font/google";

import "./globals.css";

import { Brand } from "@/app/components/Brand";
import { Header } from "@/app/components/Header";
import { ThemeProvider } from "@/app/components/ThemeProvider";
import { navigation } from "@/app/lib/navigation";
import { cn } from "@/app/lib/utils";

const inter = Inter({
  subsets: ["latin", "cyrillic"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Умный кабинет — кредиты для малого бизнеса",
    template: "%s — Умный кабинет",
  },
  description:
    "Персональные рекомендации по кредитам для бизнеса, онлайн-заявки и статус рассмотрения в одном личном кабинете.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="ru"
      suppressHydrationWarning
      className={cn("h-full", "antialiased", inter.variable, "font-sans")}
    >
      <body className="flex min-h-full flex-col bg-background text-foreground">
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <Header />
          <div className="flex flex-1 flex-col">{children}</div>
          <footer className="border-t border-border/60">
            <div className="mx-auto flex w-full max-w-6xl flex-col items-center justify-between gap-4 px-4 py-6 sm:flex-row sm:px-6">
              <Brand />
              <nav
                aria-label="Навигация в подвале"
                className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2 text-sm text-muted-foreground"
              >
                {navigation.map((item) => (
                  <Link
                    key={item.href}
                    href={item.href}
                    className="transition-colors hover:text-foreground"
                  >
                    {item.label}
                  </Link>
                ))}
              </nav>
              <p className="text-sm text-muted-foreground">
                © 2026 Умный кабинет
              </p>
            </div>
          </footer>
        </ThemeProvider>
      </body>
    </html>
  );
}
