# cubert

_Every project's a clone. Unlike Cubert, they take updates._

A [Copier] template for my projects. It ships the tooling that every repository shares,
so a fix lands once in cubert and reaches each project with `mise run template:update`.

## What a project gets

| Area         | What it does                                                                                                             |
| ------------ | ------------------------------------------------------------------------------------------------------------------------ |
| Tools, tasks | [mise] pins every tool and runs every task, locally and in CI. A new project starts with releases at least 7 days old.   |
| Git hooks    | [hk] runs formatting, linting, pinned versions, prose rules and Conventional Commits.                                    |
| Formatting   | [dprint] formats Markdown, TOML, JSON and YAML.                                                                          |
| Linting      | [yamllint], [ShellCheck], [shfmt], [jactionlint] and [zizmor] check YAML, shell and GitHub Actions.                      |
| Hygiene      | [typos] checks spelling, [betterleaks] scans for secrets and [lychee] checks links offline, all in the git hooks.        |
| Audits       | `mise run audit` and a weekly CI job: [osv-scanner] for `uv.lock` and `bun.lock`, zizmor online audits and online links. |
| Agents       | An `AGENTS.md` with shared rules for coding agents, and a section for project rules.                                     |
| Worktrees    | Setup that runs once for [Worktrunk], plain `git worktree add` and the agent apps built on it.                           |
| CI           | GitHub Actions CI, a PR title check and [Dependabot].                                                                    |
| Optional     | [Python], TypeScript with [Bun], [Docker], [OpenTofu], [Ansible], [OpenSpec] and a [git-cliff] changelog.                |

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

| Question                                                                   | Default           |
| -------------------------------------------------------------------------- | ----------------- |
| `project_name`, `description`                                              | none              |
| `github_owner`                                                             | `pawelad`         |
| `license`: `MPL-2.0` or all rights reserved                                | `MPL-2.0`         |
| `copyright_year`, for all rights reserved                                  | none              |
| `python`, `docker`, `opentofu` (`opentofu_dir`), `ansible` (`ansible_dir`) | `false`           |
| `opentofu_state_backup` (`opentofu_state_bucket`), for `opentofu`          | `false`           |
| `secrets_provider`, for `opentofu`: `proton-pass`, `age` or `none`         | `none`            |
| `secrets_vault`, for `proton-pass`; `secrets_age_recipient`, for `age`     | none              |
| `typescript` (`typescript_dirs`, a list of directories with package.json)  | `false` (`["."]`) |
| `openspec`: `none`, `changes-only` or `spec-driven`                        | `changes-only`    |
| `changelog`                                                                | `false`           |

`mise run setup` pins the seeded `latest` tool versions in `mise.toml`, so commit
`mise.toml`, `mise.lock` and `.mise/locks/` after it.

Feature directories stay inside the project. Their names use ASCII letters, numbers,
periods, underscores, hyphens and slashes. Write a path as `infra/opentofu`, with no
`./`, `..`, trailing or double slash, or leading hyphen. Copier rejects other paths
before rendering.

## Update a project

```console
$ mise run template:check    # exits 2 if a newer cubert tag exists
$ mise run template:update   # updates to the latest tag
```

`template:update` needs a clean tree. It keeps your answers and lists every file with a
conflict. `-d <question>=<answer>` changes one answer, such as `-d changelog=true`.
Resolve them, run `mise run setup` and `mise run check`, then commit the update as one
commit.

## Adopt cubert in an existing repository

Copy over the existing files, then merge the project's content back by hand. See
[docs/adoption.md](./docs/adoption.md) for the steps.

## Development

See [docs/development.md](./docs/development.md).

## Authors

Developed and maintained by [Paweł Adamczak][author].

Released under the [Mozilla Public License 2.0][license].

[ansible]: https://docs.ansible.com/
[author]: https://pawelad.me/
[betterleaks]: https://github.com/betterleaks/betterleaks
[bun]: https://bun.sh/
[copier]: https://copier.readthedocs.io/en/stable/
[dependabot]: https://docs.github.com/en/code-security/dependabot
[docker]: https://www.docker.com/
[dprint]: https://dprint.dev/
[git-cliff]: https://git-cliff.org/
[hk]: https://hk.jdx.dev/
[jactionlint]: https://github.com/jdx/jactionlint
[license]: ./LICENSE
[lychee]: https://lychee.cli.rs/
[mise]: https://mise.jdx.dev/
[opentofu]: https://opentofu.org/
[openspec]: https://github.com/Fission-AI/OpenSpec
[osv-scanner]: https://google.github.io/osv-scanner/
[python]: https://www.python.org/
[shellcheck]: https://www.shellcheck.net/
[shfmt]: https://github.com/mvdan/sh
[typos]: https://github.com/crate-ci/typos
[worktrunk]: https://worktrunk.dev/
[yamllint]: https://yamllint.readthedocs.io/
[zizmor]: https://docs.zizmor.sh/
