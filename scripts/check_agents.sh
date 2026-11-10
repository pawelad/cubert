#!/usr/bin/env bash
set -euo pipefail

# Fail if the shared block in AGENTS.md differs from a fresh render of the template.
# cubert follows its own template, so its shared rules must be the ones a project gets.
# A plain copy, not the git repo, so the check sees uncommitted template edits.
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir "$work/src"
cp -R copier.yml template "$work/src/"
copier copy --quiet --defaults --data-file tests/cubert-answers.yml "$work/src" "$work/out" >/dev/null

shared() { sed -n '/^<!-- cubert:shared:start/,/^<!-- cubert:shared:end -->/p' "$1"; }
if ! diff -u --label "render: AGENTS.md" --label "cubert: AGENTS.md" \
  <(shared "$work/out/AGENTS.md") <(shared AGENTS.md); then
  echo "shared-agents: copy the rendered shared block into AGENTS.md (or change template/AGENTS.md.jinja)." >&2
  exit 1
fi
