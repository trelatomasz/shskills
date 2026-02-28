
# OPTIMIZED PROMPT FOR CLAUDE SONNET 4.6

You are a **Senior Python Architect and DevEx Engineer**.

You are building a production-ready Python CLI + library called `shskills`.

The goal is to install Agent SKILLS from a GitHub repository into a local project.

Skills follow: [https://agentskills.io/home](https://agentskills.io/home)

Repository structure:

```
<repo>/
  SKILLS/
    <group>/
      <skill_name>/
        SKILL.md
        ...
```

The tool must:

* Fetch repository (branch/tag/commit supported)
* Install:

  * all skills
  * subtree (e.g. `/aws`)
  * single skill (`/aws/scale_up_service`)
* Validate structure
* Preprocess per agent
* Install into agent-specific directory
* Generate manifest
* Be publishable to PyPI
* Include CI + tests

---

# WORK MODE (IMPORTANT)

Work in 3 phases.

## PHASE 1 — Architecture & Decisions

Provide:

1. Clear subpath semantics (relative to `SKILLS/`)
2. Destination mapping per agent:

   * claude → `.claude/skills/`
   * codex → `.codex/skills/`
   * gemini → `.gemini/skills/`
   * opencode → `.opencode/skills/`
   * custom → configurable
3. Manifest format (JSON)
4. Conflict policy (default safe, `--force`, `--clean`)
5. Idempotency strategy
6. Copier usage strategy (temporary cache)
7. Security model (repo is untrusted, no execution)
8. Public API surface

Keep this section concise and structured.

STOP after Phase 1 and wait for confirmation.

---

## PHASE 2 — Full Implementation

Generate:

### Project structure (src layout)

```
shskills/
  pyproject.toml
  README.md
  src/shskills/
    __init__.py
    cli.py
    models.py
    config.py
    core/
      installer.py
      planner.py
      validator.py
      manifest.py
      copier_fetch.py
    adapters/
      base.py
      claude.py
      codex.py
      gemini.py
      opencode.py
      custom.py
  tests/
  .github/workflows/
```

### Requirements

* Typer for CLI
* Pydantic v2 models
* Abstract AgentAdapter
* Idempotent install
* No execution of remote scripts
* Deterministic behavior
* Strict typing
* Clean separation of concerns
* No TODOs in critical logic

### CLI

Commands:

* install (default)
* list
* installed
* doctor

Flags:

* --agent
* --url
* --subpath
* --ref
* --dest
* --dry-run
* --force
* --clean
* --strict
* --verbose

---

## PHASE 3 — Quality & Delivery

Provide:

1. pytest test suite:

   * unit tests
   * integration test with temp git repo
   * structural E2E test (verify layout correctness)
2. GitHub Actions:

   * CI (lint, typecheck, test, build)
   * Release (PyPI)
3. README with:

   * Quickstart
   * CLI examples
   * Adapter explanation
   * Manifest explanation
   * Security notes
4. Instructions:

   * Local run
   * Test run
   * Publish to PyPI

---

# DESIGN CONSTRAINTS

* Treat repository as untrusted input.
* Validate SKILL.md frontmatter.
* Default behavior must never overwrite existing files.
* `--force` enables overwrite.
* `--clean` removes orphaned skills.
* Must work cross-platform (Windows/Linux/macOS).
* Use minimal runtime dependencies.

---

# IMPLEMENTATION STYLE

* Use PEP 621 pyproject
* Use console_scripts entry point
* Use ruff + mypy
* ≥80% test coverage target
* Avoid global state
* Avoid unnecessary abstraction
* Keep code readable and pragmatic

---

# IMPORTANT

Do not generate implementation before Phase 1 is approved.

When generating files:

* Output full file content
* No placeholders
* No truncated sections
* Code must be runnable

