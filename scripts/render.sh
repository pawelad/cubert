#!/usr/bin/env bash
# Render one feature combination into <out>/<name>, then run setup and check there.
# Name format: p1d0t1a0c1s1_changes-only (python, docker, opentofu, ansible, changelog,
# typescript; openspec).
set -euo pipefail

root="$1" out="$2" name="$3"
flags="${name%%_*}"
openspec="${name#*_}"
dest="$out/$name"
log="$out/$name.log"

bit() { [ "${flags:$1:1}" = "1" ] && echo true || echo false; }
python="$(bit 1)" docker="$(bit 3)" opentofu="$(bit 5)" ansible="$(bit 7)" changelog="$(bit 9)"
typescript="$(bit 11)"
# Alternate the directory list, so both the root and the monorepo shapes render.
if [ "$python" = true ]; then ts_dirs='["apps/web", "apps/api"]'; else ts_dirs='["."]'; fi
# Alternate the license, so both texts render without doubling the matrix.
ones="${flags//[^1]/}"
license="MPL-2.0"
if [ $((${#ones} % 2)) -eq 1 ]; then license="ARR"; fi

# The nested mise runs must resolve the rendered project, not cubert.
unset MISE_PROJECT_ROOT MISE_CONFIG_ROOT MISE_ORIGINAL_CWD MISE_TASK_NAME MISE_TASK_DIR MISE_TASK_FILE

# hk skips biome and tsc when no TypeScript file changed, so a bare render proves nothing.
# This adds a small project to each directory, so check and test run both tools.
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

run() {
  copier copy --quiet --defaults --vcs-ref HEAD \
    -d project_name="demo" -d description="A demo project." -d license="$license" \
    -d python="$python" -d docker="$docker" -d opentofu="$opentofu" \
    -d ansible="$ansible" -d changelog="$changelog" -d openspec="$openspec" \
    -d typescript="$typescript" -d typescript_dirs="$ts_dirs" \
    "$root" "$dest"
  cd "$dest"
  git -c init.defaultBranch=main init --quiet
  git add --all
  mise trust --quiet --all
  if [ "$typescript" = true ]; then typescript_fixture; fi
  mise run setup
  git add --all
  mise run check
  mise run test
}

rm -rf "$dest"
# Not `if (run)`: bash turns `set -e` off inside a condition, so only the last command
# could fail the render. A background subshell keeps it on.
(run) >"$log" 2>&1 &
if wait "$!"; then
  echo "pass $name"
else
  echo "FAIL $name (log: $log)"
  # CI keeps no files from the run, so show the end of the log there.
  if [ -n "${CI:-}" ]; then tail -n 40 "$log" | sed "s/^/  $name: /"; fi
  exit 1
fi
