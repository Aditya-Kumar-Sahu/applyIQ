import * as Sentry from "@sentry/vue";
import { createApp } from "vue";

import App from "./App.vue";
import { router } from "./router";
import { store } from "./store";
import { AUTH_REQUIRED_EVENT } from "./services/api";
import "./styles.css";

const app = createApp(App);

window.addEventListener(AUTH_REQUIRED_EVENT, async () => {
  await store.dispatch("handleAuthRequired");
  if (router.currentRoute.value.name !== "login") {
    await router.replace({ name: "login" });
  }
});

const sentryDsn = import.meta.env.VITE_SENTRY_DSN;
if (sentryDsn) {
  Sentry.init({
    app,
    dsn: sentryDsn,
    environment: import.meta.env.MODE,
    release: import.meta.env.VITE_RELEASE_VERSION ?? "dev",
    tracesSampleRate: Number(import.meta.env.VITE_SENTRY_TRACES_SAMPLE_RATE ?? "0"),
  });
}

app.use(store).use(router).mount("#app");
