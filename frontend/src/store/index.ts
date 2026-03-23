import { createStore } from "vuex";

export type DashboardStat = {
  label: string;
  value: string;
};

export type RootState = {
  headline: string;
  stats: DashboardStat[];
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
  },
  getters: {
    dashboardStats: (state: RootState) => state.stats,
    headline: (state: RootState) => state.headline,
  },
  mutations: {
    setStats(state: RootState, stats: DashboardStat[]) {
      state.stats = stats;
    },
  },
});
