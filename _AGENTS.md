  # Global Agent Instructions

  ## Core Principles

  - **Concision:** Be extremely concise. Sacrifice grammar for concision when appropriate.
  - **Simplicity:** Don’t overengineer. Prefer simplicity over abstraction.
  - **Scope:** Make minimal, targeted changes. Don’t make unrelated changes or broad refactors.
  - **Consistency:** Preserve existing patterns and conventions unless there’s a strong reason not to.
  - **Tests:** When implementing a new feature, add relevant tests and verify the implementation against them.
  - **Verification:** Before finishing, run relevant tests, type checks, linters, or equivalent verification when available.
  - **Ambiguity:** Ask for clarification only when ambiguity materially affects the implementation. Otherwise, choose the simplest reasonable interpretation and proceed.

  ## Git

- When working in a worktree and asked to `push`:
  ```sh
  git add -A
  git commit -m "<concise description of changes>"
  git push -u origin HEAD
  gh pr create --base main --fill
  ```
- Check `git status` before editing and review `git diff` after editing.
- Never overwrite, revert, or modify unrelated existing changes.
