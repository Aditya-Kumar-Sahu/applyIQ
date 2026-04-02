# Placeholder Audit Report

Scope: repository-wide scan of docs, frontend, backend, and pipeline/automation code for placeholder text, static demo content, abstract stubs, and features that are presented like live behavior but are not live by default.

## Prioritized Fix List

P0
- [x] Remove static landing-page metrics and fabricated workflow claims from [frontend/src/views/HomeView.vue](frontend/src/views/HomeView.vue).
- [x] Remove the fake clock timestamps from [frontend/src/views/PipelineView.vue](frontend/src/views/PipelineView.vue).

P1
- [x] Replace the `TBD` deliverables in [README.md](README.md), [PLAN.md](PLAN.md), and [Walkthrough.md](Walkthrough.md) with real assets or clearly marked pending work.
- [ ] Decide whether demo-first auto-apply should remain the default in [backend/app/core/config.py](backend/app/core/config.py) and [backend/app/services/auto_apply_service.py](backend/app/services/auto_apply_service.py), or be changed to require explicit opt-in.

P2
- [ ] Clean up ordinary sample placeholders in forms where they can confuse users, but these are lower priority than the runtime-facing bluff.

## Executive Summary

The codebase originally contained a small number of true product bluffs: static marketing/demo content in the landing page, planned deliverables left as `TBD` in the docs, and demo-first auto-apply behavior that returns simulated results unless browser automation is explicitly enabled. The home page and pipeline log bluff items have now been removed; the remaining open issues are mostly docs and backend defaults. There are also ordinary form placeholders and a few intentional abstraction points that are not defects by themselves.

## High-Confidence Product Bluffs

The items below are the remaining confirmed bluff-like issues.

- [README.md](README.md#L192) exposes a `Demo Placeholders` section with `TBD` entries for the live demo URL, product screenshots, and demo video. This is explicit unfinished deliverable text.
- [PLAN.md](PLAN.md#L44) repeats the placeholder pattern with `TBD` entries for the live demo URL, screenshots, and architecture export.
- [UI_plan.md](UI_plan.md#L115) describes `Router with 6 placeholder routes`, and later sections call out `placeholder data` and a future-proofing integration panel marked as a placeholder. This reads as design intent rather than shipped UI.
- [Walkthrough.md](Walkthrough.md#L48) contains a literal `Screenshot placeholder:` block, which means the walkthrough still depends on missing visual evidence.

## Addressed In This Pass

- [frontend/src/views/HomeView.vue](frontend/src/views/HomeView.vue) no longer shows fake metrics, fabricated companies, or live-workflow claims.
- [frontend/src/views/PipelineView.vue](frontend/src/views/PipelineView.vue) no longer renders fabricated clock timestamps in the execution log.

## Demo-First Behavior That Is Not Live By Default

- [backend/app/core/config.py](backend/app/core/config.py#L48) defaults `auto_apply_demo_mode` to `True` and `playwright_enabled` to `False`.
- [backend/app/services/auto_apply_service.py](backend/app/services/auto_apply_service.py#L82) checks those flags and, when demo mode remains enabled, returns a simulated `DEMO-...` success instead of a real submission. The service is intentionally safe, but out of the box it does not perform live auto-apply.
- [backend/app/scrapers/base.py](backend/app/scrapers/base.py#L22) leaves `BaseJobScraper.fetch_jobs` as `raise NotImplementedError`, so scraping only works if concrete implementations exist and are wired in elsewhere.

## Ordinary UI Placeholders

These are normal form hints rather than misleading product claims, but they still count as placeholders in the literal sense.

- [frontend/src/components/layout/AppShell.vue](frontend/src/components/layout/AppShell.vue#L9) uses `Search operations...` in the top-bar search box.
- [frontend/src/views/ApplicationsView.vue](frontend/src/views/ApplicationsView.vue#L111) uses `Search applications...`.
- [frontend/src/views/JobsView.vue](frontend/src/views/JobsView.vue#L12) uses `Search by natural language, skills, or role`.
- [frontend/src/views/LoginView.vue](frontend/src/views/LoginView.vue#L18) and [frontend/src/views/RegisterView.vue](frontend/src/views/RegisterView.vue#L31) use standard email/password hints.
- [frontend/src/views/RegisterView.vue](frontend/src/views/RegisterView.vue#L18) uses `Alex Chen` as the name example.
- [frontend/src/views/LoginView.vue](frontend/src/views/LoginView.vue#L31) uses a masked password example.
- [frontend/src/views/ResumeView.vue](frontend/src/views/ResumeView.vue#L52) and [frontend/src/views/ProfileView.vue](frontend/src/views/ProfileView.vue#L51) use sample role/location values like `ML Engineer, AI Engineer` and `Remote, Bengaluru`.
- [frontend/src/views/ResumeView.vue](frontend/src/views/ResumeView.vue#L87) and [frontend/src/views/ProfileView.vue](frontend/src/views/ProfileView.vue#L71) use `Example Corp` as an excluded-company sample value.
- [frontend/src/views/ResumeView.vue](frontend/src/views/ResumeView.vue#L92) and [frontend/src/views/ProfileView.vue](frontend/src/views/ProfileView.vue#L72) use `senior` as a sample seniority value.

## Intentional Scaffolding That Looks Like a Placeholder But Is Not a Defect

- [backend/app/models/base.py](backend/app/models/base.py#L7) is a standard SQLAlchemy base scaffold.
- [backend/app/agents/auto_apply/ats/base.py](backend/app/agents/auto_apply/ats/base.py#L19) uses protocol signatures with ellipses as type-only interface declarations.
- [backend/app/services/gemini_client.py](backend/app/services/gemini_client.py#L21) uses `pass` for the exception class and normal error-handling flow; that is not a missing implementation.

## Bottom Line

The main misleading parts are the static landing page, the docs that still advertise unfinished assets as `TBD`, and the auto-apply path that is demo-first by default. The rest of the visible placeholders are mostly standard form hints or abstract interfaces.