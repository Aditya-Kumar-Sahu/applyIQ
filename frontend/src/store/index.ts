import { createStore } from "vuex";

import { ApiError } from "../services/api";
import type { JobDetail, RankedJob } from "../services/jobs";
import type {
  PipelineResults,
  PipelineRunSummary,
  PipelineStartPayload,
} from "../services/pipeline";

export type DashboardStat = {
  label: string;
  value: string;
};

export type AuthUser = {
  id: string;
  email: string;
  full_name: string;
  is_active: boolean;
  subscription_tier: string;
};

export type SkillGroups = {
  technical: string[];
  soft: string[];
  tools: string[];
  languages: string[];
};

export type ExperienceEntry = {
  company: string;
  title: string;
  duration_months: number;
  highlights: string[];
};

export type EducationEntry = {
  degree: string;
  field: string;
  institution: string;
  year: number | null;
};

export type SalaryRange = {
  min: number;
  max: number;
  currency: string;
};

export type ParsedResumeProfile = {
  name: string;
  email: string;
  current_title: string;
  years_of_experience: number;
  seniority_level: string;
  skills: SkillGroups;
  experience: ExperienceEntry[];
  education: EducationEntry[];
  preferred_roles: string[];
  inferred_salary_range: SalaryRange;
  work_style_signals: string[];
  summary_for_matching: string;
};

export type SearchPreferences = {
  target_roles: string[];
  preferred_locations: string[];
  remote_preference: string;
  salary_min: number | null;
  salary_max: number | null;
  currency: string;
  excluded_companies: string[];
  seniority_level: string | null;
  is_active: boolean;
};

export type ProfileCompleteness = {
  score: number;
  missing_fields: string[];
  recommendations: string[];
};

export type RootState = {
  headline: string;
  stats: DashboardStat[];
  authUser: AuthUser | null;
  authStatus: "idle" | "loading" | "authenticated" | "guest";
  authError: string | null;
  resumeProfile: ParsedResumeProfile | null;
  resumePreferences: SearchPreferences | null;
  profileCompleteness: ProfileCompleteness | null;
  resumeStatus: "idle" | "loading" | "ready";
  resumeError: string | null;
  jobs: RankedJob[];
  selectedJob: JobDetail | null;
  jobsStatus: "idle" | "loading" | "ready";
  jobsError: string | null;
  pipelineRun: PipelineRunSummary | null;
  pipelineResults: PipelineResults | null;
  pipelineStatus: "idle" | "loading" | "ready";
  pipelineError: string | null;
};

function buildStats(state: RootState): DashboardStat[] {
  const pendingApprovalCount =
    state.pipelineResults?.applications.filter((application) => application.status === "pending_approval").length ?? 0;
  const appliedCount =
    state.pipelineResults?.applications.filter((application) => application.status === "approved").length ?? 0;

  return [
    { label: "Jobs Found", value: String(state.pipelineRun?.jobs_found ?? state.pipelineResults?.jobs_found ?? 0) },
    { label: "Pending Approval", value: String(pendingApprovalCount) },
    { label: "Applied", value: String(appliedCount) },
    { label: "Replies", value: "0" },
  ];
}

export const store = createStore<RootState>({
  state: {
    headline: "Phase 1 frontend foundation now runs on Vue and Vuex.",
    stats: [
      { label: "Jobs Found", value: "0" },
      { label: "Pending Approval", value: "0" },
      { label: "Applied", value: "0" },
      { label: "Replies", value: "0" },
    ],
    authUser: null,
    authStatus: "idle",
    authError: null,
    resumeProfile: null,
    resumePreferences: null,
    profileCompleteness: null,
    resumeStatus: "idle",
    resumeError: null,
    jobs: [],
    selectedJob: null,
    jobsStatus: "idle",
    jobsError: null,
    pipelineRun: null,
    pipelineResults: null,
    pipelineStatus: "idle",
    pipelineError: null,
  },
  getters: {
    dashboardStats: (state: RootState) => state.stats,
    headline: (state: RootState) => state.headline,
    authUser: (state: RootState) => state.authUser,
    authStatus: (state: RootState) => state.authStatus,
    authError: (state: RootState) => state.authError,
    isAuthenticated: (state: RootState) => state.authStatus === "authenticated" && state.authUser !== null,
    resumeProfile: (state: RootState) => state.resumeProfile,
    resumePreferences: (state: RootState) => state.resumePreferences,
    profileCompleteness: (state: RootState) => state.profileCompleteness,
    resumeStatus: (state: RootState) => state.resumeStatus,
    resumeError: (state: RootState) => state.resumeError,
    jobs: (state: RootState) => state.jobs,
    selectedJob: (state: RootState) => state.selectedJob,
    jobsStatus: (state: RootState) => state.jobsStatus,
    jobsError: (state: RootState) => state.jobsError,
    pipelineRun: (state: RootState) => state.pipelineRun,
    pipelineResults: (state: RootState) => state.pipelineResults,
    pipelineStatus: (state: RootState) => state.pipelineStatus,
    pipelineError: (state: RootState) => state.pipelineError,
  },
  mutations: {
    setStats(state: RootState, stats: DashboardStat[]) {
      state.stats = stats;
    },
    setAuthLoading(state: RootState) {
      state.authStatus = "loading";
      state.authError = null;
    },
    setAuthUser(state: RootState, user: AuthUser) {
      state.authUser = user;
      state.authStatus = "authenticated";
      state.authError = null;
    },
    setGuest(state: RootState) {
      state.authUser = null;
      state.authStatus = "guest";
    },
    setAuthError(state: RootState, message: string) {
      state.authError = message;
      state.authStatus = "guest";
    },
    setResumeLoading(state: RootState) {
      state.resumeStatus = "loading";
      state.resumeError = null;
    },
    setResumeData(
      state: RootState,
      payload: {
        profile: ParsedResumeProfile | null;
        preferences: SearchPreferences | null;
        completeness: ProfileCompleteness | null;
      },
    ) {
      state.resumeProfile = payload.profile;
      state.resumePreferences = payload.preferences;
      state.profileCompleteness = payload.completeness;
      state.resumeStatus = "ready";
      state.resumeError = null;
    },
    setResumeError(state: RootState, message: string) {
      state.resumeError = message;
      state.resumeStatus = "ready";
    },
    setJobsLoading(state: RootState) {
      state.jobsStatus = "loading";
      state.jobsError = null;
    },
    setJobs(state: RootState, jobs: RankedJob[]) {
      state.jobs = jobs;
      state.jobsStatus = "ready";
      state.jobsError = null;
    },
    setSelectedJob(state: RootState, job: JobDetail | null) {
      state.selectedJob = job;
    },
    setJobsError(state: RootState, message: string) {
      state.jobsError = message;
      state.jobsStatus = "ready";
    },
    setPipelineLoading(state: RootState) {
      state.pipelineStatus = "loading";
      state.pipelineError = null;
    },
    setPipelineRun(state: RootState, pipelineRun: PipelineRunSummary | null) {
      state.pipelineRun = pipelineRun;
      state.pipelineStatus = "ready";
      state.pipelineError = null;
      state.stats = buildStats(state);
    },
    setPipelineResults(state: RootState, pipelineResults: PipelineResults | null) {
      state.pipelineResults = pipelineResults;
      state.pipelineStatus = "ready";
      state.pipelineError = null;
      state.stats = buildStats(state);
    },
    setPipelineError(state: RootState, message: string) {
      state.pipelineError = message;
      state.pipelineStatus = "ready";
    },
  },
  actions: {
    async hydrateSession({ commit }) {
      commit("setAuthLoading");

      try {
        const { me } = await import("../services/auth");
        const user = await me();
        commit("setAuthUser", user);
      } catch {
        commit("setGuest");
      }
    },
    async login({ commit }, payload: { email: string; password: string }) {
      commit("setAuthLoading");

      try {
        const { login } = await import("../services/auth");
        const user = await login(payload);
        commit("setAuthUser", user);
      } catch (error) {
        commit("setAuthError", error instanceof Error ? error.message : "Unable to sign in");
        throw error;
      }
    },
    async register({ commit }, payload: { email: string; password: string; full_name: string }) {
      commit("setAuthLoading");

      try {
        const { register } = await import("../services/auth");
        const user = await register(payload);
        commit("setAuthUser", user);
      } catch (error) {
        commit("setAuthError", error instanceof Error ? error.message : "Unable to register");
        throw error;
      }
    },
    async fetchResume({ commit }) {
      commit("setResumeLoading");

      try {
        const [{ getResume, getProfileCompleteness }] = await Promise.all([import("../services/resume")]);
        const [resume, completeness] = await Promise.all([getResume(), getProfileCompleteness()]);
        commit("setResumeData", {
          profile: resume.profile,
          preferences: resume.preferences,
          completeness,
        });
      } catch (error) {
        if (error instanceof ApiError && error.status === 404) {
          commit("setResumeData", { profile: null, preferences: null, completeness: null });
          return;
        }
        commit("setResumeError", error instanceof Error ? error.message : "Unable to load resume");
      }
    },
    async uploadResume({ commit }, file: File) {
      commit("setResumeLoading");

      try {
        const { uploadResume, getResume, getProfileCompleteness } = await import("../services/resume");
        await uploadResume(file);
        const [resume, completeness] = await Promise.all([getResume(), getProfileCompleteness()]);
        commit("setResumeData", {
          profile: resume.profile,
          preferences: resume.preferences,
          completeness,
        });
      } catch (error) {
        commit("setResumeError", error instanceof Error ? error.message : "Unable to upload resume");
        throw error;
      }
    },
    async savePreferences({ commit, state }, payload: SearchPreferences) {
      commit("setResumeLoading");

      try {
        const { updatePreferences, getProfileCompleteness } = await import("../services/resume");
        const preferences = await updatePreferences(payload);
        const completeness = state.resumeProfile ? await getProfileCompleteness() : null;
        commit("setResumeData", {
          profile: state.resumeProfile,
          preferences,
          completeness,
        });
      } catch (error) {
        commit("setResumeError", error instanceof Error ? error.message : "Unable to save preferences");
        throw error;
      }
    },
    async fetchJobs({ commit }) {
      commit("setJobsLoading");

      try {
        const { getJobs, getJobDetail } = await import("../services/jobs");
        const jobsResponse = await getJobs();
        commit("setJobs", jobsResponse.items);
        if (jobsResponse.items.length > 0) {
          const detail = await getJobDetail(jobsResponse.items[0].job_id);
          commit("setSelectedJob", detail);
        } else {
          commit("setSelectedJob", null);
        }
      } catch (error) {
        commit("setJobsError", error instanceof Error ? error.message : "Unable to load jobs");
      }
    },
    async searchJobs({ commit }, query: string) {
      commit("setJobsLoading");

      try {
        const { searchJobs, getJobDetail } = await import("../services/jobs");
        const jobsResponse = await searchJobs(query);
        commit("setJobs", jobsResponse.items);
        if (jobsResponse.items.length > 0) {
          const detail = await getJobDetail(jobsResponse.items[0].job_id);
          commit("setSelectedJob", detail);
        } else {
          commit("setSelectedJob", null);
        }
      } catch (error) {
        commit("setJobsError", error instanceof Error ? error.message : "Unable to search jobs");
      }
    },
    async fetchJobDetail({ commit }, jobId: string) {
      try {
        const { getJobDetail } = await import("../services/jobs");
        const detail = await getJobDetail(jobId);
        commit("setSelectedJob", detail);
      } catch (error) {
        commit("setJobsError", error instanceof Error ? error.message : "Unable to load job detail");
      }
    },
    async startPipeline({ commit, dispatch }, payload: PipelineStartPayload) {
      commit("setPipelineLoading");

      try {
        const { startPipeline } = await import("../services/pipeline");
        const pipelineRun = await startPipeline(payload);
        commit("setPipelineRun", pipelineRun);
        await dispatch("loadPipeline", pipelineRun.run_id);
      } catch (error) {
        commit("setPipelineError", error instanceof Error ? error.message : "Unable to start pipeline");
        throw error;
      }
    },
    async loadPipeline({ commit, state }, runId?: string) {
      const resolvedRunId = runId ?? state.pipelineRun?.run_id;
      if (!resolvedRunId) {
        return;
      }

      commit("setPipelineLoading");

      try {
        const { getPipelineResults, getPipelineStatus } = await import("../services/pipeline");
        const [pipelineResults, pipelineStatus] = await Promise.all([
          getPipelineResults(resolvedRunId),
          getPipelineStatus(resolvedRunId),
        ]);

        commit("setPipelineRun", {
          run_id: pipelineResults.run_id,
          status: pipelineResults.status,
          current_node: pipelineStatus.current_node,
          jobs_found: pipelineResults.jobs_found,
          jobs_matched: pipelineResults.jobs_matched,
          applications_submitted: pipelineResults.applications_submitted,
          pending_approvals_count: pipelineResults.applications.filter(
            (application) => application.status === "pending_approval",
          ).length,
        });
        commit("setPipelineResults", pipelineResults);
      } catch (error) {
        commit("setPipelineError", error instanceof Error ? error.message : "Unable to load pipeline");
      }
    },
    async editPipelineCoverLetter(
      { dispatch, state },
      payload: { runId?: string; applicationId: string; coverLetterText: string },
    ) {
      const resolvedRunId = payload.runId ?? state.pipelineRun?.run_id;
      if (!resolvedRunId) {
        throw new Error("No pipeline run available");
      }

      const { editCoverLetter } = await import("../services/pipeline");
      await editCoverLetter(resolvedRunId, payload.applicationId, payload.coverLetterText);
      await dispatch("loadPipeline", resolvedRunId);
    },
    async regeneratePipelineCoverLetter(
      { dispatch, state },
      payload: { runId?: string; applicationId: string },
    ) {
      const resolvedRunId = payload.runId ?? state.pipelineRun?.run_id;
      if (!resolvedRunId) {
        throw new Error("No pipeline run available");
      }

      const { regenerateCoverLetter } = await import("../services/pipeline");
      await regenerateCoverLetter(resolvedRunId, payload.applicationId);
      await dispatch("loadPipeline", resolvedRunId);
    },
    async rejectPipelineApplications(
      { dispatch, state },
      payload: { runId?: string; applicationIds: string[] },
    ) {
      const resolvedRunId = payload.runId ?? state.pipelineRun?.run_id;
      if (!resolvedRunId) {
        throw new Error("No pipeline run available");
      }

      const { rejectPipeline } = await import("../services/pipeline");
      await rejectPipeline(resolvedRunId, payload.applicationIds);
      await dispatch("loadPipeline", resolvedRunId);
    },
    async approvePipelineApplications(
      { commit, dispatch, state },
      payload: { runId?: string; applicationIds: string[] },
    ) {
      const resolvedRunId = payload.runId ?? state.pipelineRun?.run_id;
      if (!resolvedRunId) {
        throw new Error("No pipeline run available");
      }

      commit("setPipelineLoading");

      try {
        const { approvePipeline } = await import("../services/pipeline");
        const pipelineRun = await approvePipeline(resolvedRunId, payload.applicationIds);
        commit("setPipelineRun", pipelineRun);
        await dispatch("loadPipeline", resolvedRunId);
      } catch (error) {
        commit("setPipelineError", error instanceof Error ? error.message : "Unable to resume pipeline");
        throw error;
      }
    },
  },
});
