import { apiRequest } from "./api";
import type { AuthUser } from "../store";

type AuthSessionResponse = {
  user: AuthUser;
  access_token: string;
  refresh_token: string;
  token_type: string;
};

type MeResponse = {
  user: AuthUser;
};

export async function register(payload: {
  email: string;
  password: string;
  full_name: string;
}): Promise<AuthUser> {
  const response = await apiRequest<AuthSessionResponse>("/api/v1/auth/register", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  return response.user;
}

export async function login(payload: { email: string; password: string }): Promise<AuthUser> {
  const response = await apiRequest<AuthSessionResponse>("/api/v1/auth/login", {
    method: "POST",
    body: JSON.stringify(payload),
  });

  return response.user;
}

export async function me(): Promise<AuthUser> {
  const response = await apiRequest<MeResponse>("/api/v1/auth/me");
  return response.user;
}

export async function logout(): Promise<void> {
  await apiRequest<{ logged_out: boolean }>("/api/v1/auth/logout", {
    method: "POST",
  });
}
