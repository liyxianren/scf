---
name: scf-platform-context
description: Business, product, and integration architecture context for SCF's internal platform serving international-school students through customized project design and teaching delivery. Use when working on SCF OA, auth, scheduling, feedback, teacher/student collaboration, Mini Program or Feishu integration planning, OpenClaw or automation integration, notification architecture, handbook or agent extension decisions, multi-channel consistency, system boundary decisions, or internal-first productization planning for future external sale.
---

# SCF Platform Context

## Overview

Use this skill to ground product and technical decisions in SCF's actual business model instead of treating the repo like a generic school system or generic SaaS CRM.
Prioritize internal delivery efficiency first, then preserve the abstractions that could support future external commercialization.

## Core Product Frame

- Treat SCF as a small internal delivery team at the current stage, roughly 6 people. Use that as stage context, not as a permanent product constraint.
- Treat the core service as: understand a student's background, design a customized project, teach and deliver that project, then coordinate scheduling, execution, and feedback around it.
- Treat the main software user today as the internal SCF team. Optimize first for staff efficiency, operational clarity, and delivery quality.
- Treat international-school high school students applying overseas as the external service population, not as the current software buyer.
- Treat `OA / scheduling / feedback / collaboration loop` as the current product center.
- Treat handbook, agents, Mini Program, Feishu integration, and future productization as connected extensions of the same service model.

## Architecture Defaults

- Treat the website database and workflow services as the single source of truth for operational data and state transitions.
- Keep the current Flask monolith as the default application boundary unless the user explicitly asks for service decomposition.
- Route Mini Program, Feishu, OpenClaw, and other external channels through the website business layer or workflow-safe APIs instead of direct table writes or bypassed workflow steps.
- Treat Feishu documents and similar collaboration surfaces as mirrored output or structured action entrypoints, not as editable truth for official business state.
- Treat notifications such as Feishu app pushes or SMS as event consumers, not owners of workflow state.
- Prefer one-way mirrors, callback actions, or task submission over free-form bidirectional sync with external systems.

## Decision Rules

- Prioritize internal usability over building a polished multi-tenant SaaS shell too early.
- Prioritize scheduling, feedback, permissions, communication, and execution visibility before showcase features or broad platform surface area.
- Distinguish strictly between current truth and roadmap. Do not speak about planned Feishu or automation features as if they already exist.
- Preserve reusable business abstractions when they are cheap and obvious, but avoid premature tenantization, billing systems, or generalized workflow engines.
- Favor low-ops, low-training-cost, fast-to-adopt solutions because the current team is small and operational throughput matters more than architectural purity.
- Keep the delivery chain visible in product decisions: student intake, project matching, teaching execution, scheduling, feedback, and internal coordination.
- When discussing outward commercialization, let current internal efficiency win ties unless the user explicitly asks for a productized design.

## Current Priority

- Prioritize `auth`, `oa`, scheduling, feedback, chat, and internal coordination features when choosing what to build next.
- Design Feishu integrations as planned extensions. Leave clean integration seams where useful, but do not invent non-existent APIs, flows, or guarantees.
- Keep handbook and agent features aligned with the same delivery business, but do not let them displace the OA core unless the task is explicitly about them.
- Optimize for decisions that reduce manual staff work, shorten coordination loops, and make delivery quality easier to track.

## Reference Guide

- Read [references/business-model.md](references/business-model.md) when the task depends on company stage, service model, customer definition, or productization framing.
- Read [references/integration-architecture.md](references/integration-architecture.md) when the task depends on Mini Program, Feishu, OpenClaw, SMS, multi-channel consistency, source-of-truth ownership, or system boundary defaults.
- Read [references/roles-and-workflows.md](references/roles-and-workflows.md) when the task depends on internal roles, workflow boundaries, permissions, or information flow.
- Read [references/roadmap.md](references/roadmap.md) when the task touches Feishu, automated feedback generation, future integrations, or external-sale planning.
