---
name: scf-delivery-workflow
description: Plan or implement SCF's later-stage V2 project-delivery management layer on top of the existing OA/auth/workflow system. Use when working on ProjectTrack, SubProject, Milestone, Risk Board, 2+1 or 1+1+1 delivery structures, optional business-course branches, milestone templates, or deadline/risk visibility, especially when deciding how that layer should coexist with the current V2 streams for SMS reminders, sales-frontend handoff, and Tencent Meeting feedback drafts.
---

# SCF Delivery Workflow

## Read First

1. Read `docs/handoff/current-focus.md`.
2. Read `docs/versions/V2.md`.
3. Read `docs/architecture/current-system.md`.
4. If the task touches `oa`, `auth`, workflow boundaries, or delivery-chain defaults, use `scf-platform-context` alongside this skill.

## Position In Current Roadmap

- Treat this skill as the later V2 product-layer skill, not the default first skill for every V2 task.
- The current V2 active streams are still `SMS` reminders, sales-front-end handoff, and Tencent Meeting feedback drafts.
- Use this skill when the task explicitly enters delivery objects, milestone templates, or risk-board design, or when you need to decide whether those objects are required for a proposed V2 change.

## Default Workflow

1. Confirm the current object-model gap between shipped V1 objects and proposed V2 objects.
2. Confirm whether the task truly needs the delivery-model layer now, or whether it should stay inside the current `SMS` / sales / Tencent Meeting streams without new delivery objects.
3. Confirm which default project type applies:
   - Technical only
   - Technical + business
   - Technical + business + competition
4. Confirm the milestone template and risk-board view before discussing APIs or UI.
5. Confirm which V2 decisions are still open and must not be treated as fixed.
6. Only then move into interface, page, or implementation design.

## Default Model

- Treat `Enrollment` as the confirmed-service entry point, not the full project-delivery object.
- Treat `ProjectTrack` as the long-running service line under one enrollment.
- Treat `SubProject` as one project unit inside a long service, including `2+1` and `1+1+1`.
- Treat `Milestone` as the deadline-bearing node for delivery readiness.
- Treat `OATodo` as the execution-task layer, not the project model itself.

## Default Delivery Principles

- Prefer risk alerts before hard blocking.
- Keep future `3 / 5 / 7 day` milestone visibility as a first-class requirement.
- Preserve the Flask monolith and database as the source of truth.
- Integrate with `auth`, `oa`, scheduling, feedback, reminder/event plumbing, and handbook outputs instead of bypassing them.
- Do not make the delivery-model layer a prerequisite for shipping first versions of `SMS` reminders, sales handoff, or Tencent Meeting feedback drafts when existing boundaries are sufficient.

## Default Project Types

- Technical only
- Technical + business
- Technical + business + competition

Each type should add milestone templates rather than fork the whole system.

## Open-Decision Guardrail

- `V2` contains default directions, not a fully locked implementation spec.
- Do not treat these as already decided unless the current docs explicitly lock them:
  - final data model shape
  - API and page entrypoints
  - milestone template generation mode
  - default Risk Board aggregation
  - `CourseSchedule` / `OATodo` integration depth
  - whether a specific `SMS`, sales, or Tencent Meeting flow truly requires `ProjectTrack` before first release

## Design Guardrails

- Do not overload `Enrollment` with milestone state.
- Do not reduce project delivery to generic todos only.
- Do not assume every project has a business branch.
- Do not build the boss/admin view around calendars only; include risk-board views.
- Do not force reminder, sales, or feedback-draft work into `ProjectTrack` prematurely if it can ship safely on current objects and workflow boundaries.
