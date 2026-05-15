# 2026-05-15 Agent skill CLI install

## Context

Users may first encounter DeckLens through an Agent skill instead of the
desktop settings panel. In that path, the Agent needs direct installer links and
a CLI command that can install the bundled skill into user-global Agent skill
folders after the app is installed.

## Decision

- Add `decklens install-skills` as the CLI surface for installing or refreshing
  the bundled `decklens-convert` skill.
- Share the same skill installation module between Electron settings and the
  CLI.
- Package the shared installer module beside the packaged CLI resources.
- Update the skill to use Cloudflare direct download links:
  `https://updates.dsxzai.com/download/mac`,
  `https://updates.dsxzai.com/download/windows`, and
  `https://updates.dsxzai.com/download`.

## ADR checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
