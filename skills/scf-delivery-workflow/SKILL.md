---
name: scf-delivery-workflow
description: Plan or implement SCF's project-delivery management layer on top of the existing OA/auth/workflow system. Use when working on ProjectTrack, SubProject, Milestone, Risk Board, 2+1 or 1+1+1 delivery structures, optional business-course branches, milestone templates, or deadline/risk visibility tied to SCF's current OA and enrollment flows.
---

# SCF Delivery Workflow

## Read First

1. Read `docs/versions/V2.md`.
2. Read `docs/architecture/current-system.md`.
3. Read `docs/handoff/current-focus.md`.
4. If the task touches `oa`, `auth`, workflow boundaries, or delivery-chain defaults, use `scf-platform-context` alongside this skill.

## Default Workflow

1. Confirm the current object-model gap between shipped V1 objects and proposed V2 objects.
2. Confirm which default project type applies:
   - Technical only
   - Technical + business
   - Technical + business + competition
3. Confirm the milestone template and risk-board view before discussing APIs or UI.
4. Confirm which V2 decisions are still open and must not be treated as fixed.
5. Only then move into interface, page, or implementation design.

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
- Integrate with `auth`, `oa`, scheduling, feedback, and handbook outputs instead of bypassing them.

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

## Design Guardrails

- Do not overload `Enrollment` with milestone state.
- Do not reduce project delivery to generic todos only.
- Do not assume every project has a business branch.
- Do not build the boss/admin view around calendars only; include risk-board views.
