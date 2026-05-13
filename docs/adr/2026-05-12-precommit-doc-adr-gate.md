# ADR: Pre-Commit Documentation and ADR Gate

- Status: Accepted
- Date: 2026-05-12

## Context

DeckLens has had several large runtime and architecture changes, including memory-safe defaults, optional SAM/LaMa behavior, Qwen/fal.ai layering, and page-level font normalization. When code changes are committed without documentation, the project quickly accumulates stale PRDs and misleading operational notes.

The project needs a local commit-time guard that makes the author confirm whether a code change is necessary and whether the corresponding documentation has been updated.

## Decision

Install a local Git `pre-commit` hook that delegates to `scripts/hooks/pre-commit-doc-adr-check.sh`.

The hook checks staged changes:

- Documentation-only commits pass.
- Code/config commits must include a staged documentation change.
- Code/config commits must include a staged ADR under `docs/adr/YYYY-MM-DD-title.md`.
- The ADR must explicitly check the required confirmation lines.

Required confirmation:

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Consequences

Necessary code changes now carry their reasoning and documentation updates in the same commit.

Speculative or self-directed code changes should be rejected before commit. The right response is to unstage or revert the code and re-plan the task instead of bypassing the hook.

This hook is local to this checkout. The versioned script and ADR instructions are committed so the hook can be reinstalled in another clone.

## Installation

```bash
cp scripts/hooks/pre-commit-doc-adr-check.sh .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```
