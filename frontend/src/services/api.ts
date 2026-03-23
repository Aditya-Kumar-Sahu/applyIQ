const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type Envelope<T> = {
  success: boolean;
  data: T | null;
  error: {
    code: string;
    message: string;
  } | null;
};

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const payload = (await response.json()) as Envelope<T>;

  if (!response.ok || !payload.success || payload.data === null) {
    throw new Error(payload.error?.message ?? "Request failed");
  }

  return payload.data;
}
