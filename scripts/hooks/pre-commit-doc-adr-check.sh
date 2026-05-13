#!/bin/sh
set -eu

changed_files=$(
  git diff --cached --name-only --diff-filter=ACMR
)

if [ -z "$changed_files" ]; then
  exit 0
fi

code_files=$(
  printf '%s\n' "$changed_files" | awk '
    /\.py$/ ||
    /\.js$/ ||
    /\.jsx$/ ||
    /\.ts$/ ||
    /\.tsx$/ ||
    /\.css$/ ||
    /\.scss$/ ||
    /\.html$/ ||
    /\.sh$/ ||
    /\.json$/ ||
    /\.ya?ml$/ ||
    /\.toml$/ ||
    /^Dockerfile$/ ||
    /^requirements\.txt$/ ||
    /^render\.yaml$/ ||
    /^app\.py$/ ||
    /^engine\.py$/ {
      print
    }
  '
)

if [ -z "$code_files" ]; then
  exit 0
fi

doc_files=$(
  printf '%s\n' "$changed_files" | awk '
    /^README\.md$/ ||
    /^DEPLOYMENT\.md$/ ||
    /^docs\/.*\.md$/ ||
    /\.md$/ {
      print
    }
  '
)

adr_files=$(
  printf '%s\n' "$changed_files" | awk '/^docs\/adr\/[0-9]{4}-[0-9]{2}-[0-9]{2}-.*\.md$/ { print }'
)

fail() {
  cat >&2 <<EOF

DeckLens commit gate blocked this commit.

Staged code/config changes require two-way confirmation:
1. If the code change is necessary, update documentation and add an ADR under docs/adr/.
2. If the code change is speculative or over-clever, do not commit it; unstage/rework it and re-plan.

Required ADR checklist:
- [x] Code change is necessary
- [x] Documentation updated
- [x] Not speculative or over-clever

Staged code/config files:
$code_files

EOF
  exit 1
}

if [ -z "$doc_files" ]; then
  fail
fi

if [ -z "$adr_files" ]; then
  fail
fi

for adr in $adr_files; do
  content=$(git show ":$adr" 2>/dev/null || true)
  printf '%s\n' "$content" | grep -Fq -- "- [x] Code change is necessary" || fail
  printf '%s\n' "$content" | grep -Fq -- "- [x] Documentation updated" || fail
  printf '%s\n' "$content" | grep -Fq -- "- [x] Not speculative or over-clever" || fail
done

exit 0
