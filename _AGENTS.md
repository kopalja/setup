  # Global working preferences

  These are default instructions for all projects. Follow repository-local
  `AGENTS.md` files and documented project conventions when they are more
  specific.

  ## General preferencies

  - Be extremely concise. Sacrifice grammar for the sake of concision.

  ## Python

  - Try to always use typing
  - Prefer clear, idiomatic Python with type hints for public interfaces and
    non-obvious data structures.
  - Keep functions and modules focused. Use descriptive names and add comments
    only where intent is not apparent from the code.
  - Run the project's configured formatter, linter, type checker, and tests. If no
    commands are documented, inspect the repository before choosing tools; do not
    add tooling solely to validate a small change.

  ## Git

  - Treat Git as the source of truth for understanding and reviewing changes.
  - Check `git status` before editing and review `git diff` after editing.

