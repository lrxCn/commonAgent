---
name: sync-prompt-architecture
description: Cursor adapter for keeping the root README.md aligned when docs/prompts task cards or project contracts change. Core project rules live in the root AGENTS.md.
paths:
  - "docs/prompts/**/*.md"
  - "docs/prompts/*.md"
  - "README.md"
  - "AGENTS.md"
---

# Cursor Adapter: Sync Prompt Architecture

This skill is only a Cursor trigger/adapter. Do not duplicate project rules here.

Before changing documentation, read and follow:

1. [AGENTS.md](../../../AGENTS.md)
2. [README.md](../../../README.md)
3. [docs/progress.md](../../../docs/progress.md)
4. The affected `docs/prompts/XX-*.md` task card

Use this adapter when a task card or user request changes any project-level contract:

- Front / Back / Agent boundaries
- auth, context, checkpoint, or state rules
- memory, summary, mem0, RAG, rewrite, ingest, or `client_actions`
- API paths, request/response fields, SSE event format
- environment variable contract or default constants
- task list / phase-level status

Cursor-specific workflow:

1. Compare the changed task card or user request against `README.md`.
2. Update only the affected README sections.
3. Update affected task cards only if they would otherwise mislead future agents.
4. Add a short `docs/progress.md` changelog row for documentation-only contract changes.
5. Do not implement business code unless the user separately asks for implementation.
