// PhoneStep.tsx
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
import { sendCode } from "./authApi";

const loginSchema = z.object({
  phone: z
    .string()
    .min(1, "Введите номер телефона")
    .refine((value) => value.replace(/\D/g, "").length >= 11, {
      message: "Введите корректный номер телефона",
    }),
});

export type LoginFormValues = z.infer<typeof loginSchema>;

type Props = {
  defaultPhone?: string;
  codeSentAction: (phone: string) => void;
  /** Сколько секунд осталось до возможности повторной отправки */
  secondsLeft: number;
  /** Сброс кулдауна (например, если сервер не блокирует) */
  onCooldownResetAction?: () => void;
};

export function PhoneStep({
  defaultPhone = "",
  codeSentAction,
  secondsLeft,
}: Props) {
  const [isPending, setIsPending] = React.useState(false);

  const form = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { phone: defaultPhone },
    mode: "onSubmit",
  });

  // очищаем ошибки при монтировании/смене телефона
  React.useEffect(() => {
    form.reset({ phone: defaultPhone });
    form.clearErrors();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [defaultPhone]);

  const onCooldownBlocked = () => {
    form.setError("root", {
      message: `Запросить код повторно можно через ${secondsLeft} c`,
    });
  };

  const onSubmit = async (values: LoginFormValues) => {
    form.clearErrors("root");

    if (secondsLeft > 0) {
      onCooldownBlocked();
      return;
    }

    setIsPending(true);
    try {
      await sendCode(values.phone);
      codeSentAction(values.phone);
    } catch (error) {
      form.setError("root", {
        message: error instanceof Error ? error.message : "Ошибка сети",
      });
    } finally {
      setIsPending(false);
    }
  };

  return (
    <form
      onSubmit={form.handleSubmit(onSubmit)}
      className="flex flex-col gap-5 rounded-2xl border bg-card p-6 shadow-sm"
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

      {form.formState.errors.root && (
        <p
          role="alert"
          className="text-center text-sm text-destructive"
        >
          {form.formState.errors.root.message}
        </p>
      )}

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
