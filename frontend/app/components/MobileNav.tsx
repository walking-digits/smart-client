"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu } from "lucide-react";

import { Brand } from "@/app/components/Brand";
import { buttonVariants } from "@/app/components/ui/button";
import { navigation } from "@/app/lib/navigation";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/app/components/ui/sheet";
import { cn } from "@/app/lib/utils";

export function MobileNav() {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        className={cn(
          buttonVariants({ variant: "ghost", size: "icon" }),
          "md:hidden"
        )}
        aria-label="Открыть меню"
      >
        <Menu className="size-5" aria-hidden="true" />
      </SheetTrigger>
      <SheetContent side="right" className="w-full gap-6 sm:max-w-xs">
        <SheetHeader className="px-5 pt-5">
          <SheetTitle className="sr-only">Меню</SheetTitle>
          <SheetDescription className="sr-only">
            Навигация по сайту и вход в личный кабинет
          </SheetDescription>
          <Brand />
        </SheetHeader>

        <nav
          aria-label="Мобильная навигация"
          className="flex flex-col gap-1 px-3"
        >
          {navigation.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              onClick={() => setOpen(false)}
              className={cn(
                buttonVariants({ variant: "ghost" }),
                "justify-start"
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="mt-auto flex flex-col gap-2 border-t border-border/60 p-5">
          <Link
            href="/login"
            onClick={() => setOpen(false)}
            className={cn(buttonVariants({ variant: "outline" }), "w-full")}
          >
            Войти
          </Link>
        </div>
      </SheetContent>
    </Sheet>
  );
}
