export const API_BASE_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

type Envelope<T> = {
  success: boolean;
  data: T | null;
  error: {
    code: string;
    message: string;
  } | null;
};

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData;
  const response = await fetch(`${API_BASE_URL}${path}`, {
    credentials: "include",
    headers: {
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  const payload = (await response.json()) as Envelope<T>;

  if (!response.ok || !payload.success || payload.data === null) {
    throw new ApiError(payload.error?.message ?? "Request failed", response.status, payload.error?.code);
  }

  return payload.data;
}
