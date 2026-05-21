# CommonAgent Agent Instructions

This file is the cross-tool instruction source for Codex, Cursor, Antigravity, and any other AI agent working in this repository. Tool-specific files may exist only as adapters that point back here.

## Read Order

Before changing files, read:

1. [README.md](README.md) for architecture, setup, API, memory, RAG, and `client_actions` contracts.
2. [docs/progress.md](docs/progress.md) for current task status and dependencies.
3. The relevant [docs/prompts/](docs/prompts/) task card when implementing a prompt task.

If you work inside `agent/`, also read [agent/AGENTS.md](agent/AGENTS.md) for graph invocation details.

## Source Of Truth

- `README.md` is the project architecture and operating contract.
- `AGENTS.md` is the cross-tool behavior contract for AI agents.
- `docs/progress.md` is the progress ledger.
- `docs/prompts/*.md` are task-level implementation scopes.
- `docs/prd/*.md` are design proposals, historical decisions, or future plans; they do not override `README.md` unless a completed task updates `README.md`.
- `docs/maps/*.md`, when present, are navigation maps derived from the current code and README; they must not introduce new contracts by themselves.
- `.cursor/skills/*/SKILL.md` are Cursor adapters only; do not duplicate core rules there.

## Governance

The repository uses this documentation order:

1. `AGENTS.md` defines how AI agents must work in this repository.
2. `README.md` defines the current runtime architecture, contracts, and operating rules.
3. `docs/progress.md` records task status, dependencies, and the recommended next task.
4. `docs/prompts/*.md` define the scope and test plan for one executable task.
5. `docs/prd/*.md` explain design intent and future direction.
6. `docs/maps/*.md` help humans and AI navigate the current code after large refactors.

Do not silently change this order or weaken these rules. If an AI agent believes the governance/documentation order should change, it must first explain the concrete problem, the proposed replacement rule, the expected benefit, and the risk, then ask the user for approval before editing the rule.

When a task changes architecture, API, state/context rules, memory semantics, RAG flow, `client_actions`, directory layout, environment contracts, or the documentation governance itself, update the relevant documents in the same change. Prefer the narrowest correct update:

- Runtime contract changes go in `README.md`.
- AI working-rule changes go in `AGENTS.md`.
- Task status and changelog entries go in `docs/progress.md`.
- Task scope changes go in the affected `docs/prompts/*.md`.
- Design rationale goes in `docs/prd/*.md`.
- Navigation and code maps go in `docs/maps/*.md` after the code structure exists.

## Working Rules

- Communicate with the user in Chinese by default, unless the user explicitly asks for another language or the content is better kept in its original language.
- Keep changes scoped to the requested task.
- Do not overwrite user changes. If existing edits affect the task, work with them.
- Do not commit, push, or create PRs unless explicitly asked.
- Do not commit `.env` files or real secrets.
- Agent environment contracts must keep `agent/src/settings/config.py`, `agent/.env.example`, and `agent/.env` synchronized:
  - Every environment-backed `Settings` field must appear in both env files with clear comments.
  - `.env.example` uses masked or blank example values; `.env` may contain local real values and must not be committed.
  - When adding, renaming, removing, or changing the meaning/default of a setting, update all three in the same change.
  - Run `cd agent && uv run pytest tests/test_settings.py -v` after environment contract changes; `test_env_files_match_settings_contract` is the guardrail.
- Prefer existing project patterns over new abstractions.
- Use `rg` / `rg --files` for repository search.
- Run the relevant tests from the task card or the smallest meaningful test set for the change.
- If tests cannot run because local services are missing, run mock/unit coverage and report what was skipped.

## Prompt Task Workflow

When executing one task under `docs/prompts/`:

1. Identify exactly one task card.
2. Read `README.md`, `docs/progress.md`, then the task card.
3. Check the task card's `## 建议执行模型` section before implementation.
   - If the current model or reasoning effort differs from the recommendation, stop and tell the user the recommended model/reasoning. Do not implement yet.
   - If the runtime cannot expose the current model or reasoning effort, treat it as unknown and ask the user to confirm or switch before implementation.
   - If the user explicitly says to ignore the recommendation or execute directly with the current model, continue.
4. Check dependencies in `docs/progress.md`; stop if required dependencies are not complete.
5. Implement only the task scope. Do not take adjacent tasks.
6. Run the task card's test plan.
7. Only after tests pass, update `docs/progress.md` if the task status changes.

## Contract Change Workflow

If a task card or user request changes architecture, API fields, state/context rules, memory semantics, RAG flow, `client_actions`, directory layout, or environment contracts:

1. Update `README.md` in the same change.
2. Update affected task cards only when their scope/API would otherwise become misleading.
3. Update `docs/progress.md` changelog for documentation-only contract changes.

If the change modifies AI working rules or the documentation governance itself, update `AGENTS.md` in the same change. If the change is a proposed improvement rather than a direct user instruction, get explicit user approval before editing `AGENTS.md`.

## Core Project Constraints

- Agent is internal-only; browsers must go through Back.
- `thread_id` is the checkpoint key.
- `user_id`, `role_id`, and `tools[]` are per-turn request context and must not be trusted from checkpoint state.
- External tools are emitted as `client_actions`; Agent does not execute them, wait for results, or resume.
- Back owns authentication, role calculation, and external tool whitelist filtering.
- Front owns `thread_id` storage and client action execution/approval.
- mem0 is local OSS `Memory` + local/internal Qdrant only. Do not use mem0 cloud, `MemoryClient`, `MEM0_API_KEY`, or `api.mem0.ai`.
- `MEM0_MOCK` and `QDRANT_MOCK` runtime defaults are `false`; tests should not assume mock defaults unless explicitly configured.

## Frontend Notes

If working on `front/`, keep the first screen as the usable app, not a marketing page. Preserve the current Front -> Back -> Agent boundary and do not make the browser call Agent directly.
