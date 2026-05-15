# 2026-05-15 Agent skill settings installer

## Context

DeckLens includes an Agent skill that should be usable by local Agents without
manual file copying. The app needs a visible, reversible way to install the
bundled skill into user-global Agent skill folders after DeckLens is installed.

## Decision

- Package `skills/decklens-convert` into the Electron release resources.
- Add Electron IPC methods for reading Agent skill install status and installing
  the bundled skill.
- Install only into detected user-global locations, plus the shared
  `~/.agents/skills` location:
  `~/.codex/skills`, `~/.claude/skills`, `~/.agents/skills`,
  `~/.openclaw/skills`, and `~/.hermes/skills`.
- Expose the action from the settings panel as an explicit "Install Agent Skill"
  button rather than silently writing into user directories on startup.
- Keep the skill contract on `decklens convert`; if DeckLens or the CLI is
  missing, the skill asks for permission and helps the user install DeckLens
  from the official download page.

## ADR checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
