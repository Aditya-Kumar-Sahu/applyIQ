import { API_BASE_URL, ApiError, apiRequest } from "./api";

export type PipelineStartPayload = {
  target_role: string;
  location: string;
  limit_per_source: number;
  sources: string[];
};

export type PipelineRunSummary = {
  run_id: string;
  status: string;
  current_node: string;
  jobs_found: number;
  jobs_matched: number;
  applications_submitted: number;
  pending_approvals_count: number;
};

export type PipelineApplication = {
  id: string;
  job_id: string;
  title: string;
  company_name: string;
  match_score: number;
  cover_letter_text: string;
  cover_letter_version: number;
  status: string;
};

export type PipelineResults = {
  run_id: string;
  status: string;
  current_node: string;
  jobs_found: number;
  jobs_matched: number;
  applications_submitted: number;
  started_at: string;
  completed_at: string | null;
  applications: PipelineApplication[];
};

export type RejectResult = {
  rejected_count: number;
};

export type CoverLetterEditResult = {
  application_id: string;
  cover_letter_text: string;
  cover_letter_version: number;
};

export async function startPipeline(payload: PipelineStartPayload): Promise<PipelineRunSummary> {
  return apiRequest<PipelineRunSummary>("/api/v1/pipeline/start", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function getPipelineResults(runId: string): Promise<PipelineResults> {
  return apiRequest<PipelineResults>(`/api/v1/pipeline/${runId}/results`);
}

export async function getPipelineStatus(runId: string): Promise<PipelineResults> {
  const response = await fetch(`${API_BASE_URL}/api/v1/pipeline/${runId}/status`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new ApiError("Unable to stream pipeline status", response.status);
  }

  const payload = await response.text();
  const dataLine = payload
    .split("\n")
    .map((line) => line.trim())
    .find((line) => line.startsWith("data:"));

  if (!dataLine) {
    throw new ApiError("Pipeline status stream returned no data", response.status);
  }

  return JSON.parse(dataLine.slice(5).trim()) as PipelineResults;
}

export async function approvePipeline(runId: string, applicationIds: string[]): Promise<PipelineRunSummary> {
  return apiRequest<PipelineRunSummary>(`/api/v1/pipeline/${runId}/approve`, {
    method: "POST",
    body: JSON.stringify({ application_ids: applicationIds }),
  });
}

export async function rejectPipeline(runId: string, applicationIds: string[]): Promise<RejectResult> {
  return apiRequest<RejectResult>(`/api/v1/pipeline/${runId}/reject`, {
    method: "POST",
    body: JSON.stringify({ application_ids: applicationIds }),
  });
}

export async function editCoverLetter(
  runId: string,
  applicationId: string,
  coverLetterText: string,
): Promise<CoverLetterEditResult> {
  return apiRequest<CoverLetterEditResult>(`/api/v1/pipeline/${runId}/application/${applicationId}/cover-letter`, {
    method: "PUT",
    body: JSON.stringify({ cover_letter_text: coverLetterText }),
  });
}
