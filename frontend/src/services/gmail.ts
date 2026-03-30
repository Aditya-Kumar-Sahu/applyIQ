import { apiRequest } from "./api";

export type GmailAuthUrlData = {
  auth_url: string;
};

export type GmailStatusData = {
  connected: boolean;
  gmail_account_hint: string | null;
  last_checked_at: string | null;
};

export type GmailPollData = {
  polled?: boolean;
  processed_messages: number;
  matched_notifications?: number;
};

export async function getGmailAuthUrl(): Promise<GmailAuthUrlData> {
  return apiRequest<GmailAuthUrlData>("/api/v1/gmail/auth-url");
}

export async function getGmailStatus(): Promise<GmailStatusData> {
  return apiRequest<GmailStatusData>("/api/v1/gmail/status");
}

export async function pollGmailNow(): Promise<GmailPollData> {
  return apiRequest<GmailPollData>("/api/v1/gmail/poll", {
    method: "POST",
  });
}
