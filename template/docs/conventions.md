# Conventions

This project uses the [cubert](https://github.com/pawelad/cubert) template. This file
belongs to the template: change it in cubert, not here. Project setup lives in
[setup.md](./setup.md).

## File ownership

| Kind           | Files                                                                                                                                                                                                          | On `copier update`            |
| -------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| Template-owned | `.config/`, `.editorconfig`, `.yamllint`, `.shellcheckrc`, `.dclintrc.yaml`, `.github/actions/setup-mise/`, `.github/workflows/pr-title.yml`, `.github/CODEOWNERS`, `docs/conventions.md`, `openspec/schemas/` | Replaced by the new version   |
| Merged         | `AGENTS.md`, `README.md`, `docs/README.md`, `.gitignore`, `.git-blame-ignore-revs`, `.github/dependabot.yml`, `.github/workflows/ci.yml`, `openspec/config.yaml`                                               | 3-way merge, conflicts inline |
| Project-owned  | `mise.toml`, `hk.pkl`, `dprint.json`, `mise-tasks/`, `.worktreeinclude`, `.worktreelinks`, `docs/setup.md`, `LICENSE`, `CONTRIBUTING.md`                                                                       | Created once, never changed   |

Do not edit a template-owned file in a project: the next update conflicts with the edit.
Each project-owned file layers on its template-owned file, so a project change goes
there:

| Tool   | Template-owned                       | Project-owned | How the project file layers               |
| ------ | ------------------------------------ | ------------- | ----------------------------------------- |
| mise   | `.config/mise/config.toml`, `tasks/` | `mise.toml`   | mise loads both; `mise.toml` wins         |
| hk     | `.config/hk/cubert.pkl`, `base.pkl`  | `hk.pkl`      | `hk.pkl` amends `cubert.pkl`              |
| dprint | `.config/dprint.json`                | `dprint.json` | `dprint.json` extends it; excludes add up |

Copier deletes nothing. If you delete a project-owned file, the next update creates it
again.

## Tools

- mise is the source of truth for tool versions, on every machine and in CI. CI installs
  tools with `mise install`, not with setup actions.
- A Python CLI is a mise `pypi:` tool, which mise installs with uv. Do not run `uvx` or
  `pipx` directly.
- A project with `npm:` tools pins `node` in `mise.toml` too.
- A new project's `mise.toml` seeds `latest` (`lts` for Node). The first
  `mise run setup` pins each one to the newest release that `minimum_release_age`
  allows, so cubert holds no tool versions. Add a tool with `mise use --pin <tool>`.

## Tasks

`mise tasks` lists every task. Names follow `<area>:<verb>`, where the area is the noun
that the task acts on (`kif:deploy`, `tofu:init`). A wildcard then selects one area:
`mise run 'kif:*'`.

The shared tasks are file tasks in `.config/mise/tasks/`. mise names each one from its
path, so `check/repo` is `check:repo`:

| Task              | Does                                                                |
| ----------------- | ------------------------------------------------------------------- |
| `setup`           | Installs tools and git hooks, sets the blame config, runs `install` |
| `install`         | Nothing. The project replaces it with its dependency installs       |
| `check`           | Runs every `check:*` task                                           |
| `check:repo`      | Runs hk on every file, plus the repository guards                   |
| `format`          | Runs the hk fixers on changed files (`--all` for every file)        |
| `upgrade`         | Bumps the tools in `mise.toml` (`mise upgrade --bump`)              |
| `hooks:install`   | Installs the hk hooks and the `post-checkout` worktree hook         |
| `template:update` | Updates the template-owned and merged files from cubert             |
| `template:check`  | Fails if a newer cubert version exists                              |
| `worktree:setup`  | Sets up a new worktree once (see below)                             |
| `worktree:clean`  | Empties the worktrunk trash                                         |

To add a project check, add a `check:<area>` task. `check` runs it with no other change.

### Project tasks

- A short task is a TOML task in `mise.toml`.
- A task with logic, or with more than one line, is a file task in `mise-tasks/`. hk
  then runs shellcheck and shfmt on it. Header lines declare its metadata:
  `#MISE description="..."` and `#USAGE arg "<name>"`.
- File tasks run in the project root, from any directory.
- mise passes `#USAGE` args only as `usage_*` environment variables, not as `$@`.

### Overriding a shared task

A TOML task in `mise.toml` replaces a file task with the same name. Replace `install`
this way, or `setup` if the project needs more steps. A file task in `mise-tasks/` does
not replace a shared task: the `.config/mise/tasks/` file wins.

mise runs only one `postinstall` hook, and the hook in `.config/mise/config.toml` wins.
Put project install steps in the `install` task.

### Scripts

Pick the lightest tier that fits:

1. **Bash**: a short sequence of CLI calls with no data processing.
2. **Standalone Python** (`uv run --script`, PEP 723 inline dependencies): parsing, API
   calls or real branching.

`scripts/` holds only code that is not a task: check scripts that hk calls with
`{{files}}`, modules with tests, and git hook shims.

## Git hooks

hk runs the git hooks (`pre-commit`, `pre-push`, `commit-msg`). The shared steps are in
`.config/hk/base.pkl` (every project) and `.config/hk/cubert.pkl` (the steps for the
enabled features). `hk.pkl` amends `cubert.pkl`:

- Change a shared step: `steps { ["dprint"] { exclude = List("gen/**") } }`.
- Turn a shared step off: `skip_steps = List("file-length")`.
- Add a step: `steps { ["name"] = new Step { ... } }`.

The hk package version is pinned only in `base.pkl`.

`check:repo` fails when a local `core.hooksPath` is set. Git then ignores the global
config-based hooks that `hk install --global` writes, with no error. Fix it with
`git config --local --unset core.hooksPath`.

## Formatting

dprint formats Markdown, TOML, JSON and YAML. Markdown wraps at 88 columns, the Black
and ruff default. yamllint requires double-quoted strings. The hk builtins check
trailing whitespace, final newlines and line endings from `.editorconfig`.

A commit that only reformats code goes in `.git-blame-ignore-revs`. GitHub reads that
file, and `mise run setup` sets `blame.ignoreRevsFile` for local blame.

## Worktrees

Every way to create a worktree runs `mise run worktree:setup`:

- `wt switch --create` runs it from the `[pre-start]` hook in `.config/wt.toml`.
- Plain `git worktree add`, and agent tools that use it (Superset, Jean, herdr, Orca),
  fire the `post-checkout` hook, which runs it.

`worktree:setup` exits in the primary checkout. In a new worktree it:

1. Copies the gitignored files listed in `.worktreeinclude` (default `.env`).
2. Links `tmp/` and the agent dirs (`.claude`, `.codex`, ...) to the primary checkout,
   so agent output outlives the worktree.
3. Links each path in `.worktreelinks` to the primary checkout. Use it for operator
   credentials, which are the same on every branch.
4. Runs `mise run install`.
5. Writes the marker `cubert-worktree-setup-done` in the worktree's git dir.

Notes:

- The marker makes setup run once. The `post-checkout` all-zero ref does not work: Orca
  pre-warms detached worktrees and finalizes them later with a plain `git checkout`.
- The hook is a script in the hooks dir, not a config-based hook. GUI apps on macOS run
  Apple Git, which has no config-based hooks.
- A real directory blocks its link. Move its contents to the primary checkout, then run
  `mise run worktree:setup --force`.

## Upgrades

- `mise run upgrade` bumps the tools in `mise.toml`.
- Dependabot bumps GitHub Actions and the package ecosystems monthly. It has no
  ecosystem for `mise.toml`.
- mise skips releases younger than 7 days (`minimum_release_age`), which matches the
  Dependabot cooldown. Installs from `mise.lock` and exact pins are not filtered.
- The dprint plugin versions belong to the template. cubert bumps them.

## Template updates

`mise run template:update` runs `copier update` from the latest cubert tag. It needs a
clean tree, keeps your earlier answers, and stops with a list of files that have
conflict markers. Resolve them, run `mise run setup` (the update can change tools and
hooks) and `mise run check`, then commit the result as one commit.

Run Copier only through this task. Copier commits in temporary repos, and global hk
hooks there drop `mise.lock` from the update. The task runs Copier with `HK=0`.
