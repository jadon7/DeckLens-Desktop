# Architecture Decision Records

Use this directory for changes that affect code, runtime behavior, dependencies, deployment, hooks, data handling, or user-facing workflows.

The local pre-commit hook requires an ADR whenever staged code/config changes are committed. This makes the commit author confirm both sides of the change:

- The code change is necessary.
- The relevant documentation has been updated.
- The change is not speculative or over-clever.

## Filename

```text
docs/adr/YYYY-MM-DD-short-title.md
```

## Required Checklist

Every ADR used to satisfy the hook must include these exact checked lines:

```markdown
- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever
```

If any of those statements is false, do not force the commit through. Rework the task or remove the code change.
