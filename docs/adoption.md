# Adopt cubert in an existing repository

These steps bring an existing repository onto cubert. A new project follows
[Start a new project](../README.md#start-a-new-project) instead.

Copy from GitHub, not from a local clone. Copier records the source in
`.copier-answers.yml`, and a local path breaks updates on other machines.

1. Start on a clean branch. Before Copier runs, write an inventory, such as
   `tmp/reports/<date>-cubert-adoption.md`. Later steps check against it:
   - The files that Copier replaces or adds. Render a fresh copy in `/tmp`, and list
     each of its files that the repository already has.
   - The tasks that a shared task replaces or the naming rules rename, with every caller
     of each: docs, CI, hooks, scripts and other tasks.
   - The project's hk steps, and which of them the shared steps replace.
   - Each credential, where it lives, and where it goes.
   - The ignored files, as a baseline. `--directory` lists an ignored directory, such as
     `node_modules/`, once:

     ```console
     $ mkdir -p tmp
     $ git ls-files --others --ignored --exclude-standard --directory >tmp/ignored-before.txt
     ```

     After the adoption, a path that drops out of the list is no longer ignored.
2. Copy over the existing files, answering the questions for this project:

   ```console
   $ mise x pypi:copier -- copier copy --overwrite gh:pawelad/cubert .
   ```

3. Review `git diff`. Copier replaced each template-owned and merged file that existed,
   such as `AGENTS.md`, `README.md`, `docs/README.md`, `.gitignore`, `.config/wt.toml`
   and `dependabot.yml`. Put the project's own content back into each merged file, below
   the shared parts:
   - Copier keeps an existing `ci.yml` and `audit.yml`, because they are project-owned.
     Replace their check and audit jobs with calls to `cubert-check.yml` and
     `cubert-audit.yml` (see [conventions.md](../template/docs/conventions.md#ci)). Keep
     application jobs, image scans and deployment gates. When those jobs already run
     some `check:<area>` or `test:<area>` tasks, list them in `CI_CHECK_SKIP`.
   - A path filter that lists `mise.toml` must also list `.config/**` and
     `.python-version`. cubert moves shared mise settings to `.config/mise/`, and the
     Python version, such as `UV_PYTHON`, to `.python-version`.
   - Restore project privacy rules and commit policies in `AGENTS.md`. Reconcile them
     with the shared defaults: a single task ends with a suggested commit message, and
     agents commit only in Batch mode or when asked. Delete a project rule that a shared
     rule replaces, such as one that limits `fnox exec --no-redact` to one file. Two
     rules for one action disagree.
   - `wt.toml` hooks become `.worktreeinclude`, `.worktreelinks` and the `install` task.
     Project commit guidance, such as area scopes, goes at the end of `template-append`.
   - yamllint relaxations go in the project's `.yamllint`, which extends
     `.config/yamllint.yaml`.
   - Delete an old config that a template file replaces, such as `.dclintrc` next to
     `.dclintrc.yaml`.
4. Copier kept the project-owned files that already existed: `mise.toml`, `hk.pkl`,
   `dprint.json`, `LICENSE` and the others in
   [conventions.md](../template/docs/conventions.md#file-ownership). Render a fresh copy
   and merge it into each one by hand:

   ```console
   $ mise x pypi:copier -- copier copy --defaults --data-file .copier-answers.yml \
       gh:pawelad/cubert /tmp/cubert-fresh
   ```

   The project `hk.pkl` must amend `.config/hk/cubert.pkl`, `dprint.json` must extend
   `.config/dprint.json`, and `.yamllint` must extend `.config/yamllint.yaml`. The
   `python` option expects `pyproject.toml` at the root. A monorepo with Python in a
   subdirectory answers `false` and keeps its own ruff and mypy steps in `hk.pkl`. Leave
   the tool list in `mise.toml` alone: `mise run setup` adds the tools that cubert needs
   and raises an hk pin that is too old. A changelog project copies the `cliff.toml`
   header, `postprocessors`, `link_parsers` and the `entry` macro from the fresh copy.
   `--prepend` then still finds the header after the reformat, and entries link their
   PRs.
5. Move what cubert now owns out of the project files: the `postinstall` hook, the
   `[settings]` and `[env]` entries that `.config/mise/config.toml` already sets, and
   duplicate hk steps. Move project files out of `.config/`, such as check scripts in
   `.config/hk/checks/`, to `scripts/`: the ruff and mypy steps skip `.config/**`. Split
   a project `check` or `test` task into `check:<area>` and `test:<area>` tasks. Turn
   shell scripts into file tasks in `mise-tasks/`, unless tests cover them. A release
   script becomes the shared `release` task, with its version edits in `release:bump`
   and any step after the push in `release:publish`. Keep install and type-check
   prerequisites, such as Expo route generation. OpenTofu validation runs through
   `check:opentofu`; keep a project hook when validation must also run before commits
   and pushes. Preserve credential isolation and state backups. Move Ansible playbooks
   into `<ansible_dir>/playbooks/`, where the hooks check them. Delete the project's own
   `init`, `plan` and `apply` tasks, and their root wrappers: the shared `opentofu:`
   tasks replace them. With `secrets_provider: none`, keep `.env` in the OpenTofu
   directory, and load it from `<opentofu_dir>/mise.toml`. With fnox, list each value in
   `<opentofu_dir>/fnox.toml`, then delete `.env`, `.env.example` and the `.env` line in
   `.worktreelinks`. A project that already copies its state from R2 to B2 answers
   `opentofu_state_backup`. It then deletes its own backup workflow and script, and
   keeps its OpenTofu resources. Check them against
   [OpenTofu state backup](../template/docs/conventions.md#opentofu-state-backup).
6. Exclude generated and vendored data from `dprint.json`. Run `mise trust` and
   `mise run setup`, which pins tools in `mise.toml` and `mise.lock`. Commit steps 2 to
   6 with `HK=0 git commit`. The new hooks reject the old formatting, which the next
   commit fixes. Then run `mise run format --all`, and commit the reformat alone. Blame
   skips that commit, so it must hold no other change. Add its hash to
   `.git-blame-ignore-revs` in a third commit. Before you commit the reformat, review
   it:
   - dprint trims a trailing space inside a Markdown code span, so `` `] ` `` becomes
     `` `]` ``. Find each changed span with
     ``git diff --word-diff -- '*.md' | grep '`'``. Write such a value in a code block
     instead.
   - YAML reads an unquoted `{{VAR}}` placeholder as a flow mapping, and dprint rewrites
     it to `{ { VAR } }`. A tool that substitutes the text before it parses the file
     then breaks. Quote each placeholder before the reformat.
   - dprint wraps a long flow mapping across lines, and yamllint can reject the result.
     Write it as a block mapping.
   - Parse each changed YAML file before and after the reformat, and compare the data.
   - dprint keeps a line break inside a code span. Join the span by hand, so a search
     for its text finds it.
7. Fix what `mise run ci:check` and `mise run audit` report, then commit. The project's
   own workflows meet zizmor here for the first time, often with unpinned actions,
   persisted credentials and template injection. Run `zizmor --fix=safe .github`, and
   review its edits. Fix the rest by hand, or end a line with a
   `# zizmor: ignore[<rule>]` comment, with the reason above it. Exercise application
   jobs and deployment gates before merging the adoption. A step that needs a secret
   fails in CI too. An Ansible vault password file is the exception: `ci:check` supplies
   a throwaway one.

## Rebasing pre-reformat branches

A branch that forks before the reformat commit conflicts with it when rebased directly
onto `main`. Replay the branch onto the adoption commit before the reformat, format only
the files each commit touches, then rebase onto `main`:

1. Keep a backup ref before you start:

   ```console
   $ git branch <branch>-pre-cubert <branch>
   ```

2. Save a scoped exec script, such as `tmp/rebase_format.sh`, and mark it executable.
   Plain `mise run format --all` would also rewrite untouched files whose post-reformat
   fixes live on `main` (such as quoted YAML placeholders):

   ```bash
   #!/usr/bin/env bash
   # Rebase exec: reformat only the files this commit touches, then amend.
   # No -e: check-only hk steps can exit non-zero after the formatters finish.
   set -uo pipefail
   export GIT_LITERAL_PATHSPECS=1
   mise run format --all >/dev/null
   while IFS= read -r -d '' f; do
     git diff --quiet HEAD~1 HEAD -- "$f" && git checkout -q HEAD -- "$f"
   done < <(git diff -z --name-only)
   git commit -q -a --amend --no-edit --no-verify
   ```

3. Replay the branch onto the commit before the reformat, which has the new formatter
   configs, then rebase onto `main`. The reformat SHA is the one in
   `.git-blame-ignore-revs`:

   ```console
   $ git rebase <reformat-sha>~1 --exec tmp/rebase_format.sh
   $ git rebase main
   ```

   Read the exec output: a formatter error there leaves that commit partly formatted. A
   commit can still conflict on a file that an earlier exec reformatted. Take the
   commit's side with `git checkout --theirs -- <file>`, then `git add` it and run
   `git rebase --continue`. The exec after that commit formats the file again.

4. Run `mise run format`, in case `main` changed a formatter since the reformat. Commit
   any change. Then run `mise run check` and `mise run test`, and delete
   `<branch>-pre-cubert`.
