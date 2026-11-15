# Conventions

This project uses the [cubert](https://github.com/pawelad/cubert) template. This file
belongs to the template: change it in cubert, not here. Project setup lives in
[setup.md](./setup.md).

## File ownership

| Kind           | Files                                                                                                                                                                                                                                                                                                                                                                                                         | On `copier update`            |
| -------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| Template-owned | `.config/`, `.editorconfig`, `.shellcheckrc`, `.dclintrc.yaml`, `.github/actions/setup-mise/`, `.github/workflows/cubert-check.yml`, `.github/workflows/cubert-audit.yml`, `.github/workflows/pr-title.yml`, `.github/zizmor.yml`, `.github/CODEOWNERS`, `docs/conventions.md`, `openspec/schemas/`                                                                                                           | Takes the template's changes  |
| Merged         | `AGENTS.md`, `README.md`, `docs/README.md`, `.gitignore`, `.git-blame-ignore-revs`, `.github/dependabot.yml`, `openspec/config.yaml`                                                                                                                                                                                                                                                                          | Merges your additions         |
| Project-owned  | `mise.toml`, `hk.pkl`, `dprint.json`, `.yamllint`, `biome.json`, `mise-tasks/`, `.github/workflows/ci.yml`, `.github/workflows/audit.yml`, `.worktreeinclude`, `.worktreelinks`, `docs/setup.md`, `LICENSE`, `CONTRIBUTING.md`, `pyproject.toml`, `.python-version`, `cliff.toml`, `CHANGELOG.md`, `<tofu_dir>/versions.tf`, `<ansible_dir>/.gitkeep`, `openspec/changes/.gitkeep`, `openspec/specs/.gitkeep` | Created once, then left alone |

Copier treats template-owned and merged files the same way: a 3-way merge of the
template's change and your edit. The kinds differ in how you edit them. A change to a
template-owned file overlaps the template's own lines, so the next update conflicts with
it. Add to a merged file below the shared part, and the merge stays clean.

Each project-owned file layers on its template-owned file, so a project change goes
there:

| Tool     | Template-owned                       | Project-owned | How the project file layers               |
| -------- | ------------------------------------ | ------------- | ----------------------------------------- |
| mise     | `.config/mise/config.toml`, `tasks/` | `mise.toml`   | mise loads both; `mise.toml` wins         |
| hk       | `.config/hk/cubert.pkl`, `base.pkl`  | `hk.pkl`      | `hk.pkl` amends `cubert.pkl`              |
| dprint   | `.config/dprint.json`                | `dprint.json` | `dprint.json` extends it; excludes add up |
| Biome    | `.config/biome.json`                 | `biome.json`  | `biome.json` extends it (`typescript`)    |
| yamllint | `.config/yamllint.yaml`              | `.yamllint`   | `.yamllint` extends it; `ignore` replaces |

What an update does to a missing or removed file:

- A project-owned file that you delete comes back, with the new template's content.
- A template-owned or merged file that you delete stays deleted.
- A file that the new template drops is deleted, even if you edited it.

## Tools

- mise is the source of truth for tool versions, on every machine and in CI. CI installs
  tools with `mise install`, not with setup actions.
- `min_version` in `.config/mise/config.toml` pins mise itself. CI installs exactly that
  release. An older local mise stops and prints how to upgrade.
- A Python CLI is a mise `pypi:` tool, which mise installs with uv. Do not run `uvx` or
  `pipx` directly.
- Python CLI tools select a private Python 3.14 runtime through their `python` option.
  mise installs it before the tools and limits their graphs to that Python line. The
  application's `.python-version` stays independent. This Python line is the one version
  cubert holds: CLI wheels lag a new line. A cubert release moves it in
  `.config/mise/required-tools`, and `setup` then updates each tool's option.
- A project with `npm:` tools pins `node` in `mise.toml` too.
- The `typescript` option seeds `bun`, `biome` and `npm:typescript` (the `tsc`
  compiler). Bun runs the tests and installs packages. The project does not list
  `typescript` in `package.json`.
- A GitHub Action is pinned to a commit SHA, with its version in a comment:
  `uses: "actions/checkout@<sha>" # v7.0.1`. A tag can move, and a SHA cannot.
  Dependabot updates both. zizmor enforces the pin and audits workflows for injection
  and credential leaks. jactionlint checks workflow syntax, with its `correctness`
  profile, so the two tools never report the same finding.
- An action or reusable workflow in the same repository uses `$/`, such as
  `uses: "$/.github/actions/setup-mise"`. Unlike `./`, it always loads the running
  commit, never a file that an earlier step wrote.
- mise calls the GitHub API to resolve and lock tools. GitHub limits calls without a
  token. With `gh` logged in, run
  `mise settings set github.credential_command "gh auth token"` once per machine. mise
  ignores this setting in a project's config. `audit:actions` and `audit:links` use the
  `gh` token too.
- A new project's `mise.toml` seeds `latest` (`lts` for Node). The first
  `mise run setup` pins each one to the newest release that `minimum_release_age`
  allows, so cubert holds no tool versions except that Python line. Add a tool with
  `mise use --pin <tool>`.
- The `pins` check requires each request to match its version in `mise.lock`. A dotted
  prefix such as `node = "24.22"` fails when it locks `24.22.2`.
- Commit `.mise/locks/` with `mise.lock`. The `lockfile` check verifies native npm and
  Python dependency graphs and their digests, even when tools are already installed.
  `check:repo` also verifies them after edits that change only a graph.

## Tasks

`mise tasks` lists every task. Names follow `<area>:<verb>`, where the area is the noun
that the task acts on (`kif:deploy`, `tofu:init`). A wildcard then selects one area:
`mise run 'kif:*'`.

The shared tasks are file tasks in `.config/mise/tasks/`. mise names each one from its
path, so `check/repo` is `check:repo`:

| Task                 | Does                                                                     |
| -------------------- | ------------------------------------------------------------------------ |
| `setup`              | Adds and pins tools, installs them and the git hooks, runs `install`     |
| `install`            | Nothing. The project replaces it with its dependency installs            |
| `check`              | Runs every `check:*` task                                                |
| `check:repo`         | Runs hk on every file, plus the repository guards                        |
| `check:opentofu`     | OpenTofu option: runs `tofu validate`, with no backend or credentials    |
| `tofu:lock`          | OpenTofu option: locks the providers for macOS and Linux (`--upgrade`)   |
| `ci:check`           | Runs `install`, `check`, then `test`: the CI check job                   |
| `audit`              | Runs every `audit:*` task. Needs the network, so `check` skips it        |
| `audit:actions`      | Runs zizmor's online audits, such as actions with known vulnerabilities  |
| `audit:deps`         | Scans `uv.lock` and `bun.lock` for known vulnerabilities                 |
| `audit:links`        | Checks every link in the Markdown files, URLs included                   |
| `skills:update`      | OpenSpec option: updates the installed agent skills (`openspec update`)  |
| `test`               | Runs every `test:*` task                                                 |
| `test:python`        | Python option: runs `uv run pytest` on the given files, or all tests     |
| `test:typescript`    | TypeScript option: runs each directory's test script, or `bun test`      |
| `typescript:install` | TypeScript option: runs `bun install` in each directory                  |
| `release`            | Changelog option: changelog, commit and tag, then push after you confirm |
| `release:preview`    | Changelog option: prints the entries since the last release tag          |
| `format`             | Runs the hk fixers on changed files (`--all` for every file)             |
| `clean`              | Runs every `<area>:clean` task, `worktree:clean` among them              |
| `upgrade`            | Bumps the tools in `mise.toml` (`mise upgrade --bump`)                   |
| `hooks:install`      | Installs the hk hooks and the `post-checkout` worktree hook              |
| `template:update`    | Updates the template-owned and merged files from cubert                  |
| `template:check`     | Fails if a newer cubert version exists                                   |
| `worktree:setup`     | Sets up a new worktree once (see below)                                  |
| `worktree:clean`     | Empties the worktrunk trash                                              |

To add a project check, add a `check:<area>` task. `check` runs it with no other change.
To add a test suite, add a `test:<area>` task. `test` runs it, and so does CI. Let it
take test file paths (`#USAGE arg "[files]..."`), so a run can cover only the touched
files.

The `opentofu` option adds `check:opentofu` and `tofu:init`. `setup` and worktree setup
never run `tofu:init`, because it contacts the state backend and needs the operator's
login. `check:opentofu` validates with `init -backend=false` in its own data directory
(`.terraform-validate`), so it needs no credentials and leaves the real `.terraform`
alone. Run `mise run tofu:init` once per checkout before a plan or apply.

`check:opentofu` never changes `.terraform.lock.hcl`, and it fails when the lock file
lacks a provider. `mise run tofu:lock` then adds the hashes for macOS and Linux, with no
backend login. After a version constraint change, run `mise run tofu:lock --upgrade`.
`tofu init` would lock only the local platform, and CI would change the file. The
OpenTofu tasks create the configured provider cache before invoking OpenTofu. An
existing project's own `tofu:init` task must create `TF_PLUGIN_CACHE_DIR` too.
`.config/mise/config.toml` sets `TF_PLUGIN_CACHE_DIR`, so each worktree reuses the
providers that another one downloaded.

Ansible syntax checks discover nested playbooks. They exclude directories named `tasks`,
`handlers`, `vars`, `group_vars`, `host_vars`, `roles`, `templates` and `files`. Those
directories hold task fragments, variables and assets rather than playbook entrypoints.
Keep playbook entrypoints outside them.

The `ansible-template` hook parses changed `.j2` files with a custom ansible-lint rule.
It uses the existing Jinja installation, Ansible's configured extensions and `#jinja2:`
delimiter overrides. It does not render values or resolve filters, so syntax checks need
no runtime variables. A passing parse does not prove that a deployment will succeed.

The `python` option adds `test:python`. It runs `uv run pytest` and treats pytest's exit
code 5 (no tests collected) as a pass, so a fresh project passes `mise run test`. A
project without pytest in its dev group skips with a message. Add it with
`uv add --dev pytest`.

The `typescript` option asks for `typescript_dirs`: the directories that hold a
`package.json`, `["."]` by default. A monorepo lists each one. Paths stay inside the
project and use ASCII letters, numbers, periods, underscores, hyphens and slashes. The
first path component cannot start with a hyphen. Internal names such as `apps/-x` are
accepted. Copier rejects other names before rendering, because task file arguments split
on spaces. `typescript:install` and `test:typescript` loop over them and skip a
directory without `package.json`. Dependabot gets the same list. `test:typescript` runs
the `test` script of a `package.json` that has one, such as Jest or Vitest. Otherwise it
runs `bun test`, which passes when it finds no tests. Given file paths, it runs only the
directories that hold them. Redundant `/` separators and `.` components are normalized
in directory names and selected file paths. A selection outside every configured package
fails with a message. A test file that imports `bun:test` needs
`bun add --dev @types/bun` for `tsc`.

The `changelog` option adds git-cliff, `cliff.toml`, `CHANGELOG.md`, `release` and
`release:preview`. `release X.Y.Z` runs from a clean `main` that matches `origin/main`.
It needs `gh` with a login and a passing CI run on that commit. `--no-push` skips both
and keeps the commit and tag local. The first release has no earlier version to compare
with, so its section reads "Initial release." Each later section lists the commits since
the previous tag.

A project adds release steps with two optional tasks in `mise.toml`. Each task declares
its argument, and reads it from the matching `usage_` variable:

- `release:bump` (`arg "<version>"`, `$usage_version`) runs before the changelog, with
  the version without the `v`. It edits the version files. The release commit takes
  every tracked file that it changed. An untracked file stops the release.
- `release:publish` (`arg "<tag>"`, `$usage_tag`) runs after the push, with the tag,
  such as `v1.2.0`. It replaces the GitHub Release that `release` creates by default.
  Define it when a tag workflow deploys and publishes, and point it at that run.

Each entry links its pull request when the subject ends in `(#N)`, as a GitHub squash
merge writes it. Otherwise it links the commit. `cliff.toml` holds the repository URL
from the `github_owner` and `project_name` answers.

git-cliff pipes its output through dprint, so the changelog keeps the 88-column limit.
Keep the `cliff.toml` header as dprint wraps it. `--prepend` keeps one header only when
the file starts with the exact header text.

`areas` in `cliff.toml` lists the scopes that users see, such as `map` or `spots`, in
display order. Each changelog group then lists its entries by area, and the rest under
Other. With areas, the `changelog-scope` commit hook and the PR title job reject a
`feat`, `fix`, `perf` or breaking commit without an area scope or a tooling scope. A
breaking commit has a `!` or a `BREAKING CHANGE:` footer, of any type. The tooling
scopes are the ones that the `commit_parsers` skip. An empty list, the default, checks
nothing.

### Project tasks

- A short task is a TOML task in `mise.toml`.
- A task with logic, or with more than one line, is a file task in `mise-tasks/`. hk
  then runs shellcheck and shfmt on it. Header lines declare its metadata:
  `#MISE description="..."` and `#USAGE arg "<name>"`.
- File tasks run in the project root, from any directory.
- mise passes `#USAGE` args only as `usage_*` environment variables, not as `$@`.

### Overriding a shared task

A TOML task in `mise.toml` merges with the file task of the same name. Each field that
the TOML task sets wins, and the rest come from the file. Give an override its own
`run`: an override with only `depends` still runs the shared body after them. Replace
`install` this way, or `setup` if the project needs more steps. A file task in
`mise-tasks/` does not replace a shared task: the `.config/mise/tasks/` file wins.

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
- Import the hk builtins under a name of your own:
  `import "package://.../Builtins.pkl" as hkb`. hk's evaluator cannot resolve a second
  import named `Builtins`, and `base.pkl` already has one.
- hk 2.11.1 rejects a `Group` in `steps`. Give each step its own `dir` instead.

The hk package version is pinned only in `base.pkl`.

The prose rules (American English, no em dashes, no emojis) check Markdown and text
files in full. In code and config files they check comment lines only, and a fixer
rewrites only a comment. A string, an identifier or a config value can name an external
API or hold a fixture, so the rules leave it alone. Paths named `fixtures`, `testdata`,
`__snapshots__`, `generated` and `vendor` are skipped, by the smart-quotes fixer too.
Skip another path with
`steps { ["no-british-english"] { exclude = List("docs/legacy/**") } }`.

The `openspec` step runs `openspec validate --all --strict`. With `spec-driven`, an
`[INFO]` or `[WARNING]` line fails it too, such as a requirement over 500 characters.
`changes-only` changes always print an `[INFO]` line, so only the exit code counts
there.

Three hk steps cover what the formatters and linters miss:

- `typos` checks spelling in text files, and the prose rules keep American English. It
  only reports, with no fixer, so a false positive is never rewritten. A project adds
  words in a root `typos.toml`, which layers on `.config/typos.toml`. A line that ends
  in a `spellchecker:disable-line` comment is skipped.
- `betterleaks` scans for tokens, passwords and keys. A false positive gets a
  `betterleaks:allow` comment on the line, or a fingerprint in `.betterleaksignore`.
- `lychee` runs with `--offline`, so it checks relative links in Markdown only. A
  project excludes paths or URLs in a root `lychee.toml`, which layers on
  `.config/lychee.toml`.

`check:repo` fails when a local `core.hooksPath` is set. Git then ignores the global
config-based hooks that `hk install --global` writes, with no error. Fix it with
`git config --local --unset core.hooksPath`.

## CI

The template owns the shared jobs, and the project owns every trigger. Triggers decide
how many CI minutes a project spends, so each project sets its own.

| Workflow           | Owner    | Does                                                         |
| ------------------ | -------- | ------------------------------------------------------------ |
| `cubert-check.yml` | Template | The `Check` job, `mise run ci:check`. Runs only when called  |
| `cubert-audit.yml` | Template | The `Audit` job, `mise run audit`. Runs only when called     |
| `ci.yml`           | Project  | Calls `cubert-check.yml` on pushes to main and pull requests |
| `audit.yml`        | Project  | Calls `cubert-audit.yml` on the same events and weekly       |
| `pr-title.yml`     | Template | Checks the pull request title                                |

- Add project jobs to `ci.yml` or to another workflow. Path filters, draft rules,
  concurrency and a `workflow_call` trigger for a deploy gate go there too.
- The weekly schedule is in `audit.yml`, so it does not start the CI jobs.
- A caller sets `permissions`. A called workflow can only narrow them.
- `ci:check` runs `install`, `check`, then `test`. When other jobs run the slow suites
  with their services, replace it in `mise.toml`:
  `[tasks."ci:check"] run = "mise run check:repo"`. Include `mise run install` in an
  override when its checks need project dependencies. `mise run ci:check` runs the same
  job locally.
- `ci:check` sets `UV_LOCKED=1`, so a stale `uv.lock` fails CI. Bun installs with
  `--frozen-lockfile` everywhere. An override sets `UV_LOCKED=1` itself.

## Audits

`mise run audit` runs the checks that need the network: osv-scanner on `uv.lock` and
`bun.lock`, zizmor's online audits, and lychee on every URL. The zizmor hk step runs
offline, so only the audit finds actions with known vulnerabilities, impostor commits
and version comments that do not match the pinned SHA. Hooks and `mise run check` skip
them, so they stay fast and work offline. A new advisory then fails the audit and never
an unrelated commit. CI runs it from `audit.yml`, on each push and pull request and once
a week. Run it locally before a release or after a dependency change. Every project gets
osv-scanner, because the Python tools also have `uv.lock` files in `.mise/locks/`. The
scan includes those files and application lockfiles, including nested backends.

## Formatting

dprint formats Markdown, TOML, JSON and YAML. yamllint requires double-quoted strings.
With the `typescript` option, Biome formats and lints JavaScript, TypeScript and CSS. It
does not format JSON, so dprint stays the only JSON formatter. The `biome` step covers
format, lint and import order, so there is no separate format step. hk runs `tsc` once
per nearest `tsconfig.json`, so a monorepo needs no setup. `mise run format` skips
`tsc`, which cannot fix anything. The hk builtins check trailing whitespace, final
newlines and line endings from `.editorconfig`.

Every file type has the same maximum line length: 88 columns, the Black and ruff
default. dprint wraps Markdown prose and formats the other files to it, and yamllint
fails a longer YAML line. Workflows and actions are exempt from yamllint's limit,
because an action pin keeps its version comment on the same line. ruff uses its default,
and `.editorconfig` sets `max_line_length` for editors. Set a new formatter to 88 too.

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
- An existing project hook stays in place. `hooks:install` writes `post-checkout.cubert`
  and prints the delegation command to add. `check:repo` accepts that command, with
  optional `exec`, when the delegated copy is executable and current.
- A real directory blocks its link. Move its contents to the primary checkout, then run
  `mise run worktree:setup --force`.

## Upgrades

- `mise run upgrade` bumps the tools in `mise.toml`.
- Dependabot bumps GitHub Actions and the package ecosystems monthly. It has no
  ecosystem for `mise.toml`.
- mise skips releases younger than 7 days (`minimum_release_age`), which matches the
  Dependabot cooldown. Installs from `mise.lock` and exact pins are not filtered.
- `typescript:install` passes `--minimum-release-age=604800` (7 days) to `bun install`.
  Bun reads `bunfig.toml` only from the working directory, so a flag covers every
  directory. Add a `bunfig.toml` with `[install] minimumReleaseAge = 604800` to a
  directory where you also run `bun add` or `bun update`.
- The dprint plugin versions belong to the template. cubert bumps them.

## Template updates

`mise run template:update` runs `copier update` from the latest cubert tag. It needs a
clean tree, keeps your earlier answers, and stops with a list of files that have
conflict markers. Resolve them, run `mise run setup` (the update can change tools and
hooks) and `mise run check`, then commit the result as one commit.

An update cannot add a tool to the project-owned `mise.toml`.
`.config/mise/required-tools` lists the tools that the shared steps and tasks call.
`mise run setup` adds each missing one to `mise.toml`, pinned. The `required-tools` hk
step fails until it does. A line such as `hk>=2.11.1` sets a minimum version: an older
hk cannot load the shared config, so setup raises the pin to the minimum and the step
names the tool when it is too old. Other pins above the minimum stay as they are. A line
such as `node@lts` adds a missing tool from that channel, as a new project seeds it. A
selector such as `yamllint[python=3.14]` also repairs the tool's private runtime without
changing its configured version. `setup` preserves other inline tool options.

Run Copier only through this task. Copier commits in temporary repos, and global hk
hooks there drop `mise.lock` from the update. The task runs Copier with `HK=0`.
