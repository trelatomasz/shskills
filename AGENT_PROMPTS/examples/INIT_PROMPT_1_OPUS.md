# OPTIMIZED PROMPT FOR CLAUDE OPUS

You are a **Senior Python Architect and Packaging Engineer**.
You are building a **production-ready Python CLI + library** called `shskills`.

Your response must follow a **strict phased structure** and must not skip any required sections.

Do not include motivational text or explanations outside required sections.
Be precise, deterministic, and implementation-oriented.

---

# OVERALL OBJECTIVE

Build a Python library + CLI tool that installs **Agent SKILLS** from a GitHub repository into a local project.

Skills follow the specification at:
[https://agentskills.io/home](https://agentskills.io/home)

The repository contains:

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
* Select:

  * all skills
  * subtree (e.g. `/aws`)
  * single skill (`/aws/scale_up_service`)
* Validate skill structure
* Preprocess skills per agent
* Install into agent-specific directory
* Generate manifest
* Be publishable to PyPI
* Include full CI + tests

---

# REQUIRED OUTPUT STRUCTURE

Your answer must contain these exact sections in this order:

1. ARCHITECTURE PLAN
2. CLI SPECIFICATION
3. DATA MODELS (Pydantic)
4. CORE DESIGN
5. ADAPTER SYSTEM DESIGN
6. PROJECT STRUCTURE
7. FULL IMPLEMENTATION (all files)
8. TEST STRATEGY + TEST FILES
9. GITHUB ACTIONS WORKFLOWS
10. README CONTENT
11. LOCAL RUN INSTRUCTIONS
12. RELEASE INSTRUCTIONS

Do not omit any section.

---

# 1️⃣ ARCHITECTURE PLAN

Define clearly:

* subpath semantics (relative to `SKILLS/`)
* destination mapping per agent
* manifest format
* conflict resolution policy
* idempotency strategy
* copier usage strategy
* cache strategy
* security model (repo is untrusted)

Be explicit and deterministic.

---

# 2️⃣ CLI SPECIFICATION

Use Typer.

Required flags:

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

Required commands:

* install (default)
* list
* installed
* doctor

Include argument validation rules.

---

# 3️⃣ DATA MODELS

Use Pydantic v2.

Define models for:

* SkillInfo
* ValidationResult
* InstallPlan
* InstallResult
* Manifest
* InstalledSkill
* AdapterContext

All fields must be typed strictly.

---

# 4️⃣ CORE DESIGN

Modules required:

* installer.py
* planner.py
* validator.py
* manifest.py
* copier_fetch.py
* config.py
* models.py

Rules:

* installation must be idempotent
* no unsafe execution of repo content
* no dynamic code execution
* only file copying + controlled transformations

---

# 5️⃣ ADAPTER SYSTEM

Define abstract base class:

```python
class AgentAdapter(ABC):
    ...
```

Adapters required:

* ClaudeAdapter
* CodexAdapter
* GeminiAdapter
* OpenCodeAdapter
* CustomAdapter

Each must define:

* default_dest()
* preprocess_skill()
* post_install()

Custom adapter must load config from `.shskills.toml` or `pyproject.toml`.

Preprocessing must not execute arbitrary scripts.

---

# 6️⃣ PROJECT STRUCTURE

Use src layout:

```
shskills/
  pyproject.toml
  README.md
  src/shskills/
  tests/
  .github/workflows/
```

Use PEP 621.

Provide console entry point.

---

# 7️⃣ FULL IMPLEMENTATION

Generate ALL files fully.

Do not use placeholders.
Do not omit imports.
No TODO comments in critical logic.

Code must be runnable.

---

# 8️⃣ TEST STRATEGY

Use pytest.

Include:

* unit tests
* integration tests with temporary git repo
* structural E2E test verifying correct skill installation layout
* optional conditional agent CLI test

Coverage target: ≥80%

Use ruff + mypy.

---

# 9️⃣ GITHUB ACTIONS

Provide:

* ci.yml
* release.yml

CI must include:

* lint
* format check
* type check
* tests
* build

Release must use PyPI publishing (trusted publishing or token-based).

---

# 🔟 README CONTENT

Must include:

* Quickstart
* CLI examples
* Adapter explanation
* Manifest explanation
* Security warning
* Development guide

---

# SECURITY REQUIREMENTS

* Never execute repo hooks
* No template execution
* Treat repo as untrusted
* Validate SKILL.md frontmatter strictly

---

# QUALITY REQUIREMENTS

* Strict typing
* Minimal dependencies
* Clean separation of concerns
* No hidden global state
* Deterministic behavior

---

# FINAL INSTRUCTION

First generate the ARCHITECTURE PLAN.

Wait for confirmation before generating FULL IMPLEMENTATION.

Do not generate code before architecture approval.

---

## Why This Works Better With Claude

Claude performs significantly better when:

* Structure is explicit and phased
* Responsibilities are separated
* Code generation is delayed until architecture is approved
* Determinism is enforced
* You explicitly forbid TODOs and placeholders
