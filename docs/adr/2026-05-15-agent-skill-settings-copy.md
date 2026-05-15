# 2026-05-15 Agent skill settings copy

## Context

The Agent Skill settings row showed each detected Agent as a separate visual
pill. That made the settings panel busier than needed because the helper copy
already explains which tools can use the installed skill.

## Decision

- Remove per-Agent pill rendering from the settings panel.
- Keep the helper text, install button, and underlying detected-target install
  logic unchanged.

## ADR checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
