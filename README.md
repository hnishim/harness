# Agent Harness

Agent definitions, Custom Instructions, Hooks, and Skills are maintained here
as one new Git history.

## Ownership

- `agents/`, `custom-instructions/`, and `skills/` contain source assets and
  definitions. Their setup/install contract tests remain with the dotfiles
  entrypoints.
- `hooks/runtime/` and its Python tests contain Hook processing behavior.
  Hook installation and runtime-link configuration tests remain in
  `dotfiles/codex/tests/`.
- `tests/test_migration_boundaries.sh` checks the manifest, tracked/ignored
  boundaries, migrated hashes, retired source files, and excluded generated
  paths.
- `tests/test_hir82_transaction.sh` checks cross-component transaction
  rollback and success fixtures.
- `tests/manual-acceptance.md` is the macOS/LaunchAgent/Notion acceptance
  procedure; it is not a setup-script test.
- dotfiles keeps setup/install scripts, macOS runtime linking, and launch
  integration. The active script entrypoints are
  `dotfiles/codex/agents-setup.sh`, `dotfiles/skills/skills-setup.sh`, and
  `dotfiles/codex/install-codex-hooks.py`.
- `hooks/.runtime/` is generated and is not tracked.
- `skills/.system/` remains plugin-managed and is not copied here.
- `custom-instructions/user-profile.md`, MOLCURE/personal Skills, draft Skills,
  and `writing-references/business-email.md` remain ignored local overlays.

The migration manifest records source revisions and hashes without storing
security-scoped bookmark bytes or other local credentials. Runtime cutover,
macOS acceptance, and old-repository cleanup are performed only by HIR-82.
