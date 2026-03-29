# Integration Architecture

- The website application and database are the single source of truth for business state and workflow transitions.
- The Flask monolith remains the default application boundary unless service decomposition is explicitly requested.
- `SMS`, Tencent Meeting, Mini Program, WeChat, Feishu, OpenClaw, and similar external channels must go through website business services or workflow-safe APIs instead of writing directly to tables.
- The sales frontend is a pre-`Enrollment` entry surface, not a separate CRM truth owner.
- `SMS` should only handle reminder delivery, retries, and audit, not workflow-state ownership.
- Tencent Meeting should be treated as a source of recordings, transcripts, and notes that may generate feedback drafts, not as the authoritative owner of course-feedback state.
- Feishu should be treated as a mirrored output surface or structured action entrypoint, not as the authoritative owner of business data.
- Notifications and external automation should consume events rather than own workflow state.
