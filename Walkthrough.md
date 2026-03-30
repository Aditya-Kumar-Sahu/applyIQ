# ApplyIQ Walkthrough

ApplyIQ is built around a real backend workflow: upload a resume, set search preferences, start a pipeline run, review the ranked applications at an approval gate, and then let the backend advance the approved items through auto-apply and tracking.

This walkthrough reflects the current implementation, not the aspirational roadmap.

## 1. Sign Up and Log In

Create an account through the auth flow and land on the dashboard. The app uses JWT cookies for session state, and protected routes require a valid logged-in user.

## 2. Upload Your Resume

Go to the resume upload view and submit a PDF or DOCX file.

The backend extracts text, parses the resume into a structured profile, stores the parsed profile, and keeps the resume text encrypted at rest.

What you should see:

- A successful upload confirmation
- A parsed resume profile with name, role, skills, and summary data

## 3. Set Search Preferences

Open the preferences form and choose:

- Target roles
- Preferred locations
- Remote preference
- Salary range
- Seniority level

These preferences drive the pipeline run and influence ranking and filtering.

## 4. Start a Pipeline Run

Trigger a pipeline run from the pipeline page.

The backend:

1. Scrapes jobs from the configured sources
2. Deduplicates the result set
3. Ranks jobs against the resume profile
4. Generates cover letters for the approval queue
5. Pauses at the approval gate before auto-apply

The pipeline state is checkpointed in Redis so the run can be resumed after approval.

Screenshot placeholder:

![Pipeline graph](docs/screenshots/pipeline.png)

## 5. Review the Approval Gate

At the approval gate, you can review each matched job and its generated cover letter.

Current behavior:

- The approval experience is functional
- You can approve or reject individual applications
- You can regenerate or edit a cover letter before approval
- The tracker shows a ranked list, not a kanban board

The gate is the most important interaction in the app because it gives the user control before anything is submitted.

## 6. Auto-Apply

After approval, the pipeline continues into auto-apply.

Current behavior:

- Demo mode is explicit and safe
- If browser automation is not enabled, the app returns a simulated confirmation number prefixed with `DEMO-`
- If browser mode is enabled later, that is the place where real Playwright-based form submission would run

This keeps the current build honest while preserving the shape of the final workflow.

## 7. Track Applications

Open the applications view to monitor submitted jobs.

You can:

- Browse submitted applications
- Inspect status changes
- Review cover letter and job details
- Watch live SSE updates when the backend publishes changes

The tracker is currently list-based and functional, not a drag-and-drop kanban board.

## 8. Response Tracking

The app includes a response-tracking path that classifies email updates and pushes notifications into the frontend.

Current behavior:

- The monitor is present
- Notifications appear in the UI
- The live Gmail OAuth and polling flow is still a future enhancement

## 9. Notes on Current Scope

The current codebase is strongest in orchestration, encryption, and pipeline control.

What is already real:

- FastAPI backend
- LangGraph pipeline with pause and resume
- Redis-backed state persistence
- Encrypted resume and credential storage
- Parallel scraping and deduplication
- SSE updates
- Functional application tracking

What is still intentionally limited:

- Auto-apply is demo-first unless browser mode is configured
- Gmail integration is not yet a live OAuth polling flow
- The tracker is not a kanban board
- The current AI provider wiring in the repo is Gemini, not OpenAI

