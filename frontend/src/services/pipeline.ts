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
  semantic_similarity?: number;
  skills_coverage?: number;
  seniority_alignment?: number;
  location_match?: number;
  salary_alignment?: number;
  id: string;
  job_id: string;
  title: string;
  company_name: string;
  match_score: number;
  cover_letter_text: string;
  tone: string;
  word_count: number;
  cover_letter_version: number;
  status: string;
  ats_provider: string | null;
  confirmation_url: string | null;
  confirmation_number: string | null;
  screenshot_urls: string[];
  failure_reason: string | null;
  manual_required_reason: string | null;
  selected_variant_id: string | null;
  is_demo?: boolean;
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
  tone: string;
  word_count: number;
  cover_letter_version: number;
};

export type CoverLetterVariant = {
  variant_id: string;
  cover_letter_text: string;
  tone: string;
  word_count: number;
};

export type CoverLetterABTestResult = {
  application_id: string;
  cover_letter_version: number;
  variants: CoverLetterVariant[];
};

export type CoverLetterVariantSelectResult = {
  application_id: string;
  selected_variant_id: string;
  cover_letter_text: string;
  tone: string;
  word_count: number;
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

export function subscribePipelineStatus(
  runId: string,
  onStatus: (pipelineResults: PipelineResults) => void,
  onError?: (error: Error) => void,
): () => void {
  const source = new EventSource(`${API_BASE_URL}/api/v1/pipeline/${runId}/status/stream`, {
    withCredentials: true,
  });
  let closed = false;

  const handleStatus = (event: MessageEvent<string>) => {
    const pipelineResults = JSON.parse(event.data) as PipelineResults;
    onStatus(pipelineResults);

    if (pipelineResults.status === "complete" || pipelineResults.status === "failed" || pipelineResults.status === "timed_out") {
      closed = true;
      source.close();
    }
  };

  source.addEventListener("status", handleStatus as EventListener);
  source.onerror = () => {
    if (closed) {
      return;
    }
    if (source.readyState === EventSource.CLOSED) {
      onError?.(new ApiError("Pipeline status stream disconnected", 503));
    }
  };

  return () => {
    closed = true;
    source.close();
  };
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

export async function regenerateCoverLetter(runId: string, applicationId: string): Promise<CoverLetterEditResult> {
  return apiRequest<CoverLetterEditResult>(`/api/v1/pipeline/${runId}/application/${applicationId}/cover-letter/regenerate`, {
    method: "POST",
  });
}

export async function generateCoverLetterABTest(runId: string, applicationId: string): Promise<CoverLetterABTestResult> {
  return apiRequest<CoverLetterABTestResult>(
    `/api/v1/pipeline/${runId}/application/${applicationId}/cover-letter/ab-test`,
    {
      method: "POST",
    },
  );
}

export async function selectCoverLetterVariant(
  runId: string,
  applicationId: string,
  variantId: string,
): Promise<CoverLetterVariantSelectResult> {
  return apiRequest<CoverLetterVariantSelectResult>(
    `/api/v1/pipeline/${runId}/application/${applicationId}/cover-letter/select-variant`,
    {
      method: "POST",
      body: JSON.stringify({ variant_id: variantId }),
    },
  );
}

export function isDemoApplication(application: PipelineApplication): boolean {
  if (application.is_demo === true) {
    return true;
  }
  return (application.confirmation_number ?? "").startsWith("DEMO-");
}
