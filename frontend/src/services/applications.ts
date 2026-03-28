import { API_BASE_URL, ApiError, apiRequest } from "./api";

export type ApplicationListItem = {
  id: string;
  job_id: string;
  title: string;
  company_name: string;
  status: string;
  match_score: number;
  applied_at: string | null;
  latest_email_classification: string | null;
};

export type EmailMonitorData = {
  gmail_thread_id: string;
  sender: string;
  subject: string;
  snippet: string;
  latest_classification: string;
  last_checked_at: string;
  is_resolved: boolean;
};

export type ApplicationDetail = {
  id: string;
  job_id: string;
  title: string;
  company_name: string;
  status: string;
  match_score: number;
  cover_letter_text: string;
  ats_provider: string | null;
  confirmation_url: string | null;
  screenshot_urls: string[];
  email_monitor: EmailMonitorData | null;
};

export type ApplicationsListResponse = {
  items: ApplicationListItem[];
};

export type NotificationItem = {
  application_id: string;
  company_name: string;
  title: string;
  classification: string;
  snippet: string;
  created_at: string;
};

export type NotificationsResponse = {
  items: NotificationItem[];
};

export async function getApplications(): Promise<ApplicationsListResponse> {
  return apiRequest<ApplicationsListResponse>("/api/v1/applications");
}

export async function getApplicationDetail(applicationId: string): Promise<ApplicationDetail> {
  return apiRequest<ApplicationDetail>(`/api/v1/applications/${applicationId}`);
}

export async function getNotifications(): Promise<NotificationsResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/notifications`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new ApiError("Unable to load notifications", response.status);
  }

  const payload = await response.text();
  const dataLine = payload
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.startsWith("data:"));

  if (!dataLine) {
    throw new ApiError("Notifications stream returned no data", response.status);
  }

  return JSON.parse(dataLine.slice(5).trim()) as NotificationsResponse;
}
