import { createStore } from "vuex";

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

export type RootState = {
  headline: string;
  stats: DashboardStat[];
  authUser: AuthUser | null;
  authStatus: "idle" | "loading" | "authenticated" | "guest";
  authError: string | null;
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
  },
  getters: {
    dashboardStats: (state: RootState) => state.stats,
    headline: (state: RootState) => state.headline,
    authUser: (state: RootState) => state.authUser,
    authStatus: (state: RootState) => state.authStatus,
    authError: (state: RootState) => state.authError,
    isAuthenticated: (state: RootState) => state.authStatus === "authenticated" && state.authUser !== null,
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
  },
});
