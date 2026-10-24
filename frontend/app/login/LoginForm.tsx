// LoginForm.tsx
"use client";

import * as React from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { ArrowRight, Loader2 } from "lucide-react";
import { Controller, useForm } from "react-hook-form";
import { z } from "zod";

import { Button } from "@/app/components/ui/button";
import { Field, FieldError, FieldLabel } from "@/app/components/ui/field";
import { PhoneInput } from "@/app/components/ui/PhoneInput";
import { Separator } from "@/app/components/ui/separator";
import { ConsentDialog } from "./ConsentDialog";

const loginSchema = z.object({
  phone: z
    .string({
      error: (issue) =>
        issue.input === undefined
          ? "Введите номер телефона"
          : "Некорректное значение",
    })
    .min(1, "Введите номер телефона")
    .refine((value) => value.replace(/\D/g, "").length >= 10, {
      message: "Введите корректный номер телефона",
    }),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export function LoginForm() {
  const [isPending, setIsPending] = React.useState(false);

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { phone: "" },
    mode: "onSubmit",
  });

  const onSubmit = async (values: LoginFormValues) => {
    setIsPending(true);
    try {
      await new Promise((resolve) => setTimeout(resolve, 800));
      console.log("Отправка кода на номер:", values.phone);
    } finally {
      setIsPending(false);
    }
  };

  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="flex flex-col gap-5"
      noValidate
    >
      <Field data-invalid={!!form.formState.errors.phone}>
        <FieldLabel htmlFor="phone">Номер телефона</FieldLabel>
        <Controller
          name="phone"
          control={form.control}
          render={({ field }) => (
            <PhoneInput
              id="phone"
              value={field.value}
              onChange={(value) => field.onChange(value ?? "")}
              onBlur={field.onBlur}
              ref={field.ref}
              placeholder=""
              aria-invalid={!!form.formState.errors.phone}
              autoComplete="tel"
            />
          )}
        />
        {form.formState.errors.phone && (
          <FieldError>{form.formState.errors.phone.message}</FieldError>
        )}
      </Field>

      <Button
        type="submit"
        size="lg"
        className="h-11 w-full gap-2 px-6 text-base"
        disabled={isPending}
      >
        {isPending ? (
          <>
            <Loader2 className="size-4 animate-spin" aria-hidden="true" />
            Отправляем код…
          </>
        ) : (
          <>
            Получить код
            <ArrowRight className="size-4" aria-hidden="true" />
          </>
        )}
      </Button>

      <Separator />

      <p className="text-center text-xs leading-relaxed text-muted-foreground">
        Нажимая на кнопку «Получить код», вы даёте согласие на{" "}
        <ConsentDialog>
          <button
            type="button"
            className="font-medium text-foreground underline underline-offset-2 transition-colors hover:text-primary"
          >
            обработку персональных данных
          </button>
        </ConsentDialog>
      </p>
    </form>
  );
}
