# Desktop I18n Settings

## Status

Accepted

## Context

DeckLens Desktop is now the primary product surface. The app was still mostly
Chinese-only, while the public desktop repository and release packaging are
intended for broader open-source distribution.

The language behavior needs to be simple for a desktop app: follow the user's
system language by default, but allow an explicit override without requiring a
restart.

## Decision

- Add a lightweight renderer-side i18n layer for the main workbench template.
- Support Chinese and English initially.
- Store the user's override in local storage, with `system` as the default
  preference.
- Add a language selector to the existing settings modal.
- Localize the first-run Electron runtime setup page from the system language,
  since settings are not available before the backend runtime is installed.
- Keep server-generated conversion progress messages as returned by the backend
  for now; the shell chrome, settings, upload flow, status structure, result
  summary, and preview controls are localized client-side.

## Consequences

- Adding new visible UI text in `templates/index.html` should include matching
  Chinese and English dictionary entries.
- Future backend progress localization should use structured status codes
  rather than translating arbitrary server text in the browser.
- The settings modal remains the single place for user-controlled desktop
  preferences.

## Checklist

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
