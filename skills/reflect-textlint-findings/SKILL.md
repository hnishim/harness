---
name: reflect-textlint-findings
description: Reflect textlint or prh findings from the current conversation in the appropriate shared writing rules or skill-specific writing references. Use when the user asks to update writing conventions from lint feedback, locate where a writing rule belongs, or report that a finding is already documented.
---

# Reflect textlint findings

## Purpose

Convert recurring textlint/prh findings into reusable writing guidance. Locate the authoritative writing norm, determine whether the principle is already documented, make the smallest appropriate update when needed, and report the result in the chat.

## Workflow

1. Extract each finding from the conversation. Record the rule ID, the problematic pattern, the suggested correction, and whether it is mechanical formatting, terminology, or a semantic writing principle.
2. Identify the writing-norm source before editing. Search the current workspace and repository roots with `rg`, prioritizing:
   - shared references such as `skills/writing-references/prose-basics.md` and `markdown-formatting.md`;
   - a more specific reference such as technical, communication, translation, or domain writing rules;
   - a skill's own `SKILL.md` only when the rule is specific to that skill;
   - project-local documentation only when the rule is not a shared convention.
3. For every finding, perform a two-pass search. First search exact identifiers, quoted terms, and suggested corrections. Then search semantic variants in Japanese and English, including the relevant Markdown construct, punctuation, case, and spacing concepts. For example, search `半角スペース`, `日本語と英字`, and `全角` rather than only `ja-space-between-half-and-full-width`.
4. Check candidate references and headings, not only filenames. Read the surrounding lines and classify each finding as `Updated`, `Already documented`, or `Needs a decision`. Mark a finding as documented only when the reference states the behavior and its scope or exception, not merely a related keyword.
5. If the principle is missing, add it to the narrowest authoritative reference. Prefer a general principle with one representative example over a copy of the full textlint rule set.
6. Resolve conflicts explicitly. Keep semantic writing guidance in the shared references and leave mechanical enforcement to textlint/prh. If a Markdown construct is an intentional exception, state the precedence between the generic prose rule and the Markdown-specific rule.
7. Before reporting, reconcile the finding list against the result. Every finding must have one status, a reference path and heading when applicable, and a short reason. Do not silently omit a finding because a nearby rule was found.
8. Preserve unrelated worktree changes. Inspect Git status before editing, use `apply_patch`, and modify only the selected writing-reference or skill files unless the user explicitly asks to change textlint configuration.
9. Validate the result with `git diff --check` in every changed repository. Run targeted textlint or configuration checks when useful. Do not claim that a writing-reference file is lint-clean when its intentional examples or rule descriptions trigger unrelated mechanical checks.

## Guidance for findings from this workflow

- In ordinary Japanese prose, do not insert a space merely to separate Japanese text from Latin letters, digits, or half-width symbols.
- Treat Markdown inline code and Markdown links as formatting exceptions: put one half-width space outside the span where the surrounding syntax permits it, and do not alter the content inside the span.
- Keep meaningful English spaces, such as spaces inside a multiword product name or between a number and its unit.
- For repeated particles, redundant verb phrases, and formal nouns, describe the readability principle and its exceptions. Do not prohibit a particle or kanji mechanically when the meaning requires it.
- Preserve the registered spelling and capitalization of product names, tool names, rule names, and technical terms. Prefer the project's terminology dictionary when it is authoritative.

## Reporting

Report one of these outcomes:

- **Updated**: list the changed files and the principle added or clarified.
- **Already documented**: identify the existing reference and explain why no edit was needed.
- **Needs a decision**: describe the conflict or ambiguous scope and stop before making a broad or duplicate change.

Always state whether textlint configuration, dictionaries, or only writing references were changed. Keep the report concise and preserve exact paths and validation results.
