# Integration Architecture

- The website application and database are the single source of truth for business state and workflow transitions.
- The Flask monolith remains the default application boundary unless service decomposition is explicitly requested.
- Mini Program, Feishu, OpenClaw, and similar external channels must go through website business services or workflow-safe APIs instead of writing directly to tables.
- Feishu should be treated as a mirrored output surface or structured action entrypoint, not as the authoritative owner of business data.
- Notifications and external automation should consume events rather than own workflow state.
