import * as React from "react";
import { Input } from "@/app/components/ui/input";
import { cn } from "@/app/lib/utils";

export interface PhoneInputProps
  extends Omit<React.ComponentPropsWithoutRef<"input">, "onChange" | "value"> {
  value?: string;
  onChange?: (value: string) => void;
}

function extractNationalDigits(input: string): string {
  const digits = input.replace(/\D/g, "");

  if (digits.startsWith("7") && digits.length >= 11) {
    return digits.slice(1, 11);
  }
  if (digits.startsWith("8") && digits.length >= 11) {
    return digits.slice(1, 11);
  }
  if (digits.startsWith("7") && digits.length === 11) {
    return digits.slice(1);
  }
  if (digits.startsWith("8") && digits.length === 11) {
    return digits.slice(1);
  }
  if (digits.length === 10 && !digits.startsWith("7")) {
    return digits;
  }
  if ((digits.startsWith("7") || digits.startsWith("8")) && digits.length > 1) {
    return digits.slice(1, 11);
  }

  return digits.slice(0, 10);
}

function formatRussianNumber(nationalDigits: string): string {
  if (!nationalDigits) return "";

  let result = "+7 (";
  result += nationalDigits.substring(0, 3);

  if (nationalDigits.length > 3) {
    result += ") " + nationalDigits.substring(3, 6);
  }
  if (nationalDigits.length > 6) {
    result += "-" + nationalDigits.substring(6, 8);
  }
  if (nationalDigits.length > 8) {
    result += "-" + nationalDigits.substring(8, 10);
  }

  return result;
}

const PhoneInput = React.forwardRef<HTMLInputElement, PhoneInputProps>(
  ({ className, value = "", onChange, ...props }, ref) => {
    const [nationalDigits, setNationalDigits] = React.useState(() =>
      extractNationalDigits(value)
    );

    React.useEffect(() => {
      setNationalDigits(extractNationalDigits(value));
    }, [value]);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      const inputValue = e.target.value;

      if (inputValue === "" || inputValue === "+7 (" || inputValue === "+7") {
        setNationalDigits("");
        onChange?.("");
        return;
      }

      const newDigits = extractNationalDigits(inputValue);

      if (newDigits.length <= 10) {
        setNationalDigits(newDigits);
        const backendValue = newDigits.length > 0 ? `+7${newDigits}` : "";
        onChange?.(backendValue);
      }
    };

    const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
      const target = e.currentTarget;
      const selectionStart = target.selectionStart || 0;
      const selectionEnd = target.selectionEnd || 0;

      if (nationalDigits.length === 0) {
        if (e.key === "Backspace" || e.key === "Delete") {
          e.preventDefault();
        }
        return;
      }

      if (e.key === "Backspace" && selectionStart <= 4 && selectionStart === selectionEnd) {
        e.preventDefault();
      }
      if (e.key === "Delete" && selectionStart < 4 && selectionStart === selectionEnd) {
        e.preventDefault();
      }
    };

    const displayValue = formatRussianNumber(nationalDigits);

    return (
      <div className={cn("flex items-center w-full", className)}>
        <span
          className={cn(
            "flex h-9 items-center gap-1 rounded-s-md border border-r-0 border-input bg-transparent px-3 select-none",
            props.disabled ? "opacity-50" : "cursor-default"
          )}
          aria-hidden="true"
        >
          <svg
            className="h-4 w-6 overflow-hidden rounded-sm shadow-sm"
            viewBox="0 0 9 6"
            xmlns="http://www.w3.org/2000/svg"
          >
            <rect fill="#ffffff" width="9" height="6" />
            <rect fill="#0039a6" y="2" width="9" height="4" />
            <rect fill="#d52b1e" y="4" width="9" height="2" />
          </svg>
        </span>

        {/* Текстовое поле ввода */}
        <Input
          {...props}
          ref={ref}
          type="tel"
          value={displayValue}
          placeholder="+7 ("
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          className={cn(
            "rounded-s-none rounded-e-md border-l-0 focus-visible:z-10"
          )}
        />
      </div>
    );
  }
);

PhoneInput.displayName = "PhoneInput";

export { PhoneInput };
