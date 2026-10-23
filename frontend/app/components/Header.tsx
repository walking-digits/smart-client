import Link from "next/link";

import { Brand } from "@/app/components/Brand";
import { MobileNav } from "@/app/components/MobileNav";
import { buttonVariants } from "@/app/components/ui/button";
import ThemeToggle from "@/app/components/ui/ThemeToggle";
import { navigation } from "@/app/lib/navigation";
import { cn } from "@/app/lib/utils";

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-border/60 bg-background/80 backdrop-blur-md supports-backdrop-filter:bg-background/60">
      <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <Brand />

        <nav
          aria-label="Основная навигация"
          className="hidden items-center gap-1 md:flex"
        >
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                buttonVariants({ variant: "ghost", size: "sm" }),
                "text-muted-foreground hover:text-foreground"
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="flex items-center gap-2">
          <ThemeToggle />
          <span
            aria-hidden="true"
            className="hidden h-6 w-px bg-border sm:block"
          />
          <Link
            href="/login"
            className={cn(
              buttonVariants({ variant: "ghost", size: "sm" }),
              "hidden sm:inline-flex"
            )}
          >
            Войти
          </Link>
          <MobileNav />
        </div>
      </div>
    </header>
  );
}
