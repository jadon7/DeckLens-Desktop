# 2026-05-15 Agent skill install paths

## Context

DeckLens now ships an Agent skill that calls the product CLI. We need a default
installation strategy for Agents such as Claude, Codex, OpenClaw, and Hermes,
without depending on project-local paths or asking users to manually copy files
after installing the app.

The target is user-global installation. True OS-level system installation is
not consistently documented across these Agents and would require elevated
permissions on macOS and Windows.

## Findings

- Claude Code documents personal skills at `~/.claude/skills/<skill-name>/SKILL.md`
  and project skills at `.claude/skills/<skill-name>/SKILL.md`.
  Source: https://code.claude.com/docs/en/skills
- Codex defaults custom skill creation to `$CODEX_HOME/skills`, falling back to
  `~/.codex/skills` when `CODEX_HOME` is unset.
  Source: https://github.com/openai/codex/blob/main/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md
- OpenClaw supports multiple roots. User-global agent skills live in
  `~/.agents/skills`, managed/local OpenClaw skills live in `~/.openclaw/skills`,
  and workspace skills live under `<workspace>/skills` or
  `<workspace>/.agents/skills`.
  Source: https://docs.openclaw.ai/tools/skills
- Hermes uses `~/.hermes/skills` as its primary local skill directory. It can
  also scan external directories such as `~/.agents/skills` through
  `skills.external_dirs` in `~/.hermes/config.yaml`.
  Source: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/

## Decision

- Keep `skills/decklens-convert` as the canonical bundled skill in this repo.
- Do not silently write project-local skill directories such as `.claude/skills`
  or `<workspace>/skills` from the app installer.
- For a later installer/onboarding step, install or offer to install the same
  skill into user-global paths:
  - macOS/Linux: `~/.codex/skills/decklens-convert`,
    `~/.claude/skills/decklens-convert`, `~/.agents/skills/decklens-convert`,
    `~/.openclaw/skills/decklens-convert`, and
    `~/.hermes/skills/decklens-convert` when the corresponding product is
    detected.
  - Windows: `%USERPROFILE%\.codex\skills\decklens-convert`,
    `%USERPROFILE%\.claude\skills\decklens-convert`,
    `%USERPROFILE%\.agents\skills\decklens-convert`,
    `%USERPROFILE%\.openclaw\skills\decklens-convert`, and
    `%USERPROFILE%\.hermes\skills\decklens-convert` when the corresponding
    product is detected.
- Prefer an explicit "Install Agent Skill" control in DeckLens settings instead
  of doing this silently during first install. This makes filesystem changes
  visible and lets users opt into only the Agents they use.
- The installer must be idempotent: copy the complete skill folder, preserve
  `SKILL.md`, overwrite only the DeckLens-managed skill copy, and expose an
  uninstall option.
- The skill must continue to call `decklens convert` as the stable product
  surface. If the CLI is missing, the skill should direct users to the official
  DeckLens download page instead of exposing backend dependencies.

## ADR checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
