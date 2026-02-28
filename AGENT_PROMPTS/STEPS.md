1. Architecture
   1. GUARDRAILS
   2. Instruction
   3. PHASE1
```text
Provide architecture plan only:
- subpath semantics
- adapter system design
- manifest format
- copier strategy
- idempotency & conflict policy
- public API surface
- project structure

Do NOT generate implementation yet.
```
2. PHASE 2 - IMPLEMENTATION
Requirements:
- Full src layout
- All files complete
- No TODO placeholders
- No truncated files
- Deterministic code
- Strict typing
- Idempotent installer

If output exceeds safe size, generate in batches and clearly mark continuation.

3. PHASE 3 - TESTS & CI
Generate:
- pytest test suite
- integration tests (temp git repo fixture)
- structural E2E layout verification
- GitHub Actions (CI + release)
- README
- Local run instructions
- PyPI release instructions
