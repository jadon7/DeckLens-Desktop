# 2026-05-15 Agent skill version management

## Context

DeckLens installs an Agent skill into user-global Agent directories. Those
copies need a controlled update path after the app ships new skill behavior,
without overwriting local edits the user may have made.

## Decision

- Add DeckLens version metadata to `skills/decklens-convert/SKILL.md`.
- Hash skill folders excluding `.decklens-managed.json` and `.DS_Store`.
- Store install metadata in `.decklens-managed.json`, including skill version,
  source hash, installed hash, app version, and install time.
- Treat local changes as protected: if the current installed hash differs from
  the recorded installed hash, skip updates unless `--force` is passed.
- Add `decklens skills status` and `decklens skills update` while keeping
  `decklens install-skills` as the first-install command.
- Surface skill update availability in the settings panel through the same
  shared install/status module.

## ADR checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
