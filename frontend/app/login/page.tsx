import type { Metadata } from "next";
import { MessageSquareText } from "lucide-react";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/app/components/ui/card";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = {
  title: "Вход в кабинет",
  description: "Введите номер телефона — мы отправим код для входа",
};

export default function LoginPage() {
  return (
    <main className="relative flex flex-1 items-center justify-center px-4 py-16 sm:px-6">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
      >
        <div className="absolute -top-32 right-[-10%] size-128 rounded-full bg-primary/5 blur-3xl" />
        <div className="absolute -bottom-40 left-[-15%] size-112 rounded-full bg-primary/4 blur-3xl" />
      </div>

      <Card className="w-full max-w-md gap-0 overflow-visible py-0 shadow-xl">
        <CardHeader className="gap-3 border-b border-border/60 py-6 text-center">
          <div className="mx-auto flex size-11 items-center justify-center rounded-xl bg-primary/10 text-primary">
            <MessageSquareText className="size-5" aria-hidden="true" />
          </div>
          <CardTitle className="text-2xl font-semibold tracking-tight">
            Вход в кабинет
          </CardTitle>
          <CardDescription className="text-pretty">
            Введите номер телефона — мы отправим код для входа
          </CardDescription>
        </CardHeader>

        <CardContent className="py-6">
          <LoginForm />
        </CardContent>
      </Card>
    </main>
  );
}
