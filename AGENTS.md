# AGENTS.md

This file is the Codex entrypoint for this repository.

## Current Truth

- SCF Hub is currently an internal delivery platform centered on `auth + enrollment + workflow + oa + feedback + chat`.
- Backend integration tests exist under `tests/integration/`.
- Explicit project-delivery management is still a V2 target, not a shipped model.

## Read This First

Read these files in order before making broad architectural or product assumptions or continuing active work:

1. `docs/README.md`
2. `docs/versions/V1-status.md`
3. `docs/handoff/current-focus.md`
4. `docs/versions/V1.md`
5. `docs/versions/V2.md`
6. `docs/versions/V3.md`
7. `docs/architecture/current-system.md`
8. `docs/governance/docs-governance.md`

## Skill Triggers

- Use `scf-platform-context` first when the task touches `oa`, `auth`, scheduling, feedback, chat, project-delivery design, or internal workflow boundaries.
- Use `openai-docs` only for OpenAI API/product/model questions.
- Use `scf-docs-governance` for any update to `docs/`, `AGENTS.md`, or `CLAUDE.md`.
- Use `scf-delivery-workflow` for `ProjectTrack / SubProject / Milestone / Risk Board / 2+1 / 1+1+1` work.
- Use `skill-creator` when creating or restructuring repo-local skills themselves.
- Repo-local skills live under `skills/` as source-controlled assets.
- Automatic triggering still depends on installation under `$CODEX_HOME/skills`.
- If repo-local skills are not installed, manually read:
  - `skills/scf-docs-governance/SKILL.md`
  - `skills/scf-delivery-workflow/SKILL.md`

## Verification

```bash
pip install -r requirements.txt
python app.py
pytest -q tests/integration
pytest -q tests/integration/test_enrollment_flow.py tests/integration/test_oa_p1_regressions.py
```

Notes:

- The app defaults to port `5000`, or uses `PORT`.
- SQLite path is controlled by `SCF_DB_PATH`.
- C execution requires `gcc`.

## Maintenance Rule

Detailed facts live in `docs/`. This file only provides reading order, trigger rules, and minimum verification commands.
