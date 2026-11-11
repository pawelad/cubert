# shellcheck shell=bash disable=SC2154
# Sourced by render.sh, which sets ts_dirs, tofu_dir and ansible_dir.
# Small projects and known errors for each render.
# hk skips a step when no file matches its glob, so a bare render proves nothing.

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

# Each case writes one known error. A check that stays green on it is not running.
break_python() { printf 'x: int = "text"\n' >>demo.py; }
break_typescript() {
  local dir
  dir="$(tr -d '[]",' <<<"$ts_dirs" | cut -d' ' -f1)"
  printf 'export const bad: number = "text";\n' >"$dir/src/bad.ts"
}
break_docker() { printf 'FROM debian\n' >Dockerfile; }
break_opentofu() { printf 'output "greeting" {\nvalue = "hello"\n}\n' >"$tofu_dir/main.tf"; }
# Only the role changes, and the playbook that includes it stays as it is.
break_ansible() {
  printf -- '- name: "Say hello"\n  ansible.builtin.no_such_module:\n    msg: "hello"\n' \
    >"$ansible_dir/roles/demo/tasks/main.yml"
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
