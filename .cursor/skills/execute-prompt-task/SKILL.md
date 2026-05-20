---
name: execute-prompt-task
description: Cursor adapter for executing one docs/prompts/*.md task in commonAgent. Use when the user opens, @-mentions, or asks to run a docs/prompts task card. Core project rules live in the root AGENTS.md.
paths:
  - "docs/prompts/**/*.md"
  - "docs/prompts/*.md"
---

# Cursor Adapter: Execute Prompt Task

This skill is only a Cursor trigger/adapter. Do not duplicate project rules here.

Before making changes, read and follow:

1. [AGENTS.md](../../../AGENTS.md)
2. [README.md](../../../README.md)
3. [docs/progress.md](../../../docs/progress.md)
4. The current `docs/prompts/XX-*.md` task card

Cursor-specific workflow:

1. Resolve exactly one task card from the user message or opened file.
2. Check the task dependencies in `docs/progress.md`.
3. If dependencies are complete, implement only that card's scope.
4. Run the task card's test plan.
5. Update `docs/progress.md` only after tests pass.

If the task card changes architecture/API/memory/RAG/client_actions/environment contracts, first use the sibling `sync-prompt-architecture` adapter to sync the root `README.md`.
