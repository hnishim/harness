# Agent Harness

Agent definitions, Custom Instructions, Hooks, and Skills are maintained here
as one new Git history.

## Ownership

- `agents/`, `custom-instructions/`, and `skills/` contain source assets and
  definitions. Their setup/install contract tests remain with the dotfiles
  entrypoints.
- `hooks/runtime/` and its Python tests contain Hook processing behavior.
  Hook installation and runtime-link configuration tests remain in
  `dotfiles/apps/codex/tests/` and `dotfiles/apps/codex/skills/tests/`.
- `tests/test_hir82_transaction.sh` checks cross-component transaction
  rollback and success fixtures.
- `tests/manual-acceptance.md` is the macOS/LaunchAgent/Notion acceptance
  procedure; it is not a setup-script test.
- dotfiles keeps setup/install scripts, macOS runtime linking, and launch
  integration. The active script entrypoints are
  `dotfiles/apps/codex/agents-setup.sh`, `dotfiles/apps/codex/skills/skills-setup.sh`, and
  `dotfiles/apps/codex/install-codex-hooks.py`.
- `hooks/.runtime/` is generated and is not tracked.
- `skills/.system/` remains plugin-managed opaque state and is not copied, linked, or modified here.
- `custom-instructions/user-profile.md`, MOLCURE/personal Skills, draft Skills,
  and `writing-references/business-email.md` remain ignored local overlays.

Runtime cutover and macOS acceptance are performed by the dotfiles setup and
the local acceptance procedure.
