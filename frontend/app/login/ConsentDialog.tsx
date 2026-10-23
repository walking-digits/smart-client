"use client";

import * as React from "react";
import { ShieldCheck } from "lucide-react";

import { Button } from "@/app/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/app/components/ui/dialog";
import { } from "@base-ui/react";

export function ConsentDialog({ children }: { children: React.ReactNode }) {
  return (
    <Dialog>
      <DialogTrigger render={<span className="inline" />} nativeButton={false}>
        {children}
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] gap-0 overflow-hidden p-0 sm:max-w-lg">
        <DialogHeader className="border-b border-border/60 px-6 py-5">
          <div className="flex items-center gap-2.5">
            <span className="flex size-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
              <ShieldCheck className="size-4.5" aria-hidden="true" />
            </span>
            <DialogTitle>Согласие на обработку персональных данных</DialogTitle>
          </div>
        </DialogHeader>

        <div className="max-h-[55vh] overflow-y-auto px-6 py-5">
          <DialogDescription className="text-pretty">
            Настоящим я, субъект персональных данных, свободно, своей волей и в
            своём интересе даю согласие на обработку моих персональных данных.
          </DialogDescription>

          <div className="mt-4 flex flex-col gap-3 text-sm leading-relaxed text-muted-foreground">
            <p>
              <span className="font-medium text-foreground">Оператор:</span>{" "}
              ООО «Пример», ИНН 0000000000, адрес: г. Москва.
            </p>
            <p>
              <span className="font-medium text-foreground">
                Цель обработки:
              </span>{" "}
              идентификация пользователя, предоставление доступа к личному
              кабинету, направление SMS-кодов для входа, а также информирование
              о продуктах и услугах.
            </p>
            <p>
              <span className="font-medium text-foreground">
                Перечень данных:
              </span>{" "}
              номер мобильного телефона, данные об устройстве и сессии,
              технические данные о посещениях.
            </p>
            <p>
              <span className="font-medium text-foreground">
                Действия с данными:
              </span>{" "}
              сбор, запись, систематизация, накопление, хранение, уточнение,
              извлечение, использование, передача (в случаях, предусмотренных
              законом), обезличивание, блокирование, удаление, уничтожение.
            </p>
            <p>
              <span className="font-medium text-foreground">Срок:</span> до
              достижения целей обработки либо до отзыва согласия.
            </p>
            <p>
              Согласие может быть отозвано в любой момент путём направления
              письменного обращения оператору по адресу, указанному выше, либо
              через настройки личного кабинета.
            </p>
          </div>
        </div>

        <DialogFooter className="border-t border-border/60 px-6 py-4">
          <DialogClose render={<Button variant="outline" className="w-full sm:w-auto" />}>
            Понятно
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
