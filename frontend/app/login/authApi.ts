// authApi.ts
type ApiError = { message?: string };

async function post<TBody extends object>(
  path: string,
  body: TBody,
): Promise<void> {
  const res = await fetch(`/api/auth${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const data = (await res.json().catch(() => null)) as ApiError | null;
    throw new Error(data?.message ?? "Не удалось выполнить запрос");
  }
}

export function sendCode(phone: string) {
  return post("/phone/request", { phone });
}

export function verifyCode(phone: string, code: string) {
  return post("/phone/verify", { phone, code });
}
