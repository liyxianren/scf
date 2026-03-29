---
name: scf-docs-governance
description: Maintain SCF's versioned docs, status docs, handoff notes, AGENTS/CLAUDE entrypoints, and any repo-local skill guidance that must stay aligned with those docs. Use when updating docs/README.md, docs/versions/*.md, docs/architecture/current-system.md, docs/handoff/current-focus.md, docs/governance/docs-governance.md, or when deciding which documentation and repo-local skills must change for a given product, architecture, or handoff update.
---

# SCF Docs Governance

## Read First

1. Read `docs/README.md`.
2. Read `docs/governance/docs-governance.md`.
3. Read `docs/versions/V1.md` and `docs/versions/V1-status.md` before updating current-state claims.
4. Read the relevant target doc:
   - Use `docs/versions/V2.md` for next-stage planning.
   - Use `docs/versions/V3.md` for long-range direction.
   - Use `docs/architecture/current-system.md` for system-boundary updates.
   - Use `docs/handoff/current-focus.md` for active-stream updates.
5. Use the matching starter under `docs/templates/` when drafting a new status, handoff, or version doc.

## Decision Tree

- If runtime facts, shipped scope, or current risks changed:
  - Update `docs/versions/V1-status.md`
  - Update `docs/versions/V1.md` only if the shipped capability boundary changed
- If the active stream, dirty worktree, or handoff state changed:
  - Update `docs/handoff/current-focus.md`
- If next-stage or future-stage goals changed:
  - Update `docs/versions/V2.md` or `docs/versions/V3.md`
- If the system boundary or main business objects changed:
  - Update `docs/architecture/current-system.md`
- If reading order, doc tree structure, or entrypoint rules changed:
  - Update `docs/README.md`
  - Update `AGENTS.md` and `CLAUDE.md`
- If version facts, entrypoint rules, or business framing changed in a way that would stale a repo-local skill:
  - Update the affected `skills/*/SKILL.md`
  - Update the affected `skills/*/references/*` files when the detailed framing changed
  - Update the affected `skills/*/agents/openai.yaml` so the UI metadata still matches

## Core Rules

- Treat code, tests, and recent commits as the source for `V1` facts.
- Treat `docs/versions/*.md` as product-plan truth.
- Keep `AGENTS.md` and `CLAUDE.md` short. They are entrypoint files, not full specifications.
- Keep repo-local skills aligned with `docs/` when trigger conditions, reading order, or business framing changes.
- Update `docs/handoff/current-focus.md` before ending a large task or switching the active stream.
- Use the fixed status states in `docs/versions/V1-status.md`:
  - `Done`
  - `In Progress`
  - `Planned`
  - `Risk`
- Keep the existing `V1-status` table shape; do not invent new columns unless the governance rules change.
- Use repo-local evidence only. Do not cite chat history as a documentation source.
- Start new docs from `docs/templates/` when a matching template exists.

## Do Not

- Do not mark a feature as done without evidence.
- Do not put roadmap details back into `AGENTS.md`.
- Do not let repo-local skills become the only place where important project knowledge exists.
