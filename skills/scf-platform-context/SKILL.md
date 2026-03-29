---
name: scf-platform-context
description: Business, product, and integration architecture context for SCF's internal delivery platform serving international-school students through intake, scheduling, teaching, feedback, and workflow coordination. Use when working on SCF OA, auth, enrollment, workflow boundaries, reminder architecture, SMS reminder integration, sales-frontend-to-enrollment handoff, Tencent Meeting feedback-draft integration, Mini Program or WeChat planning, Feishu or OpenClaw channel design, handbook or agent extension decisions, multi-channel consistency, system boundary decisions, or internal-first productization choices.
---

# SCF Platform Context

## Overview

Use this skill to ground product and technical decisions in SCF's actual operating model instead of treating the repo like a generic school system or generic SaaS CRM.
Prioritize internal delivery efficiency first, keep the website as the mother port, then preserve only the abstractions that help future external commercialization.

## Core Product Frame

- Treat SCF as a small internal delivery team at the current stage, roughly 6 people. Use that as stage context, not as a permanent product constraint.
- Treat the core service as: understand a student's background, design a customized project, teach and deliver that project, then coordinate scheduling, execution, and feedback around it.
- Treat the main software user today as the internal SCF team. Optimize first for staff efficiency, operational clarity, and delivery quality.
- Treat international-school high school students applying overseas as the external service population, not as the current software buyer.
- Treat `auth + enrollment + workflow + oa + feedback + chat` as the current product center.
- Treat the current V2 active streams as:
  - `SMS` reminders for student-side proactive reach
  - sales-front-end handoff into student-profile draft and `Enrollment`
  - Tencent Meeting material flowing into feedback drafts
- Treat `OpenClaw + Feishu` as valid planned extensions, but not the only current V2 first move.
- Treat project-delivery management (`ProjectTrack / SubProject / Milestone / Risk Board`) as a later V2 product layer unless the task explicitly enters that scope.

## Architecture Defaults

- Treat the website database and workflow services as the single source of truth for operational data and state transitions.
- Keep the current Flask monolith as the default application boundary unless the user explicitly asks for service decomposition.
- Route `SMS`, Tencent Meeting, Mini Program, WeChat, Feishu, OpenClaw, and other external channels through the website business layer or workflow-safe APIs instead of direct table writes or bypassed workflow steps.
- Treat the sales frontend as a pre-`Enrollment` surface inside the same business system, not as a separate CRM truth owner.
- Treat Tencent Meeting recordings, transcripts, and notes as classroom evidence that may produce feedback drafts, not as official feedback state.
- Treat Feishu documents and similar collaboration surfaces as mirrored output or structured action entrypoints, not as editable truth for official business state.
- Treat notifications such as Feishu app pushes or `SMS` as event consumers, not owners of workflow state.
- Prefer one-way mirrors, callback actions, or task submission over free-form bidirectional sync with external systems.

## Decision Rules

- Prioritize internal usability over building a polished multi-tenant SaaS shell too early.
- Prioritize the current V2 active streams before secondary channel expansion unless the user explicitly asks to design the later path first.
- Prioritize scheduling, feedback, permissions, communication, reminder routing, and execution visibility before showcase features or broad platform surface area.
- Distinguish strictly between current truth and roadmap. Do not speak about planned Feishu or automation features as if they already exist.
- Preserve reusable business abstractions when they are cheap and obvious, but avoid premature tenantization, billing systems, or generalized workflow engines.
- Favor low-ops, low-training-cost, fast-to-adopt solutions because the current team is small and operational throughput matters more than architectural purity.
- Keep the delivery chain visible in product decisions: student intake, project matching, teaching execution, scheduling, feedback, and internal coordination.
- If the task moves into `ProjectTrack / SubProject / Milestone / Risk Board`, use `scf-delivery-workflow` alongside this skill instead of stretching current V1 objects.
- When discussing outward commercialization, let current internal efficiency win ties unless the user explicitly asks for a productized design.

## Current Priority

- Prioritize `auth`, `oa`, scheduling, feedback, chat, reminder/event plumbing, sales handoff, and teacher-reviewed feedback automation when choosing what to build next.
- Design `OpenClaw + Feishu` integrations as planned secondary extensions. Leave clean integration seams where useful, but do not invent non-existent APIs, flows, or guarantees.
- Treat `SMS` as the current low-friction student reminder channel, not as a workflow-state channel.
- Treat Tencent Meeting integration as a feedback-draft assistant path, not as a direct feedback-submission path.
- Keep handbook and agent features aligned with the same delivery business, but do not let them displace the OA core unless the task is explicitly about them.
- Optimize for decisions that reduce manual staff work, shorten coordination loops, and make delivery quality easier to track.

## Reference Guide

- Read [references/business-model.md](references/business-model.md) when the task depends on company stage, service model, customer definition, or productization framing.
- Read [references/integration-architecture.md](references/integration-architecture.md) when the task depends on `SMS`, Tencent Meeting, Mini Program, WeChat, Feishu, OpenClaw, multi-channel consistency, source-of-truth ownership, or system boundary defaults.
- Read [references/roles-and-workflows.md](references/roles-and-workflows.md) when the task depends on internal roles, workflow boundaries, permissions, information flow, or sales-to-enrollment handoff.
- Read [references/roadmap.md](references/roadmap.md) when the task touches the current V2 active streams, later delivery-model work, future channel expansion, or external-sale planning.
