# Adopt cubert in an existing repository

These steps bring an existing repository onto cubert. A new project follows
[Start a new project](../README.md#start-a-new-project) instead.

Copy from GitHub, not from a local clone. Copier records the source in
`.copier-answers.yml`, and a local path breaks updates on other machines.

1. Start on a clean branch.
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
     application jobs, image scans and deployment gates. Override `ci:check` when those
     jobs already run the application suites.
   - Restore project privacy rules and commit policies in `AGENTS.md`. Reconcile them
     with the shared defaults, which permit automatic commits for a single task.
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
   duplicate hk steps. Split a project `check` or `test` task into `check:<area>` and
   `test:<area>` tasks. Turn shell scripts into file tasks in `mise-tasks/`, unless
   tests cover them. A release script becomes the shared `release` task, with its
   version edits in `release:bump` and any step after the push in `release:publish`.
   Keep install and type-check prerequisites, such as Expo route generation. OpenTofu
   validation runs through `check:opentofu`; keep a project hook when validation must
   also run before commits and pushes. Preserve credential isolation and state backups.
   Delete the project's own `init`, `plan` and `apply` tasks, and their root wrappers:
   the shared `opentofu:` tasks replace them. With `secrets_provider: none`, keep `.env`
   in the OpenTofu directory, and load it from `<opentofu_dir>/mise.toml`. With fnox,
   list each value in `<opentofu_dir>/fnox.toml`, then delete `.env`, `.env.example` and
   the `.env` line in `.worktreelinks`. A project that already copies its state from R2
   to B2 answers `opentofu_state_backup`. It then deletes its own backup workflow and
   script, and keeps its OpenTofu resources. Check them against
   [OpenTofu state backup](../template/docs/conventions.md#opentofu-state-backup).
6. Exclude generated and vendored data from `dprint.json`. Then run `mise trust`,
   `mise run setup` and `mise run format --all`. Commit the reformat alone, and add its
   hash to `.git-blame-ignore-revs`.
7. Fix what `mise run ci:check` and `mise run audit` report, then commit. Exercise
   application jobs and deployment gates before merging the adoption. A step that needs
   a secret, such as an Ansible vault password, fails in CI too.
