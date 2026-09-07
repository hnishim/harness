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
- Component-specific machine-checkable checks remain with the relevant
  dotfiles tests and related Issues; Harness does not maintain a permanent
  aggregate acceptance procedure.
- dotfiles keeps setup/install scripts, macOS runtime linking, and launch
  integration. The active script entrypoints are
  `../dotfiles/apps/codex/agents/agents-setup.sh`, `../dotfiles/apps/codex/skills/skills-setup.sh`, and
  `../dotfiles/apps/codex/hooks/install-codex-hooks.py`.
- `hooks/.runtime/` is generated and is not tracked.
- `skills/.system/` remains plugin-managed opaque state and is not copied, linked, or modified here.
- `custom-instructions/user-profile.md`, MOLCURE/personal Skills, draft Skills,
  and `writing-references/business-email.md` remain ignored local overlays.

Runtime cutover and component-level acceptance are owned by the dotfiles
setup and tests.

The Codex entrypoint delegates directly to Agents, Skills, Custom
Instructions, and Hooks in that order. A component failure stops the
entrypoint immediately; after correcting the cause, rerun the same entrypoint
to verify that setup converges.
