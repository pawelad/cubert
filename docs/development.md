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

cubert follows its own template. `.config/hk`, `.editorconfig` and `.shellcheckrc` link
into `template/`. `hk.pkl`, `dprint.json` and `.yamllint` layer on the template's files,
as a project's files do.

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

- **Template-owned**: a plain file under `template/`. Copier replaces it on update. Keep
  it under `template/.config/` unless a tool needs it elsewhere.
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

| Task                   | Covers                                                                           |
| ---------------------- | -------------------------------------------------------------------------------- |
| `mise run check`       | hk on every file (`shared-agents` included) and the unit tests (`check:scripts`) |
| `mise run test:render` | Renders every feature combination, then runs `setup` and `check` in each         |
| `mise run test:update` | Renders `HEAD~1`, adds project edits, updates to the working tree, checks        |

- Renders read the working tree, including uncommitted changes.
- `test:render` runs 96 combinations, about 10 minutes with `--jobs 6`. Use
  `--filter <regex>` for the combinations that a change touches. Names look like
  `p1d0t1a0c1_changes-only`: python, docker, opentofu, ansible, changelog, then
  openspec.
- Each render pins the newest tool releases, so upstream breakage shows up here first.
- `test:update --from <ref>` tests the update from an older release.
- CI runs `check`, `test:update` and the full render matrix.

The unit tests in `tests/` cover the template's check scripts, so projects do not test
them.

## Upgrades

- `mise run upgrade` bumps cubert's own tools and the template's dprint plugins.
- After an hk bump, change the hk package version in `template/.config/hk/base.pkl` and
  `cubert.pkl.jinja`. The `template-versions` hk step fails until they match.
- After an OpenSpec bump, run `mise run openspec:refork`. It rebuilds the changes-only
  schema from the new built-in one. Review the diff, then run the render tests.
- The mise version for CI is the `version` input default in
  `template/.github/actions/setup-mise/action.yml`. Bump it by hand.
- Dependabot bumps the Actions in cubert's workflows and in the template.

## Releases

cubert uses SemVer tags (`v0.1.0`). `template:update` updates a project to the latest
tag, so a tag is a release.

1. Run `mise run check`, `mise run test:render` and
   `mise run test:update --from <previous tag>`.
2. Write the release notes from `git log <previous tag>..HEAD`. Name each step a project
   must take by hand.
3. Tag: `git tag -a vX.Y.Z -m "<notes>"`. Then push the tag.

Before 1.0, a breaking change bumps the minor version. A breaking change is one that
makes `template:update` conflict or need a manual step.
