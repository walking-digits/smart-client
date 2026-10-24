// LoginCard.tsx
"use client";

import * as React from "react";
import { PhoneStep } from "./PhoneStep";
import { CodeStep } from "./CodeStep";

type Step = "phone" | "code";

const RESEND_SECONDS = 60;

export function LoginCard() {
  const [step, setStep] = React.useState<Step>("phone");
  const [phone, setPhone] = React.useState("");
  // timestamp (ms) до которого повторная отправка запрещена
  const [resendAvailableAt, setResendAvailableAt] = React.useState(0);
  // «тикер» для пересчёта секунд
  const [, forceTick] = React.useReducer((n: number) => n + 1, 0);

  const isCodeStep = step === "code";

  // общий тик, пока кулдаун активен
  React.useEffect(() => {
    if (resendAvailableAt <= Date.now()) return;
    const id = window.setTimeout(forceTick, 1000);
    return () => window.clearTimeout(id);
  });

  const secondsLeft = Math.max(
    0,
    Math.ceil((resendAvailableAt - Date.now()) / 1000),
  );

  const startCooldown = () => {
    setResendAvailableAt(Date.now() + RESEND_SECONDS * 1000);
    forceTick();
  };

  const handleCodeSent = (submittedPhone: string) => {
    setPhone(submittedPhone);
    setStep("code");
    startCooldown();
  };

  return (
    <div className="relative w-full max-w-sm" style={{ perspective: "1200px" }}>
      <div
        className="relative grid w-full transition-transform duration-700 ease-in-out"
        style={{
          transformStyle: "preserve-3d",
          transform: isCodeStep ? "rotateY(180deg)" : "rotateY(0deg)",
        }}
      >
        <div
          className="col-start-1 row-start-1"
          style={{ backfaceVisibility: "hidden" }}
          aria-hidden={isCodeStep}
        >
          <PhoneStep
            defaultPhone={phone}
            codeSentAction={handleCodeSent}
            secondsLeft={secondsLeft}
            onCooldownResetAction={() => setResendAvailableAt(0)}
          />
        </div>

        <div
          className="col-start-1 row-start-1"
          style={{
            backfaceVisibility: "hidden",
            transform: "rotateY(180deg)",
          }}
          aria-hidden={!isCodeStep}
        >
          <CodeStep
            phone={phone}
            backAction={() => setStep("phone")}
            secondsLeft={secondsLeft}
            onTickAction={forceTick}
            onCodeResentAction={startCooldown}
            onVerifiedAction={() => setResendAvailableAt(0)}
          />
        </div>
      </div>
    </div>
  );
}
