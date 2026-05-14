# ADR: Persistent Desktop Settings

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

DeckLens desktop settings were stored in renderer `localStorage`. That is enough
for normal browser sessions, but it can be lost across Electron runtime resets,
profile changes, or packaged-app storage differences. The fal.ai API key is a
user-entered credential needed by AI intelligent layering, so asking for it
again after restarting the app breaks the desktop workflow.

## Decision

Persist user settings through Electron main-process IPC in
`app.getPath("userData")/settings.json`. The preload bridge exposes a small
`settings.get` and `settings.set` API, and the renderer still mirrors values to
`localStorage` as a fallback.

The stored settings are limited to the current desktop preferences:
`falApiKey`, `inpaintBackend`, `language`, and `firstRunSeen`. The main process
filters all incoming setting keys before writing them to disk.

## Consequences

- User-entered API keys survive app restarts in the same desktop profile.
- Settings are available before the user starts an AI intelligent layering job.
- Renderer code does not get arbitrary filesystem access; it only calls the
  bounded settings IPC methods exposed by preload.
