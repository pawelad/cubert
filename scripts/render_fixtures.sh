# shellcheck shell=bash disable=SC2154
# Sourced by render.sh, which sets ts_dirs, tofu_dir and ansible_dir.
# Small projects and known errors for each render.
# hk skips a step when no file matches its glob, so a bare render proves nothing.

# Prose rules must leave values alone: an external API can use a British spelling in a
# field name or send an em dash. Both files pass, and so does a fixtures dir.
prose_fixture() {
  mkdir -p fixtures
  printf '{\n  "colour": "red \xe2\x80\x94 dark"\n}\n' >data.json
  printf -- '---\ncolour: "grey \xe2\x80\x94 dark"\n' >settings.yaml
  # A Markdown heading in a string is not a divider.
  printf 'story: |\n  ###### Fine print\n' >>settings.yaml
  printf '# Legacy\n\nThe colour is grey.\n' >fixtures/legacy.md
}

python_fixture() {
  mkdir -p tests
  printf '"""Demo module."""\n\n\ndef add(a: int, b: int) -> int:\n    """Return the sum of two numbers."""\n    return a + b\n' >demo.py
  printf 'from demo import add\n\n\ndef test_add_sums_two_numbers() -> None:\n    assert add(1, 2) == 3\n' >tests/test_demo.py
}

typescript_fixture() {
  local dir
  for dir in $(tr -d '[]",' <<<"$ts_dirs"); do
    mkdir -p "$dir/src"
    printf '{\n  "name": "demo",\n  "private": true,\n  "type": "module"\n}\n' >"$dir/package.json"
    printf '{\n  "compilerOptions": {\n    "strict": true,\n    "noEmit": true,\n    "module": "ESNext",\n    "moduleResolution": "bundler"\n  },\n  "include": ["src"],\n  "exclude": ["src/**/*.test.ts"]\n}\n' >"$dir/tsconfig.json"
    printf 'export const add = (a: number, b: number): number => a + b;\n' >"$dir/src/add.ts"
    printf 'import { expect, test } from "bun:test";\nimport { add } from "./add";\n\ntest("add sums two numbers", () => {\n  expect(add(1, 2)).toBe(3);\n});\n' >"$dir/src/add.test.ts"
  done
}

docker_fixture() {
  printf 'FROM debian:12.11-slim\nCMD ["sleep", "infinity"]\n' >Dockerfile
  cat >compose.yaml <<'YAML'
---
services:
  app:
    build: "."
    healthcheck:
      test: ["CMD", "true"]
      interval: "30s"
YAML
}

# A local dependency tests installation without adding a registry or another tool.
typescript_dependency_fixture() {
  local dir
  for dir in $(tr -d '[],"' <<<"$ts_dirs"); do
    mkdir -p "$dir/fixtures/library"
    printf '{"name":"demo-library","version":"1.0.0","main":"index.js","types":"index.d.ts"}\n' \
      >"$dir/fixtures/library/package.json"
    printf 'export const offset = 0;\n' >"$dir/fixtures/library/index.js"
    printf 'export declare const offset: number;\n' >"$dir/fixtures/library/index.d.ts"
    mise x -- jq '.dependencies = {"demo-library": "file:./fixtures/library"}' \
      "$dir/package.json" >"$dir/package.json.new"
    mv "$dir/package.json.new" "$dir/package.json"
    printf 'import { offset } from "demo-library";\n\nexport const add = (a: number, b: number): number => a + b + offset;\n' \
      >"$dir/src/add.ts"
    mise x -- bun install --cwd "$dir"
    # Commit the lock, then reproduce a fresh CI checkout without node_modules.
    rm -rf "$dir/node_modules"
  done
  mise run format --all
}

opentofu_fixture() {
  printf 'output "greeting" {\n  value = "hello"\n}\n' >"$tofu_dir/main.tf"
}

ansible_fixture() {
  mkdir -p "$ansible_dir/playbooks" "$ansible_dir/roles/demo/tasks"
  # Playbooks in playbooks/ do not find roles/ on their own.
  printf '[defaults]\nroles_path = roles\n' >"$ansible_dir/ansible.cfg"
  cat >"$ansible_dir/playbooks/site.yml" <<'YAML'
---
- name: "Configure the demo hosts"
  hosts: "all"
  roles:
    - role: "demo"
YAML
  cat >"$ansible_dir/roles/demo/tasks/main.yml" <<'YAML'
---
- name: "Say hello"
  ansible.builtin.debug:
    msg: "hello"
YAML
}

openspec_fixture() {
  mkdir -p openspec/changes/improve-greeting
  printf 'schema: "%s"\n' "$openspec" >openspec/changes/improve-greeting/.openspec.yaml
  if [ "$openspec" = changes-only ]; then
    # `openspec new change` marks schemas without a specs artifact the same way.
    printf 'skip_specs: true\n' >>openspec/changes/improve-greeting/.openspec.yaml
  fi
  cat >openspec/changes/improve-greeting/proposal.md <<'MARKDOWN'
# Improve the greeting

## Why

The demo needs a consistent greeting so callers receive the same friendly response.

## What Changes

- Return a friendly greeting to callers.

## Impact

- The demo greeting behavior.
MARKDOWN
  if [ "$openspec" = spec-driven ]; then
    mkdir -p openspec/specs/greeting openspec/changes/improve-greeting/specs/greeting
    cat >openspec/specs/greeting/spec.md <<'MARKDOWN'
# Greeting

## Purpose

Define the greeting returned to callers so the demo has a consistent response.

## Requirements

### Requirement: Greeting

The system SHALL return a greeting.

#### Scenario: Request a greeting

- **WHEN** a caller requests a greeting
- **THEN** the system returns hello
MARKDOWN
    {
      printf '## MODIFIED Requirements\n\n'
      sed -n '/^### Requirement:/,$p' openspec/specs/greeting/spec.md
    } >openspec/changes/improve-greeting/specs/greeting/spec.md
  fi
}

break_openspec_warning() {
  perl -0pi -e 's/The system SHALL return a greeting\./"The system SHALL return a greeting. " x 20/e' \
    openspec/specs/greeting/spec.md
}

break_openspec_info() {
  perl -pi -e 's/^### Requirement: Greeting$/### Requirement: Missing greeting/' \
    openspec/changes/improve-greeting/specs/greeting/spec.md
}

# An advisory must fail hk even when OpenSpec's strict exit status stays successful.
expect_openspec_info() {
  local info_log="$out/$name.openspec-info.log"
  break_openspec_info
  mise x -- openspec validate --all --strict >"$info_log" 2>&1
  grep -qF '[INFO]' "$info_log" || {
    cat "$info_log" >&2
    echo "render: the advisory fixture did not produce INFO" >&2
    return 1
  }
  expect_hook_failure openspec_info openspec
}

# Each case writes one known error. A check that stays green on it is not running.
break_prose() { printf '# Notes\n\nThe colour is red.\n' >notes.md; }
break_comment() { printf '# The colour is red.\n' >>settings.yaml; }
break_dash() { printf '# One \xe2\x80\x94 two.\n' >>settings.yaml; }
break_divider() { printf '# ----------\n' >>settings.yaml; }
# Default yamllint allows a plain string, so this fails only with the shared rules.
break_yaml() { printf 'plain: text\n' >>settings.yaml; }
break_typo() { printf '# Notes\n\nWe recieve data.\n' >notes.md; } # spellchecker:disable-line
break_link() { printf '[Gone](docs/gone.md)\n' >notes.md; }
# Split, so that no scanner flags this script.
break_secret() { printf 'token = "ghp_%s"\n' 'qOomCIZBWchHR4v5FPp9UiQRS9CyigrCkXXuIJQPfe63f12a' >notes.txt; }
break_python() { printf 'x: int = "text"\n' >>demo.py; }
break_typescript() {
  local dir
  dir="$(tr -d '[]",' <<<"$ts_dirs" | cut -d' ' -f1)"
  printf 'export const bad: number = "text";\n' >"$dir/src/bad.ts"
}
break_docker() { printf 'FROM debian\n' >Dockerfile; }
break_workflow() {
  printf 'on:\n  push:\n    branch: main\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - run: "true"\n' \
    >.github/workflows/broken.yml
}
break_opentofu() { printf 'output "greeting" {\nvalue = "hello"\n}\n' >"$tofu_dir/main.tf"; }
# Only the role changes, and the playbook that includes it stays as it is.
break_ansible() {
  printf -- '- name: "Say hello"\n  ansible.builtin.no_such_module:\n    msg: "hello"\n' \
    >"$ansible_dir/roles/demo/tasks/main.yml"
}

# A package test script must replace bun test, so a failing one fails the task.
expect_test_script() {
  local dir
  dir="$(tr -d '[]",' <<<"$ts_dirs" | awk '{ print $NF }')"
  mise x -- jq '.scripts.test = "exit 7"' "$dir/package.json" >"$dir/package.json.new"
  mv "$dir/package.json.new" "$dir/package.json"
  if mise run test:typescript >/dev/null 2>&1; then
    echo "render: test:typescript did not run the package test script" >&2
    return 1
  fi
  git checkout --quiet -- "$dir/package.json"
}

# CI must reject a uv.lock that no longer matches pyproject.toml. Install fails first.
expect_stale_uv_lock() {
  local log
  sed -i.bak 's/^version = "0.1.0"$/version = "0.2.0"/' pyproject.toml && rm pyproject.toml.bak
  if log="$(CI=true mise run ci:check 2>&1)" || ! grep -q 'needs to be updated' <<<"$log"; then
    echo "$log"
    echo "render: ci:check accepted a stale uv.lock" >&2
    return 1
  fi
  git checkout --quiet -- pyproject.toml
}

# One failing check step must not stop the fixers that run after it.
expect_format_despite_failure() {
  break_prose
  printf '{"a":1}\n' >format.json
  git add --all
  mise run format --all >/dev/null 2>&1 || true
  if [ "$(cat format.json)" = '{"a":1}' ]; then
    echo "render: a failing check step stopped format --all" >&2
    return 1
  fi
  git reset --quiet --hard HEAD
}

# Stage one error, expect the pre-commit step to fail on it, then undo it. The staged
# file selects the step, as in a real commit, and --check stops fixers from repairing it.
expect_hook_failure() {
  local feature="$1" step="$2" log
  "break_$feature"
  git add --all
  if log="$(mise x -- hk run pre-commit --check --step "$step" 2>&1)"; then
    echo "$log"
    echo "render: $step passed on a known $feature error" >&2
    return 1
  fi
  git reset --quiet --hard HEAD
}

# `clean` must run each project <area>:clean task.
expect_clean() {
  printf '\n[tasks."demo:clean"]\nrun = "touch .cleaned"\n' >>mise.toml
  mise run clean >/dev/null
  if [ ! -e .cleaned ]; then
    echo "render: clean did not run demo:clean" >&2
    return 1
  fi
  git checkout --quiet -- mise.toml
  rm .cleaned
}

# Cut two releases with the release task, so a header or format drift fails the render.
changelog_release() {
  local base origin
  # The release task commits and tags, and a CI runner has no git identity.
  export GIT_AUTHOR_NAME=render GIT_AUTHOR_EMAIL=render@example.com
  export GIT_COMMITTER_NAME=render GIT_COMMITTER_EMAIL=render@example.com
  base="$(git rev-parse HEAD)"
  origin="$(mktemp -d)/origin.git"
  git init --quiet --bare --initial-branch=main "$origin"
  git remote add origin "$origin"
  git push --quiet origin main
  mise run release 0.1.0 --no-push
  git -c user.name=render -c user.email=render@example.com commit --quiet --no-verify \
    --allow-empty -m "feat: add a feature with a subject long enough that dprint must wrap the entry"
  mise run release:preview | grep -q '^## \[Unreleased\]'
  git push --quiet origin main
  mise run release 0.2.0 --no-push
  if [ "$(grep -c '^# Changelog' CHANGELOG.md)" -ne 1 ]; then
    echo "render: the second release wrote a second changelog header" >&2
    return 1
  fi
  mise x -- dprint check CHANGELOG.md
  git tag --list 'v0.2.0' --format='%(contents)' | grep -q 'dprint must wrap'
  git tag --delete v0.1.0 v0.2.0 >/dev/null
  git remote remove origin
  git reset --quiet --hard "$base"
}
