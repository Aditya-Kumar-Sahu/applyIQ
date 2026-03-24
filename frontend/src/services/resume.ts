import { apiRequest } from "./api";
import type { ParsedResumeProfile, ProfileCompleteness, SearchPreferences } from "../store";

type ResumeUploadResponse = {
  profile: ParsedResumeProfile;
  file_hash: string;
  embedding_dimensions: number;
};

type ResumeDetailResponse = {
  profile: ParsedResumeProfile;
  preferences: SearchPreferences | null;
};

type SearchPreferencesResponse = {
  preferences: SearchPreferences;
};

export async function uploadResume(file: File): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  return apiRequest<ResumeUploadResponse>("/api/v1/resume/upload", {
    method: "POST",
    body: formData,
  });
}

export async function getResume(): Promise<ResumeDetailResponse> {
  return apiRequest<ResumeDetailResponse>("/api/v1/resume");
}

export async function updatePreferences(payload: SearchPreferences): Promise<SearchPreferences> {
  const response = await apiRequest<SearchPreferencesResponse>("/api/v1/resume/preferences", {
    method: "PUT",
    body: JSON.stringify(payload),
  });
  return response.preferences;
}

export async function getProfileCompleteness(): Promise<ProfileCompleteness> {
  return apiRequest<ProfileCompleteness>("/api/v1/resume/profile-completeness");
}
