# Shared Agent Skill Root

## Context

DeckLens originally installed the same Agent skill into several user-global agent-specific directories. That made the filesystem noisy and could produce duplicate skill discovery when an Agent scans both its own skill directory and the shared `~/.agents/skills` directory.

The `skills` CLI behavior used by `npx -y skills add https://open.feishu.cn --skill -y` uses a cleaner model: install the skill content once under `.agents/skills/<skill-name>` and expose it as a project/global Agent skill from that shared root.

## Decision

DeckLens now treats `~/.agents/skills/decklens-convert` as the only default install target.

Legacy DeckLens-managed copies under agent-specific directories are detected for status, but a normal install/update removes those legacy copies when they are still DeckLens-managed and unmodified:

- `~/.codex/skills/decklens-convert`
- `~/.claude/skills/decklens-convert`
- `~/.openclaw/skills/decklens-convert`
- `~/.hermes/skills/decklens-convert`

If a legacy copy is unmanaged or modified by the user, DeckLens leaves it in place and reports it as skipped.

## Verification Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
- [x] Fresh install writes only the shared Agent skill root.
- [x] Install cleans unmodified DeckLens-managed legacy copies.
- [x] Install does not remove unmanaged or modified legacy copies.
