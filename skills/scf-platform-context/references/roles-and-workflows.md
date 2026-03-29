# Roles And Workflows

## Roles

- Admin and operations staff own intake, scheduling coordination, user management, and delivery oversight.
- Teachers own availability, teaching execution, student communication, and feedback entry.
- Students own availability submission, schedule confirmation or rejection, class attendance, and receiving feedback.
- Planned V2 sales-facing surfaces should record communication, intent, risk, and next action, then hand off into student-profile draft and `Enrollment` through the website business layer. Treat that as planned unless code and tests prove it exists.

## Workflow Principle

- Keep the scheduling and feedback loop visible from intake through delivery completion.
- Do not let student objections or scheduling changes disappear into isolated chat threads without returning to an auditable workflow.
- Do not let sales communication remain outside the system once it needs to drive profile drafts, intake decisions, or `Enrollment` handoff.
- Treat AI-generated meeting summaries and feedback drafts as assistive content. Teacher review remains required before formal feedback submission.
- Keep role boundaries clear so action ownership remains explicit across admin, teacher, and student surfaces.
