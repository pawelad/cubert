#!/usr/bin/env bash
# Render one feature combination into <out>/<name>, then run setup and check there.
# Name format: p1d0t1a0c1s1_changes-only (python, docker, opentofu, ansible, changelog,
# typescript; openspec).
set -euo pipefail

root="$1" out="$2" name="$3"
# shellcheck source=scripts/e2e_env.sh
source "$root/scripts/e2e_env.sh"
flags="${name%%_*}"
openspec="${name#*_}"
dest="$out/$name"
log="$out/$name.log"

bit() { [ "${flags:$1:1}" = "1" ] && echo true || echo false; }
python="$(bit 1)" docker="$(bit 3)" opentofu="$(bit 5)" ansible="$(bit 7)" changelog="$(bit 9)"
typescript="$(bit 11)"
opentofu_dir=opentofu ansible_dir=ansible
# Alternate the state backup with docker, so both OpenTofu shapes render.
state_backup=false
if [ "$opentofu" = true ] && [ "$docker" = false ]; then state_backup=true; fi
# Alternate the directory list, so both the root and the monorepo shapes render.
if [ "$python" = true ]; then ts_dirs='["apps/web", "apps/api"]'; else ts_dirs='["."]'; fi
# Alternate the license, so both texts render without doubling the matrix.
ones="${flags//[^1]/}"
license="MPL-2.0" year=()
if [ $((${#ones} % 2)) -eq 1 ]; then license="ARR" year=(-d copyright_year=2026); fi

# shellcheck source=scripts/render_fixtures.sh
source "$root/scripts/render_fixtures.sh"

# Parallel renders share one mise data dir. Concurrent installs of a new project's `lts`
# and `latest` seeds race: npm tools then fail on "node@lts ... is not installed".
setup_one_at_a_time() {
  local lock="$out/.setup.lock" status=0
  until mkdir "$lock" 2>/dev/null; do sleep 1; done
  mise run setup || status=$?
  rmdir "$lock"
  return "$status"
}

run() {
  copier copy --quiet --defaults --vcs-ref HEAD \
    -d project_name="demo" -d description="A demo project." -d license="$license" ${year[@]+"${year[@]}"} \
    -d python="$python" -d docker="$docker" -d opentofu="$opentofu" \
    -d opentofu_state_backup="$state_backup" \
    -d ansible="$ansible" -d changelog="$changelog" -d openspec="$openspec" \
    -d typescript="$typescript" -d typescript_dirs="$ts_dirs" \
    "$root" "$dest"
  cd "$dest"
  git -c init.defaultBranch=main init --quiet
  git add --all
  mise trust --quiet --all
  prose_fixture
  if [ "$python" = true ]; then python_fixture; fi
  if [ "$typescript" = true ]; then typescript_fixture; fi
  if [ "$docker" = true ]; then docker_fixture; fi
  if [ "$opentofu" = true ]; then opentofu_fixture; fi
  if [ "$ansible" = true ]; then ansible_fixture; fi
  if [ "$openspec" != none ]; then openspec_fixture; fi
  setup_one_at_a_time
  if [ "$typescript" = true ]; then typescript_dependency_fixture; fi
  git add --all
  # A runner starts without application dependencies, unlike a checkout after setup.
  CI=true mise run ci:check
  if [ "$opentofu" = true ]; then
    # Setup and check must not touch the state backend or its data dir.
    [ ! -e "$opentofu_dir/.terraform" ] || {
      echo "render: setup or check ran tofu init" >&2
      exit 1
    }
    [ -z "$(git status --porcelain --untracked-files=all "$opentofu_dir/.terraform-validate")" ] \
      || {
        echo "render: .terraform-validate is not ignored" >&2
        exit 1
      }
  fi

  # The lockfile scan needs the network, so it runs here and not in check.
  mise run audit:deps

  git -c user.name=render -c user.email=render@example.com commit --quiet --no-verify -m "chore: render"
  if [ "$changelog" = true ]; then changelog_release; fi
  if [ "$typescript" = true ]; then expect_test_script; fi
  if [ "$python" = true ]; then expect_stale_uv_lock; fi
  expect_format_despite_failure
  expect_clean
  expect_hook_failure prose no-british-english
  expect_hook_failure comment no-british-english-comments
  expect_hook_failure dash no-em-dashes-comments
  expect_hook_failure yaml yamllint
  expect_hook_failure divider no-dividers
  expect_hook_failure typo typos
  expect_hook_failure link lychee
  expect_hook_failure secret betterleaks
  expect_hook_failure workflow jactionlint
  if [ "$python" = true ]; then expect_hook_failure python mypy; fi
  if [ "$typescript" = true ]; then expect_hook_failure typescript "tsc"; fi
  if [ "$docker" = true ]; then expect_hook_failure docker "hadolint"; fi
  if [ "$opentofu" = true ]; then expect_hook_failure opentofu "tofu-fmt"; fi
  if [ "$ansible" = true ]; then
    expect_hook_failure ansible "ansible-syntax-check"
    expect_hook_failure ansible_template_expression "ansible-template" "cubert-jinja:"
    expect_hook_failure ansible_template_statement "ansible-template" "cubert-jinja:"
    expect_hook_failure ansible_template_custom "ansible-template" "cubert-jinja:"
  fi
  if [ "$openspec" = spec-driven ]; then
    expect_hook_failure openspec_warning openspec
    expect_openspec_info
  fi
}

# Not `if (run)`: bash turns `set -e` off inside a condition, so only the last command
# could fail the render. A background subshell keeps it on.
attempt() {
  rm -rf "$dest"
  (run) >"$log" 2>&1 &
  status=0
  wait "$!" || status=$?
}
attempt
retry=""
# Cross-platform locking can hit GitHub's download limits. An immediate retry can
# fail before setup when mise resolves the Python runtime for Copier.
if [ "$status" -ne 0 ] && grep -qE \
  'lock-time provenance verification failed|HTTP status client error \(403 Forbidden\).*https://github.com/[^/]+/[^/]+/releases/download/' "$log"; then
  mv "$log" "$log.first"
  echo "retry $name after 60s: mise download failed (first log: $log.first)"
  sleep 60
  attempt
  retry=" (after a mise download retry, first log: $log.first)"
fi
if [ "$status" -eq 0 ]; then
  echo "pass $name$retry"
else
  echo "FAIL $name$retry (log: $log)"
  # Show the failure immediately; CI also uploads the full logs as artifacts.
  if [ -n "${CI:-}" ]; then tail -n 40 "$log" | sed "s/^/  $name: /"; fi
  exit 1
fi
