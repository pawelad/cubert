# Development

How to change cubert, test the change and release it. The tooling that projects get is
described in [template/docs/conventions.md](../template/docs/conventions.md).

## Layout

| Path                       | Holds                                                         |
| -------------------------- | ------------------------------------------------------------- |
| `copier.yml`               | Questions, Copier settings and the ownership lists            |
| `template/`                | The files that Copier renders (`_subdirectory`)               |
| `mise.toml`, `mise-tasks/` | cubert's own tools and tasks                                  |
| `scripts/`                 | Scripts that cubert's tasks and hk steps call                 |
| `tests/`                   | Unit tests for the check scripts, and cubert's own answers    |
| `AGENTS.md`                | Agent rules. The shared block must match a render (see below) |

cubert follows its own template, at the working tree and not at a release:

- `.config/hk`, `.config/lychee.toml`, `.config/typos.toml`, `.config/mise/config.toml`,
  `.config/wt.toml`, `.editorconfig` and `.shellcheckrc` link into `template/`.
- `.config/mise/tasks/` links each shared task that cubert can run. Tasks with a
  conditional name stay out: mise would load them under that name.
- `.github/workflows/pr-title.yml` is a copy, not a link, because GitHub ignores a
  symlinked workflow. `.github/CODEOWNERS` and `.gitignore` are copies of rendered
  files. `test_cubert_copies.py` fails when a copy drifts.
- `hk.pkl`, `dprint.json`, `.yamllint` and `lychee.toml` layer on the template's files,
  as a project's files do.
- `cliff.toml` and `CHANGELOG.md` are project-owned copies. cubert's `cliff.toml` hides
  only the `agents`, `docs` and `e2e` scopes, because its tooling is what projects get.
- `release:preview` is a TOML task in `mise.toml`, because the shared one has a
  conditional name.

A new shared task needs a link here too. Run `mise run setup` after you clone cubert.

## Template syntax

Template files use `[[ ]]` for variables, `[% %]` for blocks and `[# #]` for comments.
hk, mise, worktrunk and GitHub Actions all use `{{ }}`, so the Jinja defaults would need
escapes in most files. `copier.yml` sets these delimiters in `_envops`.

- Only files that end in `.jinja` are rendered. Copier drops the suffix.
- Put each `[% %]` tag on its own line. `trim_blocks` and `lstrip_blocks` then remove
  the line from the output.
- A file that exists only for a feature has a conditional name:
  `[% if changelog %]cliff.toml[% endif %]`. An empty name skips the file.
- A conditional directory goes in `_exclude` in `copier.yml`. dprint cannot exclude a
  path that holds `[ ]`, so directory names stay plain.

### Markdown templates

dprint does not format `.jinja` files, but every render must pass `dprint check`. Write
a `.md.jinja` file as dprint would format its render, at 88 columns.

- Wrap whole list items or paragraphs in a conditional, never part of a wrapped line.
  Each branch then wraps the same way in every render.
- To reflow a file, strip the tag lines from a copy, run `dprint fmt` on it, then put
  the tags back.

## File ownership

Each template file is one of three kinds. The table in
[conventions.md](../template/docs/conventions.md#file-ownership) lists them.

- **Template-owned**: a plain file under `template/`. Copier merges the template's
  change into it, and a project edit conflicts. Keep it under `template/.config/` unless
  a tool needs it elsewhere.
- **Merged**: also a plain file. Copier merges the project's edits on update. Keep the
  shared part short and stable, so the merge rarely conflicts.
- **Project-owned**: listed in `_skip_if_exists`. Copier creates it once.

Moving a file to another kind breaks updates for existing projects. Treat it as a
breaking change, and say what projects must do in the release notes.

## Shared AGENTS.md block

`AGENTS.md` here has the same shared block as a project's, between the
`cubert:shared:start` and `cubert:shared:end` markers. Edit it in
`template/AGENTS.md.jinja`. The `shared-agents` hk step renders the template with
`tests/cubert-answers.yml` and fails if the blocks differ. Its diff shows what to copy.

## Tests

| Task                    | Covers                                                                      |
| ----------------------- | --------------------------------------------------------------------------- |
| `mise run check`        | hk on every file, `shared-agents` included                                  |
| `mise run test`         | The pytest tests: check scripts (also on Python 3.11), ownership, renders   |
| `mise run e2e:render`   | Renders every feature combination, then runs `setup`, `check`, `test`       |
| `mise run e2e:update`   | Renders `HEAD~1`, adds project edits, updates to the working tree, checks   |
| `mise run e2e:conflict` | Changes one line in a merged file on both sides, expects the update to stop |
| `mise run e2e:adopt`    | Adopts cubert in an existing repo: Python in `apps/backend`, and infra code |

- Renders read the working tree, including uncommitted changes.
- E2E output paths become absolute. A mise ceiling keeps parent project tasks out,
  including when `--out` points inside cubert.
- `e2e:render` runs 192 combinations, about 20 minutes with `--jobs 6`. Locally,
  `e2e:render` needs `--filter <regex>` for the combinations that a change touches, or
  `--all` when you really want every one. Names look like `p1d0t1a0c1s1_changes-only`:
  python, docker, opentofu, ansible, changelog, typescript, then openspec. A typescript
  render with python on lists two directories.
- Each render adds a small project for each enabled feature
  (`scripts/render_fixtures.sh`). After `check` and `test`, it stages one known error
  per feature and expects the matching hk step to fail. A step that stays green on that
  error is not running.
- Each render pins the newest tool releases, so upstream breakage shows up here first.
- Parallel renders can exceed GitHub's limit for calls without a token. Set the mise
  credential command from [conventions.md](../template/docs/conventions.md#tools) first.
- A render that fails on a `mise lock` provenance download runs once more, and says so.
  The first log stays next to it as `<name>.log.first`.
- Failed CI e2e jobs upload their full logs, including retry logs, for three days.
- `e2e:update --from <ref>` tests the update from an older release.
- `e2e:adopt` follows the README's adoption steps for two layouts. The infra one has an
  OpenTofu S3 backend and an Ansible project collection, and runs with no cloud login.
- CI runs `check`, `test`, `audit`, `e2e:update`, `e2e:conflict`, `e2e:adopt` and the
  full render matrix. A weekly run repeats `audit` and the render matrix, which catch
  new advisories and tool releases.
- The e2e tasks are not `test:*` tasks, so `mise run test` stays fast.

The unit tests in `tests/` cover the template's check scripts, so projects do not test
them. Five more tests read the template itself:

- `test_file_ownership.py` fails when the ownership table in `conventions.md`, the
  `_skip_if_exists` list or `template/` disagree.
- `test_update_ownership.py` renders two releases and checks what an update does to an
  edited, deleted and removed file of each kind.
- `test_cubert_copies.py` fails when cubert's copies of the PR title workflow,
  `CODEOWNERS` or `.gitignore` drift from the template's.
- `test_render.py` renders a project with awkward answers and parses the output.
- `test_worktree_setup.py` renders a project and runs `git worktree add`. It skips when
  `git`, `mise`, `copier` or `wt` is missing.

## Upgrades

- `mise run upgrade` bumps cubert's own tools and the template's dprint plugins.
- After an hk bump, change the hk package version in `template/.config/hk/base.pkl` and
  `cubert.pkl.jinja`, and the `hk>=` minimum in
  `template/.config/mise/required-tools.jinja`. The `template-versions` hk step fails
  until they match.
- After an OpenSpec bump, run `mise run openspec:refork`. It rebuilds the changes-only
  schema from the new built-in one. Review the diff, then run the render tests.
- The mise version for CI is the `version` input default in
  `template/.github/actions/setup-mise/action.yml`. Bump it by hand.
- Dependabot bumps the Actions in cubert's workflows and in the template. It also bumps
  pytest in `uv.lock`, which pins it for cubert's tests.

## Releases

cubert uses SemVer tags (`v0.1.0`). `template:update` updates a project to the latest
tag, so a tag is a release. git-cliff generates the release notes from the commits.

1. Run `mise run check`, `mise run test`, `mise run e2e:render --all` and
   `mise run e2e:update --from <previous tag>`.
2. Run `mise run release:preview` and read the entries.
3. Add the notes to `CHANGELOG.md`:
   - The first release appends `## [0.1.0] - <date>` and `Initial release.` below the
     header.
   - A later release runs `git-cliff --tag vX.Y.Z --unreleased --prepend CHANGELOG.md`.
4. Below the new entries, name each step a project must take by hand.
5. Commit with `chore(release): vX.Y.Z`. git-cliff skips that commit.
6. Copy the new section, without its heading, to `tmp/release-notes.md`. Tag with it:
   `git tag -a vX.Y.Z -F tmp/release-notes.md`. Then push the commit and the tag.

git-cliff pipes its output through dprint, so the changelog keeps the 88-column limit.
The `cliff.toml` header is wrapped the same way, so `--prepend` finds it and keeps one.

Before 1.0, a breaking change bumps the minor version. A breaking change is one that
makes `template:update` conflict or need a manual step.
