# shellcheck shell=bash
# Sourced by the e2e tasks after they choose out.
mkdir -p "$out"
out="$(cd "$out" && pwd -P)"
# Renders inside cubert must not inherit its tools and tasks from parent directories.
export MISE_CEILING_PATHS="$out"
unset MISE_PROJECT_ROOT MISE_CONFIG_ROOT MISE_ORIGINAL_CWD MISE_TASK_NAME MISE_TASK_DIR MISE_TASK_FILE
