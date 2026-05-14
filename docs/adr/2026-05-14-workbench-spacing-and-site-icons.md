# ADR: Workbench Spacing and Site Icons

- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

## Context

The desktop workbench heading needed tighter top spacing after recent topbar
changes. The website feature icon layout also needed to keep icons in the
dedicated icon box instead of inline with the heading, matching the neighboring
feature rows.

Hero social links were text-only, making them weaker than the footer links and
harder to scan visually.

## Decision

- Change the desktop workbench heading margin to `20px auto 36px`.
- Move the feature icon for "元素分层可人工校对" into the existing icon box and
  leave the heading as plain text.
- Reuse the existing committed social platform SVGs for the website hero social
  links and serve them from `site/assets/social/`.

## Consequences

- The desktop workbench starts closer to the top while retaining bottom spacing.
- The website feature rows use a consistent icon pattern.
- Hero social links are easier to recognize without adding new external assets.
