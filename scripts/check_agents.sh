#!/usr/bin/env bash
set -euo pipefail

# Fail if the shared block in AGENTS.md differs from a fresh render of the template.
# cubert follows its own template, so its shared rules must be the ones a project gets.
# With --fix, copy the rendered block into AGENTS.md first, then check.
# A plain copy, not the git repo, so the check sees uncommitted template edits.
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir "$work/src"
cp -R copier.yml template "$work/src/"
copier copy --quiet --defaults --data-file tests/cubert-answers.yml "$work/src" "$work/out" >/dev/null

shared() { sed -n '/^<!-- cubert:shared:start/,/^<!-- cubert:shared:end -->/p' "$1"; }
if [ "${1:-}" = "--fix" ]; then
  shared "$work/out/AGENTS.md" >"$work/shared"
  awk -v f="$work/shared" '
    /^<!-- cubert:shared:start/ { while ((getline l < f) > 0) print l; skip = 1; next }
    /^<!-- cubert:shared:end -->/ { skip = 0; next }
    !skip { print }' AGENTS.md >"$work/AGENTS.md"
  cp "$work/AGENTS.md" AGENTS.md
  # A diff that survives dprint's reflow means the template wraps differently.
  dprint fmt AGENTS.md >/dev/null
fi
if ! diff -u --label "render: AGENTS.md" --label "cubert: AGENTS.md" \
  <(shared "$work/out/AGENTS.md") <(shared AGENTS.md); then
  echo "shared-agents: wrap template/AGENTS.md.jinja lines the way dprint does." >&2
  [ "${1:-}" = "--fix" ] || echo "shared-agents: or run mise run format to copy the render." >&2
  exit 1
fi
