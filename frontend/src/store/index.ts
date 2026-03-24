import { createStore } from "vuex";

import { ApiError } from "../services/api";
import type { JobDetail, RankedJob } from "../services/jobs";

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
};

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
  },
});
