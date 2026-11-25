# Changelog

All notable changes to this project are documented here.
[git-cliff](https://git-cliff.org) generates them from the Conventional Commits history.
Do not edit past entries by hand.

## [0.2.1] - 2026-11-25

### Bug Fixes

#### CI

- Stop uv warning that a script has no lockfile in each CI check and test
  ([bf5b54e](https://github.com/pawelad/cubert/commit/bf5b54e4feee38cb955fbc4bc713fe85f02f3d3a))

## [0.2.0] - 2026-11-25

### Features

#### Checks

- Let a project check whole files of a type for em dashes and British spelling
  ([e32a7c8](https://github.com/pawelad/cubert/commit/e32a7c8395e55593b9429bc7fff2fcd24a3a6250))
- Load a root .betterleaks.toml, so a project can allowlist a path or a pattern
  ([056425a](https://github.com/pawelad/cubert/commit/056425a6c59c75e695adfd3103396a0565d0a6fd))

#### CI

- Skip the check and test tasks in CI_CHECK_SKIP, and give Ansible a throwaway vault
  password in CI
  ([831e109](https://github.com/pawelad/cubert/commit/831e109a7438594ccc31f6cb805d7625c4924aa2))
- Mark where a project adds keys to each shared Dependabot entry
  ([3d87263](https://github.com/pawelad/cubert/commit/3d8726334496ca112e307a5386164ac98019f9f1))
- Skip install in ci:check when CI_CHECK_SKIP_INSTALL is set
  ([55c5a7f](https://github.com/pawelad/cubert/commit/55c5a7ff0af4ff1da8c1a6678ca35b87af372a92))
- Lock project workflow actions in a generated actions.lock
  ([ba7a689](https://github.com/pawelad/cubert/commit/ba7a689bcf07d7d2cfb3f0c8b9a79a6731f1c43c))

#### Tasks

- Replace a project post-checkout hook with hooks:install --replace, and keep a backup
  ([09d13db](https://github.com/pawelad/cubert/commit/09d13db94be5cafa45c00ecd6c3be15f0847beee))
- List each cubert-gap marker after template:update
  ([7d12736](https://github.com/pawelad/cubert/commit/7d12736fae3383531ad00d103872e6c57be67517))

#### Release

- Confirm the push with gum when it is installed
  ([c4f5c73](https://github.com/pawelad/cubert/commit/c4f5c73ff999d626a97c7f562020c13a308180ad))
- Let a changelog area set its heading, such as ci:CI
  ([1c0f6d3](https://github.com/pawelad/cubert/commit/1c0f6d359d09c1c28e6d2f6f1107c4f742a65d91))

#### Audit

- Skip the locks in AUDIT_DEPS_EXCLUDE, which app tasks audit with their own scanner
  ([2d013bc](https://github.com/pawelad/cubert/commit/2d013bc5b888c91e3816bcd004f1f81b123f383a))

#### OpenTofu

- Keep the R2 endpoint readable in redacted plan output
  ([19e675a](https://github.com/pawelad/cubert/commit/19e675a12574d18c3df4ced3d297a75c956b3c00))

#### OpenSpec

- Add openspec_changes_tracked, which ignores OpenSpec changes and links them into
  worktrees
  ([cfa8439](https://github.com/pawelad/cubert/commit/cfa8439d596d7d4f73bef620850162c41c22f051))

#### Template

- Mark each workaround for a cubert gap, and remove it after an update
  ([1830b62](https://github.com/pawelad/cubert/commit/1830b624e9eef42760929bb199f7810a47117c3f))

#### Agent rules

- Ask another provider's model to review the work on "final review"
  ([d1ceadb](https://github.com/pawelad/cubert/commit/d1ceadb6c863e7112cb80787191697e18dac4cf3))

### Bug Fixes

#### Checks

- Keep smart quotes in data files and strings, and fix them in prose and comments only
  ([20007b9](https://github.com/pawelad/cubert/commit/20007b9d85c4fc468464a668b4dd36f2c901eb6b))
- Make mypy check a plain file for the Python that ruff's per-file-target-version gives
  it
  ([8ccceac](https://github.com/pawelad/cubert/commit/8ccceac0d31e9088fac27ee9323a9bcdad8b6a35))
- Leave PEP 723 metadata blocks out of the comment-length prose count
  ([6428c9f](https://github.com/pawelad/cubert/commit/6428c9fbb0ba7510ee379472f9d9f0b8237a7823))
- Skip MAC addresses and PEM blocks in typos
  ([563e328](https://github.com/pawelad/cubert/commit/563e328e56fb27f248fa73a055fa49296fae195d))
- Make Biome leave Markdown and YAML to dprint, which Biome 2.6 started to format
  ([b820c3d](https://github.com/pawelad/cubert/commit/b820c3d234592973d90a32832cf8807f2daf2ed9))
- Name the pins check fix for a templated tool version, which mise.lock cannot verify
  ([38e3f3e](https://github.com/pawelad/cubert/commit/38e3f3e672c09952565c0ed40c0737620e0e3f2a))
- Skip hex IDs glued to a prefix in typos, such as Google Maps place IDs
  ([640822a](https://github.com/pawelad/cubert/commit/640822ad49139c314cf84fb070c2798c450c4053))
- Flag the British spelling of story, as in a floor of a building
  ([5b25778](https://github.com/pawelad/cubert/commit/5b2577833367fa93e9a8d6c2a0e8a313e4252e9c))

#### CI

- Install tools with mise-action v5, and give the installs a GitHub token against rate
  limits
  ([f4e100d](https://github.com/pawelad/cubert/commit/f4e100de13115d2f509ca050e79c5c9409d9a3f8))

#### Tasks

- Make setup add a missing required tool at its minimum when the newest allowed release
  is older
  ([7cef547](https://github.com/pawelad/cubert/commit/7cef5477dbce075e04078f0982ff2ffa2a067756))
- Make test run the suites when every test:<area> task is hidden
  ([279fff1](https://github.com/pawelad/cubert/commit/279fff167a48ccf5cc8a8497a62a1673a80e5316))
- Skip tsc in the format task only when hk.pkl defines a tsc step
  ([83aa3b9](https://github.com/pawelad/cubert/commit/83aa3b915d76ed625138237629159d95ad7c4e25))
- Make setup pin a seeded tool at its minimum when the newest allowed release is older
  ([9d9e756](https://github.com/pawelad/cubert/commit/9d9e7566c3ae9d7db035255be431d71ec9853953))
- Name setup and check in the template:update conflict message
  ([b410f98](https://github.com/pawelad/cubert/commit/b410f98bdcff81ec353b01d13949028eca209301))
- Pin a tool to its minimum when setup finds no release past the cutoff
  ([055b092](https://github.com/pawelad/cubert/commit/055b0922ab0dbc057bcf05203f420411afa3a10d))

#### Release

- Title each GitHub Release with its tag and unwrap its notes
  ([ec57464](https://github.com/pawelad/cubert/commit/ec5746431ecc8a99dce67782ee8a05e9fa63e55a))

#### Audit

- Retry a link that times out or fails with a server error, with growing waits
  ([48c6868](https://github.com/pawelad/cubert/commit/48c686836887e8f4d3ca24cb4fd9f82a0d53bb39))

#### OpenTofu

- Remove a partial state snapshot, and refuse a state with empty encrypted data
  ([bb49c62](https://github.com/pawelad/cubert/commit/bb49c62b93c24e0f021bbf4acfd753a4f5ab4cbf))
- Refuse to back up an OpenTofu state that is not encrypted
  ([ad91396](https://github.com/pawelad/cubert/commit/ad91396d093a7854b701cb8d3993392ed5d7d517))

#### Ansible

- Leave Ansible YAML to the yamllint step, which loads the project's rules
  ([deb1737](https://github.com/pawelad/cubert/commit/deb173758c8cd13192146ca54d860668d0bc6ffe))
- Stop seeding a .gitkeep in the Ansible directory, which came back after each delete
  ([c44bfe7](https://github.com/pawelad/cubert/commit/c44bfe7bc91253e0aa3bf4fbf5d73c54c053e367))

#### OpenSpec

- Wrap a long project description in openspec/config.yaml, which yamllint rejected
  ([dff9df3](https://github.com/pawelad/cubert/commit/dff9df34cd368026336169bc5be86d26be832c88))

#### Template

- Ignore OpenTofu crash logs, override files and .DS_Store in .gitignore
  ([9965949](https://github.com/pawelad/cubert/commit/99659495e25761a6d2a6bf0bfbe18a331ecf4000))
- Track .python-version even when a global gitignore hides it
  ([487eaa0](https://github.com/pawelad/cubert/commit/487eaa070cc91960433d53f8eaefb51265435c6e))
- Drop impeccable from gitignore, worktree setup and conventions
  ([d5036b7](https://github.com/pawelad/cubert/commit/d5036b71c2678db75b0974392f811c87ba0c5050))

#### Agent rules

- Unstage the paths after git commit -- <paths>, so a hook fix is not reverted
  ([1756b41](https://github.com/pawelad/cubert/commit/1756b41ca48e2e12f3c2c20dc3aabc65f5d711f2))
- Keep checkboxes out of OpenSpec workflow follow-up bullets
  ([019575e](https://github.com/pawelad/cubert/commit/019575ed68432f9c299671529992052f6df90f2a))
- Review the commits not yet on origin/main, so unpushed main counts
  ([234e8f8](https://github.com/pawelad/cubert/commit/234e8f82106d4673517873a9e4d1b19f7197a87d))

### Performance

#### CI

- Cache the OpenTofu providers and Ansible collections in the Check job
  ([44f85bb](https://github.com/pawelad/cubert/commit/44f85bb224b654263f627f79c3b171c9688dd475))

## [0.1.0] - 2026-11-22

Initial release.
