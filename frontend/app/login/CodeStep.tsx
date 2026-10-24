// CodeStep.tsx
"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowLeft, Loader2, RotateCw } from "lucide-react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { sendCode, verifyCode } from "./authApi";

const codeSchema = z.object({
  code: z.string().trim().regex(/^\d{6}$/, "Введите 6 цифр из SMS"),
});

type CodeFormValues = z.infer<typeof codeSchema>;

const CODE_LENGTH = 6;

type Props = {
  phone: string;
  backAction: () => void;
  /** Вызывается после успешной отправки нового кода — чтобы обновить кулдаун на уровне LoginCard */
  onCodeResentAction: () => void;
  /** Сколько секунд осталось до возможности повторной отправки */
  secondsLeft: number;
  /** Колбэк тика — управляется родителем */
  onTickAction: () => void;
  /** Сбрасывает кулдаун после успешной верификации, чтобы при возврате на PhoneStep не было блокировки */
  onVerifiedAction: () => void;
};

export function CodeStep({
  phone,
  backAction,
  onCodeResentAction,
  secondsLeft,
  onTickAction,
  onVerifiedAction,
}: Props) {
  const [isSubmitting, setIsSubmitting] = React.useState(false);
  const [isResending, setIsResending] = React.useState(false);
  const inputsRef = React.useRef<Array<HTMLInputElement | null>>([]);

  const form = useForm<CodeFormValues>({
    resolver: zodResolver(codeSchema),
    defaultValues: { code: "" },
    mode: "onSubmit",
  });

  const code = form.watch("code");

  // Сброс ошибок и поля при монтировании / смене телефона
  React.useEffect(() => {
    form.reset({ code: "" });
    form.clearErrors();
    inputsRef.current[0]?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phone]);

  // Тик кулдауна — делегируем родителю
  React.useEffect(() => {
    if (secondsLeft <= 0) return;
    const id = window.setTimeout(onTickAction, 1000);
    return () => window.clearTimeout(id);
  }, [secondsLeft, onTickAction]);

  const submitCode = React.useCallback(
    async (value: string) => {
      setIsSubmitting(true);
      form.clearErrors("root");
      try {
        await verifyCode(phone, value);
        onVerifiedAction();
        // успех — redirect / сохранение токена
      } catch (error) {
        form.setError("root", {
          message: error instanceof Error ? error.message : "Ошибка сети",
        });
        // очищаем поле и возвращаем фокус на первую ячейку
        form.setValue("code", "");
        inputsRef.current[0]?.focus();
      } finally {
        setIsSubmitting(false);
      }
    },
    [form, phone, onVerifiedAction],
  );

  // Автоотправка при заполнении всех цифр
  React.useEffect(() => {
    if (code.length === CODE_LENGTH && !isSubmitting) {
      void submitCode(code);
    }
  }, [code, isSubmitting, submitCode]);

  const setDigit = (index: number, value: string) => {
    const digits = code.split("");
    // support paste / multi-char input
    const chars = value.replace(/\D/g, "").split("");
    if (chars.length === 0) {
      digits[index] = "";
    } else {
      for (let i = 0; i < chars.length && index + i < CODE_LENGTH; i++) {
        digits[index + i] = chars[i];
      }
    }
    const next = digits.join("").slice(0, CODE_LENGTH);
    form.setValue("code", next, { shouldValidate: false });
    const focusIndex = Math.min(index + Math.max(chars.length, 1), CODE_LENGTH - 1);
    inputsRef.current[focusIndex]?.focus();
  };

  const handleKeyDown = (
    index: number,
    e: React.KeyboardEvent<HTMLInputElement>,
  ) => {
    if (e.key === "Backspace") {
      if (code[index]) {
        // очистить текущую
        const digits = code.split("");
        digits[index] = "";
        form.setValue("code", digits.join(""), { shouldValidate: false });
      } else if (index > 0) {
        // перейти назад и очистить
        const digits = code.split("");
        digits[index - 1] = "";
        form.setValue("code", digits.join(""), { shouldValidate: false });
        inputsRef.current[index - 1]?.focus();
      }
      e.preventDefault();
    } else if (e.key === "ArrowLeft" && index > 0) {
      inputsRef.current[index - 1]?.focus();
      e.preventDefault();
    } else if (e.key === "ArrowRight" && index < CODE_LENGTH - 1) {
      inputsRef.current[index + 1]?.focus();
      e.preventDefault();
    }
  };

  const onResend = async () => {
    if (isResending || secondsLeft > 0) return;
    setIsResending(true);
    form.clearErrors("root");
    try {
      await sendCode(phone);
      onCodeResentAction();
      form.setValue("code", "");
      inputsRef.current[0]?.focus();
    } catch (error) {
      form.setError("root", {
        message: error instanceof Error ? error.message : "Ошибка сети",
      });
    } finally {
      setIsResending(false);
    }
  };

  const canResend = secondsLeft <= 0 && !isResending;

  return (
    <div className="relative rounded-2xl border bg-card p-6 shadow-sm h-full">
      <button
        type="button"
        onClick={backAction}
        aria-label="Вернуться к вводу номера"
        className="absolute left-2 top-2 inline-flex size-9 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="size-5" aria-hidden="true" />
      </button>

      <form
        onSubmit={form.handleSubmit((v) => submitCode(v.code))}
        className="flex flex-col gap-5 pt-8"
        noValidate
      >
        <div className="text-center">
          <h2 className="text-lg font-semibold">Введите код из SMS</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Мы отправили код на номер{" "}
            <span className="font-medium text-foreground">{phone}</span>
          </p>
        </div>

        <div
          className="flex items-center justify-center gap-2"
          role="group"
          aria-label="Код из SMS"
        >
          {Array.from({ length: CODE_LENGTH }).map((_, index) => {
            const char = code[index] ?? "";
            const invalid = !!form.formState.errors.code;
            return (
              <input
                key={index}
                ref={(el) => {
                  inputsRef.current[index] = el;
                }}
                value={char}
                onChange={(e) => setDigit(index, e.target.value)}
                onKeyDown={(e) => handleKeyDown(index, e)}
                onFocus={(e) => e.currentTarget.select()}
                inputMode="numeric"
                autoComplete={index === 0 ? "one-time-code" : "off"}
                maxLength={CODE_LENGTH}
                aria-label={`Цифра ${index + 1} из ${CODE_LENGTH}`}
                aria-invalid={invalid}
                disabled={isSubmitting}
                className={[
                  "size-12 rounded-md border bg-background text-center text-xl font-medium",
                  "outline-none transition-colors",
                  "focus-visible:ring-2 focus-visible:ring-ring",
                  "disabled:opacity-60",
                  invalid
                    ? "border-destructive"
                    : char
                      ? "border-primary/60"
                      : "border-input",
                ].join(" ")}
              />
            );
          })}
        </div>

        {(form.formState.errors.code || form.formState.errors.root) && (
          <p role="alert" className="text-center text-sm text-destructive">
            {form.formState.errors.code?.message ??
              form.formState.errors.root?.message}
          </p>
        )}

        {isSubmitting && (
          <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            Проверяем…
          </div>
        )}

        <div className="flex items-center justify-center text-sm text-muted-foreground">
          {canResend ? (
            <button
              type="button"
              onClick={onResend}
              className="inline-flex items-center gap-2 font-medium text-foreground underline underline-offset-2 transition-colors hover:text-primary disabled:opacity-50"
            >
              <RotateCw className="size-4" aria-hidden="true" />
              Отправить код ещё раз
            </button>
          ) : (
            <span>
              Отправить новый код можно через{" "}
              <span className="tabular-nums font-medium text-foreground">
                {secondsLeft} c
              </span>
            </span>
          )}
        </div>

        {/* Скрытая кнопка submit на случай автозаполнения/скринридеров */}
        <button type="submit" className="sr-only">
          Подтвердить
        </button>
      </form>
    </div>
  );
}
