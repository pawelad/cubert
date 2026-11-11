#!/usr/bin/env bash
# Render one feature combination into <out>/<name>, then run setup and check there.
# Name format: p1d0t1a0c1_changes-only (python, docker, opentofu, ansible, changelog; openspec).
set -euo pipefail

root="$1" out="$2" name="$3"
flags="${name%%_*}"
openspec="${name#*_}"
dest="$out/$name"
log="$out/$name.log"

bit() { [ "${flags:$1:1}" = "1" ] && echo true || echo false; }
python="$(bit 1)" docker="$(bit 3)" opentofu="$(bit 5)" ansible="$(bit 7)" changelog="$(bit 9)"
# Alternate the license, so both texts render without doubling the matrix.
ones="${flags//[^1]/}"
license="MPL-2.0"
if [ $((${#ones} % 2)) -eq 1 ]; then license="ARR"; fi

# The nested mise runs must resolve the rendered project, not cubert.
unset MISE_PROJECT_ROOT MISE_CONFIG_ROOT MISE_ORIGINAL_CWD MISE_TASK_NAME MISE_TASK_DIR MISE_TASK_FILE

run() {
  copier copy --quiet --defaults --vcs-ref HEAD \
    -d project_name="demo" -d description="A demo project." -d license="$license" \
    -d python="$python" -d docker="$docker" -d opentofu="$opentofu" \
    -d ansible="$ansible" -d changelog="$changelog" -d openspec="$openspec" \
    "$root" "$dest"
  cd "$dest"
  git -c init.defaultBranch=main init --quiet
  git add --all
  mise trust --quiet --all
  mise run setup
  git add --all
  mise run check
  mise run test
}

rm -rf "$dest"
if (run) >"$log" 2>&1; then
  echo "pass $name"
else
  echo "FAIL $name (log: $log)"
  # CI keeps no files from the run, so show the end of the log there.
  if [ -n "${CI:-}" ]; then tail -n 40 "$log" | sed "s/^/  $name: /"; fi
  exit 1
fi
