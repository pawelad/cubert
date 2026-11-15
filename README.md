# cubert

A [Copier] template for my projects. It ships the tooling that every repository shares,
so a fix lands once in cubert and reaches each project with `mise run template:update`.

## What a project gets

- [mise] for every tool version and task, on every machine and in CI. A new project
  starts with the newest releases that are at least 7 days old.
- [hk] git hooks: formatting, linting, pinned versions, prose rules and Conventional
  Commits.
- [dprint] for Markdown, TOML, JSON and YAML, plus yamllint, shellcheck, shfmt,
  jactionlint and zizmor.
- Spell checking with typos, secret scanning with betterleaks and an offline link check
  with lychee, all in the git hooks.
- `mise run audit` and a weekly CI job: known vulnerabilities in `uv.lock` and
  `bun.lock` (osv-scanner), zizmor's online audits of the GitHub Actions, and online
  links. They need the network, so hooks skip them.
- An `AGENTS.md` with shared rules for coding agents, and a section for project rules.
- Worktree setup that runs once for `wt switch --create`, plain `git worktree add` and
  the agent apps built on it.
- GitHub Actions CI, a PR title check and Dependabot.
- Optional features: Python, TypeScript with Bun, Docker, OpenTofu, Ansible, OpenSpec
  and a git-cliff changelog.

[`template/docs/conventions.md`](./template/docs/conventions.md) describes the shared
tooling in detail. Every project gets that file as `docs/conventions.md`.

## Requirements

- [mise]. It installs Copier and every other tool.
- Git.

## Start a new project

```console
$ mise x pypi:copier -- copier copy gh:pawelad/cubert my-project
$ cd my-project
$ git init
$ mise trust
$ mise run setup
$ git add --all
$ mise run check
$ git commit -m "chore: start from the cubert template"
```

Copier asks these questions:

| Question                                                                  | Default           |
| ------------------------------------------------------------------------- | ----------------- |
| `project_name`, `description`                                             | none              |
| `github_owner`                                                            | `pawelad`         |
| `license`: `MPL-2.0` or all rights reserved                               | `MPL-2.0`         |
| `copyright_year`, for all rights reserved                                 | `2026`            |
| `python`, `docker`, `opentofu` (`tofu_dir`), `ansible` (`ansible_dir`)    | `false`           |
| `typescript` (`typescript_dirs`, a list of directories with package.json) | `false` (`["."]`) |
| `openspec`: `none`, `changes-only` or `spec-driven`                       | `changes-only`    |
| `changelog`                                                               | `false`           |

`mise run setup` pins the seeded `latest` tool versions in `mise.toml`, so commit
`mise.toml`, `mise.lock` and `.mise/locks/` after it.

Feature directories stay inside the project. Their names use ASCII letters, numbers,
periods, underscores, hyphens and slashes. The first path component cannot start with a
hyphen. Copier rejects unsupported paths before rendering.

## Update a project

```console
$ mise run template:check    # exits 2 if a newer cubert tag exists
$ mise run template:update   # updates to the latest tag
```

`template:update` needs a clean tree. It keeps your answers and lists every file with a
conflict. Resolve them, run `mise run setup` and `mise run check`, then commit the
update as one commit.

## Adopt cubert in an existing repository

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
     `cubert-audit.yml` (see [conventions.md](./template/docs/conventions.md#ci)).
   - `wt.toml` hooks become `.worktreeinclude`, `.worktreelinks` and the `install` task.
   - yamllint relaxations go in the project's `.yamllint`, which extends
     `.config/yamllint.yaml`.
   - Delete an old config that a template file replaces, such as `.dclintrc` next to
     `.dclintrc.yaml`.
4. Copier kept the project-owned files that already existed: `mise.toml`, `hk.pkl`,
   `dprint.json`, `LICENSE` and the others in
   [conventions.md](./template/docs/conventions.md#file-ownership). Render a fresh copy
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
6. Exclude generated and vendored data from `dprint.json`. Then run `mise trust`,
   `mise run setup` and `mise run format --all`. Commit the reformat alone, and add its
   hash to `.git-blame-ignore-revs`.
7. Fix what `mise run check` reports, then commit. A step that needs a secret, such as
   an Ansible vault password, fails in CI too.

## Development

See [docs/development.md](./docs/development.md).

## Authors

Developed and maintained by [Paweł Adamczak][author].

Released under the [Mozilla Public License 2.0][license].

[author]: https://pawelad.me/
[copier]: https://copier.readthedocs.io/en/stable/
[dprint]: https://dprint.dev/
[hk]: https://hk.jdx.dev/
[license]: ./LICENSE
[mise]: https://mise.jdx.dev/
