# Intent: Job Application Tracker

Confirmed: 2026-10-17

- **Outcome:** A job application tracker that replaces the spreadsheet. Each application keeps its full job description, applied date, status, links, notes, and a log of every conversation, so all of it is on one screen before an interview.
- **User:** Me, during an active search for backend and DevOps/platform roles (50+ applications so far). It's also a portfolio piece that shows backend and infrastructure skills.
- **Why now:** The spreadsheet can't hold job descriptions or contact history, so I keep re-checking status and who I talked to before interviews. Posting pages also disappear.
- **Follow-ups:** Each conversation is logged against an application (person, date, channel, note). Contacts are people at a company and can link to several applications there. A "needs follow-up" list shows open applications with no contact in N days, oldest first.
- **Resume improvement:** Export a markdown file of rejected and no-response applications with their full job descriptions, to paste into Claude by hand. The app never calls an LLM.
- **Data and infrastructure:** Everything stays on my computer, in Postgres running under Docker Compose.
- **Order of work:**
  - Stage 1: a usable local tracker (API, database, deliberately plain frontend).
  - Later stages, each showcasable on its own: CI/CD, then Kubernetes manifests or Helm, then Terraform for a cloud deployment.
- **Success:** I stop using the spreadsheet within about a week, and later stages give me real changes to talk about in interviews.
- **Out of scope for stage 1:** LLM calls inside the app, push or email notifications, logins or multiple users, a polished frontend, any cloud deployment.

## Changes since confirmation

- 2026-10-17: CSV import moved out of stage 1 to the backlog, because the spreadsheet data is stale. Status history added, so early and late rejections can be told apart.
