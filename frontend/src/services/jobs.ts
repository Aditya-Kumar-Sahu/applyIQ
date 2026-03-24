import { apiRequest } from "./api";

export type ScoreBreakdown = {
  semantic_similarity: number;
  skills_coverage: number;
  seniority_alignment: number;
  location_match: number;
  salary_alignment: number;
};

export type RankedJob = {
  job_id: string;
  title: string;
  company_name: string;
  source: string;
  location: string;
  is_remote: boolean;
  salary_min: number | null;
  salary_max: number | null;
  apply_url: string;
  match_score: number;
  score_breakdown: ScoreBreakdown;
  matched_skills: string[];
  missing_skills: string[];
  recommendation: string;
  one_line_reason: string;
};

export type JobDetail = RankedJob & {
  company_domain: string | null;
  description_text: string;
  posted_at: string | null;
};

type JobsListResponse = {
  total: number;
  items: RankedJob[];
};

export async function getJobs(): Promise<JobsListResponse> {
  return apiRequest<JobsListResponse>("/api/v1/jobs");
}

export async function searchJobs(query: string): Promise<JobsListResponse> {
  const params = new URLSearchParams({ q: query });
  return apiRequest<JobsListResponse>(`/api/v1/jobs/semantic-search?${params.toString()}`);
}

export async function getJobDetail(jobId: string): Promise<JobDetail> {
  return apiRequest<JobDetail>(`/api/v1/jobs/${jobId}`);
}
