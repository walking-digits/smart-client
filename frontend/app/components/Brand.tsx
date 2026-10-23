import Link from "next/link";
import { Landmark } from "lucide-react";

import { cn } from "@/app/lib/utils";

export function Brand({ className }: { className?: string }) {
  return (
    <Link
      href="/"
      className={cn("group flex items-center gap-2.5", className)}
      aria-label="Умный кабинет — на главную"
    >
      <span className="flex size-9 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm transition-transform group-hover:scale-105">
        <Landmark className="size-5" aria-hidden="true" />
      </span>
      <span className="flex flex-col">
        <span className="text-sm leading-tight font-semibold tracking-tight">
          Умный кабинет
        </span>
        <span className="text-[11px] leading-tight text-muted-foreground">
          Кредиты для бизнеса
        </span>
      </span>
    </Link>
  );
}
