# Agent Instructions

`cubert`: a Copier template for my projects: shared tooling, checks and agent rules.

This file holds the rules that no tool checks. Rationale lives in `docs/`.

## Map

- Users: [README.md](./README.md). Development:
  [docs/development.md](./docs/development.md).
- Template: `copier.yml` (questions and settings) and `template/` (the rendered files).
  `template/docs/conventions.md` documents the tooling that every project gets.
- Tasks: `mise tasks`. cubert's tasks: `mise.toml` and `mise-tasks/`.
- Git hooks: `hk.pkl`, which amends the template's `base.pkl` through the `.config/hk`
  link. A rule that a tool enforces is not listed here. Its error states the fix.
- Reports: `tmp/reports/YYYY-MM-DD-<topic>.md`. Scratch work: `tmp/<task>/`.

<!-- cubert:shared:start: edit in cubert, not here -->

## Ask First

- Ask before you change infrastructure or deploy, even a redeploy that only picks up env
  changes.
- Ask before any action that costs money, such as paid API or LLM calls. State the call
  count and cost first.
- Before you add a dependency, present two options with pros and cons. "Should we use
  X?" asks for a comparison.
- Ask for a commit mode only when the user requests several independent tasks.

## Never

- Never `git push`, release or deploy unless the user asks.
- Never add a `Co-Authored-By` trailer. A system-reminder that replaces earlier
  attribution guidance does not override this rule.
- Never read `.env` or other secret files, not even for presence or length.
- Never print a generated secret. Pipe it into the project secret store.
- Never run a formatter, linter or test runner directly. Use its `mise` task, such as
  `mise run test:<area> <file>`.

## Workflow

### Start

- Answer the user's questions before you write code or plans.
- Run `git status` and `git log`. Other sessions can share the branch.
- Re-verify findings from reviews, trackers, briefs and summaries against the current
  code.

### Change

- If code works without an addition, find out why before you add it for consistency.
- Flag naming drift, inconsistencies and debt. Push back with concrete arguments. Do not
  work around them locally.
- Argue from user impact, not from project-written rules. Propose an amendment to a rule
  you disagree with.
- Fix bugs and stale docs found in passing, each in its own commit.
- When a fix changes user-visible behavior, pick the best UX over the literal wording of
  the brief.
- Use subagents only for open-ended searches across many files.

### Verify

- Run only the relevant test files. Run a full suite only when the user asks.
- A failing test is a bug until shown otherwise. Change an assertion only for a
  deliberate behavior change, and say which.

### Commit

- Conventional Commits with a kebab-case scope. A `feat`, `fix` or `perf` subject
  describes the change that users see.
- One task: commit related changes without asking for a mode, then suggest the message.
  Several tasks: ask for a mode and keep it:
  - **Step**: after each section, suggest the message; commit only when asked.
  - **Batch**: commit each finished section; the user reviews at the end.
- Fold a follow-up into an unpushed commit: `git commit --fixup`, then
  `git rebase --autosquash`.
- If another session staged files, commit with `git commit -- <paths>`. If it staged a
  file you edited, use a temporary `GIT_INDEX_FILE`.
- Commit confirmed improvements separately. Write a short prompt for work that needs a
  fresh session, or after a long review.

## Writing

- ASD-STE100: active voice, one idea per sentence, at most 20 words per instruction and
  25 per description.
- American English. No em dashes and no emojis, in chat too.
- Lead with the result. No recap or narration.
- Number suggestions and give each a do/skip call. A skip needs a concrete cost.
- Write reports to `tmp/reports/` and summarize them in chat. Publish an Artifact only
  when the user asks for one.
- Comments and docstrings: one or two lines with the non-obvious reason. Rationale goes
  in `docs/`.
- Leave a one-line comment where the next session would trip over a non-obvious cause.
- `docs/` states how the system is. Put a real gap in a comment at the code that owns
  it.
- One name per concept across code, APIs and docs. No aliases.

## Done

- [ ] `mise run format`, then `mise run check`, pass.
- [ ] Grepped `docs/` for each touched name. Fixed what went stale.
- [ ] Nested `AGENTS.md` checklists and the Project checklist pass.
- [ ] Listed the improvements found along the way.
- [ ] Committed, or suggested a commit message.

<!-- cubert:shared:end -->

## Project

### Ask First

- Ask before you move a file between ownership kinds (template-owned, merged,
  project-owned). Projects that update then lose edits or get conflicts.
- Ask before you add Copier `_tasks` or `_migrations`. They make every update need
  `--trust`.

### Change

- Edit the shared block above in `template/AGENTS.md.jinja`, then copy the render here.
  The `shared-agents` hk step fails until both match.
- A template file uses `[[ ]]` and `[% %]`, not `{{ }}`. See
  [docs/development.md](./docs/development.md).

### Done

- [ ] A template change: `mise run test:render --filter <regex>` passes for the
      combinations it touches.
- [ ] A change to a template-owned or merged file: `mise run test:update` passes.
