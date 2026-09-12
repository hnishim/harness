# Agent Harness

Agent definitions, Custom Instructions, Hooks, and Skills are maintained here
as one new Git history.

## Ownership

- `agents/`, `custom-instructions/`, and `skills/` contain source assets and
  definitions. Their component test ownership remains with the dotfiles
  entrypoints:
  - Agents: `../dotfiles/apps/codex/agents/tests/test_agents_setup.sh`
  - Skills: `../dotfiles/apps/codex/skills/tests/test_skills_setup.sh`
  - Custom Instructions: `../dotfiles/apps/codex/custom-instructions/tests/test_custom_instructions_setup_contract.sh`
  - Hooks installation and runtime-link configuration: `../dotfiles/apps/codex/hooks/tests/test_install_hooks.sh`
  - Top-level delegation: `../dotfiles/apps/codex/tests/test_codex_setup_delegation_contract.sh`
- `hooks/runtime/` and its Python tests contain Hook processing behavior.
- Component-specific machine-checkable checks remain with the relevant
  dotfiles tests and related Issues; Harness does not maintain a permanent
  aggregate acceptance procedure.
- dotfiles keeps setup/install scripts, macOS runtime linking, and launch
  integration. The active script entrypoints are
  `../dotfiles/apps/codex/agents/agents-setup.sh`,
  `../dotfiles/apps/codex/skills/skills-setup.sh`,
  `../dotfiles/apps/codex/custom-instructions/custom-instructions-setup.sh`,
  and `../dotfiles/apps/codex/hooks/hooks-setup.sh`.
- `hooks/.runtime/` is generated and is not tracked.
- `skills/.system/` remains plugin-managed opaque state and is not copied, linked, or modified here.
- `custom-instructions/user-profile.md`, MOLCURE/personal Skills, draft Skills,
  and `writing-references/business-email.md` remain ignored local overlays.

## Repository CI

GitHub Actions runs the Harness-owned, host-independent repository checks on
pull requests targeting `main` and pushes to `main`. Run the same checks
locally with:

```sh
python3 hooks/tests/test_gh_normal_context_guard.py
python3 hooks/tests/test_textlint_boundaries.py
python3 skills/implementation-loop/tests/test_remote_adapter_contract.py
bash custom-instructions/tests/test-openai-routing-contract.sh
python3 tests/test_ci_workflow_contract.py
```

This CI is limited to repository-local contracts and Hook processing behavior.
It does not replace the dotfiles-owned setup/install, macOS runtime cutover, or
component-level acceptance described above.

Runtime cutover and component-level acceptance are owned by the dotfiles
setup and tests.

The Codex entrypoint delegates directly to Agents, Skills, Custom
Instructions, and Hooks in that order. A component failure stops the
entrypoint immediately; after correcting the cause, rerun the same entrypoint
to verify that setup converges.
