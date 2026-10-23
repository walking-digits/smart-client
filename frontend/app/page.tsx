import Link from "next/link";
import {
  ArrowRight,
  BarChart3,
  BellRing,
  CheckCircle2,
  Clock,
  FileText,
  ShieldCheck,
  Sparkles,
  Wallet,
} from "lucide-react";

import { Badge } from "@/app/components/ui/badge";
import { buttonVariants } from "@/app/components/ui/button";
import {
  Card,
  CardAction,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/app/components/ui/card";
import { Separator } from "@/app/components/ui/separator";
import { cn } from "@/app/lib/utils";

const features = [
  {
    icon: BarChart3,
    title: "Подбор кредита",
    text: "Сравните программы банков по ставке, сроку и сумме — без лишних звонков и визитов.",
  },
  {
    icon: FileText,
    title: "Онлайн-заявки",
    text: "Введите данные один раз и подавайте сразу несколько заявок на разные продукты.",
  },
  {
    icon: BellRing,
    title: "Статус в реальном времени",
    text: "Следите за рассмотрением заявки и получайте уведомления о решении банка.",
  },
  {
    icon: ShieldCheck,
    title: "Документы под защитой",
    text: "Храните справки и отчётность в кабинете — они понадобятся при повторной заявке.",
  },
];

const steps = [
  {
    title: "Заполните профиль",
    text: "Укажите данные компании — это займёт несколько минут.",
  },
  {
    title: "Сравните предложения",
    text: "Мы покажем подходящие кредиты с учётом ваших показателей.",
  },
  {
    title: "Отправьте заявку",
    text: "Подайте заявку онлайн в один или несколько банков сразу.",
  },
  {
    title: "Получите решение",
    text: "Отслеживайте статус и подпишите договор в кабинете.",
  },
];

const programs = [
  { name: "Кредитная линия", rate: "от 12,5%", icon: Wallet },
  { name: "Оборотный кредит", rate: "от 14,0%", icon: BarChart3 },
  { name: "Инвестиционный", rate: "от 15,5%", icon: Sparkles },
];

export default function Home() {
  return (
    <main className="flex flex-1 flex-col">
      <section className="relative overflow-hidden">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 -z-10 overflow-hidden"
        >
          <div className="absolute -top-32 right-[-10%] size-128 rounded-full bg-primary/5 blur-3xl" />
          <div className="absolute -bottom-40 left-[-15%] size-112 rounded-full bg-primary/4 blur-3xl" />
        </div>

        <div className="mx-auto grid w-full max-w-6xl items-center gap-14 px-4 py-16 sm:px-6 lg:grid-cols-2 lg:py-24">
          <div className="flex flex-col items-start gap-6">
            <Badge
              variant="secondary"
              className="h-7 gap-2 rounded-full px-3 text-xs font-normal"
            >
              <Sparkles className="size-3.5" aria-hidden="true" />
              Умный кредитный кабинет предпринимателя
            </Badge>

            <h1 className="max-w-xl text-4xl font-semibold tracking-tight text-balance sm:text-5xl lg:text-6xl">
              Кредиты для малого бизнеса —{" "}
              <span className="text-muted-foreground">
                просто и прозрачно
              </span>
            </h1>

            <p className="max-w-lg text-lg leading-relaxed text-muted-foreground text-pretty">
              Получайте персональные рекомендации от банка, подавайте заявки
              онлайн и следите за их статусом в одном личном кабинете.
            </p>

            <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
              <Link
                href="/login"
                className={cn(
                  buttonVariants({ size: "lg" }),
                  "h-11 gap-2 px-6 text-base"
                )}
              >
                Войти в кабинет
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
              <Link
                href="/loans"
                className={cn(
                  buttonVariants({ variant: "outline", size: "lg" }),
                  "h-11 px-6 text-base"
                )}
              >
                Смотреть варианты
              </Link>
            </div>

            <dl className="mt-2 grid w-full max-w-md grid-cols-3 gap-4 border-t border-border/60 pt-6">
              <div>
                <dt className="text-xs text-muted-foreground">
                  Банков-партнёров
                </dt>
                <dd className="mt-1 text-2xl font-semibold tracking-tight">
                  12+
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">На заявку</dt>
                <dd className="mt-1 text-2xl font-semibold tracking-tight">
                  5 мин
                </dd>
              </div>
              <div>
                <dt className="text-xs text-muted-foreground">Доступ</dt>
                <dd className="mt-1 text-2xl font-semibold tracking-tight">
                  24/7
                </dd>
              </div>
            </dl>
          </div>

          <div className="relative mx-auto w-full max-w-md lg:ml-auto">
            <div
              aria-hidden="true"
              className="absolute -inset-6 rounded-[2rem] bg-linear-to-br from-primary/10 via-transparent to-primary/5 blur-2xl"
            />
            <Card className="relative gap-0 overflow-visible py-0 shadow-xl">
              <CardHeader className="border-b border-border/60 py-5">
                <div className="flex items-center justify-between gap-3">
                  <CardDescription>Доступный лимит</CardDescription>
                  <Badge
                    variant="secondary"
                    className="gap-1 text-emerald-700 dark:text-emerald-400"
                  >
                    <CheckCircle2 className="size-3" aria-hidden="true" />
                    Одобрено
                  </Badge>
                </div>
                <CardTitle className="text-3xl font-semibold tracking-tight">
                  4 500 000 ₽
                </CardTitle>
              </CardHeader>

              <CardContent className="gap-5 py-5">
                <div>
                  <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
                    <span>Использовано</span>
                    <span>1 200 000 ₽</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-muted">
                    <div className="h-full w-[27%] rounded-full bg-primary" />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-muted/60 p-3">
                    <p className="text-xs text-muted-foreground">Ставка от</p>
                    <p className="mt-1 text-lg font-semibold">12,5%</p>
                  </div>
                  <div className="rounded-lg bg-muted/60 p-3">
                    <p className="text-xs text-muted-foreground">Срок до</p>
                    <p className="mt-1 text-lg font-semibold">36 мес</p>
                  </div>
                </div>

                <Separator />

                <div className="flex flex-col gap-3">
                  <p className="text-xs font-medium text-muted-foreground">
                    Подходящие программы
                  </p>
                  {programs.map((program) => {
                    const Icon = program.icon;
                    return (
                      <div
                        key={program.name}
                        className="flex items-center justify-between gap-3"
                      >
                        <div className="flex items-center gap-2.5">
                          <span className="flex size-8 items-center justify-center rounded-lg bg-muted">
                            <Icon
                              className="size-4 text-muted-foreground"
                              aria-hidden="true"
                            />
                          </span>
                          <span className="text-sm font-medium">
                            {program.name}
                          </span>
                        </div>
                        <span className="text-sm text-muted-foreground">
                          {program.rate}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      <section
        id="features"
        className="border-y border-border/60 bg-muted/40"
      >
        <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
          <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 text-center">
            <p className="text-sm font-medium text-muted-foreground">
              Возможности
            </p>
            <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
              Всё для кредитования бизнеса
            </h2>
            <p className="text-muted-foreground text-pretty">
              Один кабинет вместо десятка звонков, писем и поездок в отделения.
            </p>
          </div>

          <div className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {features.map((feature) => {
              const Icon = feature.icon;
              return (
                <Card
                  key={feature.title}
                  size="sm"
                  className="h-full bg-card/70 transition-shadow hover:shadow-md"
                >
                  <CardHeader>
                    <CardAction>
                      <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                        <Icon className="size-4.5" aria-hidden="true" />
                      </span>
                    </CardAction>
                    <CardTitle className="pr-10">
                      {feature.title}
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <p className="text-muted-foreground">{feature.text}</p>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>
      </section>

      <section id="how-it-works" className="scroll-mt-20">
        <div className="mx-auto w-full max-w-6xl px-4 py-16 sm:px-6 lg:py-24">
          <div className="mx-auto flex max-w-2xl flex-col items-center gap-3 text-center">
            <p className="text-sm font-medium text-muted-foreground">
              Процесс
            </p>
            <h2 className="text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
              Как это работает
            </h2>
            <p className="text-muted-foreground text-pretty">
              От регистрации до решения банка — четыре понятных шага.
            </p>
          </div>

          <ol className="mt-12 grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
            {steps.map((step, index) => (
              <li key={step.title} className="flex flex-col gap-3">
                <span className="flex size-10 items-center justify-center rounded-full border border-border bg-background font-mono text-sm font-medium shadow-xs">
                  {String(index + 1).padStart(2, "0")}
                </span>
                <h3 className="text-lg font-semibold">{step.title}</h3>
                <p className="text-sm leading-relaxed text-muted-foreground">
                  {step.text}
                </p>
              </li>
            ))}
          </ol>

          <div className="mt-12 flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <Clock className="size-4" aria-hidden="true" />
            Среднее время заполнения заявки — около 5 минут
          </div>
        </div>
      </section>

      <section className="px-4 pb-16 sm:px-6 lg:pb-24">
        <div className="relative mx-auto max-w-6xl overflow-hidden rounded-3xl bg-primary px-6 py-14 text-center text-primary-foreground sm:px-12">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 opacity-[0.07]"
            style={{
              backgroundImage:
                "radial-gradient(circle at 1px 1px, currentColor 1px, transparent 0)",
              backgroundSize: "24px 24px",
            }}
          />
          <div className="relative flex flex-col items-center gap-5">
            <h2 className="max-w-xl text-3xl font-semibold tracking-tight text-balance sm:text-4xl">
              Готовы начать?
            </h2>
            <p className="max-w-lg text-pretty text-primary-foreground/80">
              Зарегистрируйтесь и подайте первую заявку — это займёт несколько
              минут.
            </p>
            <div className="mt-1 flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
              <Link
                href="/login"
                className={cn(
                  buttonVariants({ variant: "secondary", size: "lg" }),
                  "h-11 gap-2 px-6 text-base"
                )}
              >
                Войти в кабинет
                <ArrowRight className="size-4" aria-hidden="true" />
              </Link>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
