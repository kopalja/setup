  # Global Agent Instructions

  ## Core Principles

  - Be extremely concise. Sacrifice grammar for concision when appropriate.
  - Don’t overengineer. Prefer simplicity over abstraction.
  - Prefer minimal, targeted changes over broad refactoring.
  - Preserve existing patterns and conventions unless there’s a strong reason not to.
  - Verify the implementation before finishing. Run relevant tests, type checks, or linters when available.
  - Don’t make unrelated changes.
  - Don’t add abstractions, dependencies, or configuration unless necessary.
  - If requirements are ambiguous and the ambiguity materially affects the implementation, ask for clarification before proceeding.
  - If ambiguity is minor, choose the simplest reasonable interpretation and proceed.

  ## Python

  - Prefer clear, idiomatic Python with type hints for public interfaces and
    non-obvious data structures.
  - Keep functions and modules focused. Use descriptive names and add comments
    only where intent is not apparent from the code.

  ## Git

  - Treat Git as the source of truth for understanding and reviewing changes.
  - Check `git status` before editing and review `git diff` after editing.
  - Never overwrite, revert, or modify unrelated existing changes.

