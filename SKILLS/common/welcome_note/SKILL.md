---
name: welcome_note
description: "Print a greeting to the prompt. Always invoke when the agent starts."
allowed-tools: Bash, Read
metadata:
  author: trela.ai
  version: "1.0"
---

Print a single greeting line using the following format:
```
<TimeAndDate> | <AgentType> | <TheGoal> | <MotivationSlogan>
```

### Field Definitions

- **TimeAndDate** — Current date and time in ISO 8601 (International Organization for Standardization 8601 — date/time string format) format. Use `date -u +"%Y-%m-%dT%H:%M:%SZ"` to obtain it.
- **AgentType** — The runtime identity. Use `ClaudeCode` if running inside Claude Code. Otherwise use `AgentUnknown`.
- **TheGoal** — One sentence, maximum 6 words, describing the current task goal inferred from context.
- **MotivationSlogan** — Maximum 5 words. Examples: `Let's do it!`, `Only good code matters!`

### Rules
- Output exactly one line, no newlines within it.
- Do not explain or add any prose around the greeting line.
- Infer TheGoal from the user's request context; if unknown, use `"Goal not yet defined"`.
- Use `echo` to print the line.
- Use `date` to et current date and time.

## Example Output
```
2025-11-01T09:14:32Z | ClaudeCode | Refactor auth service | Only good code matters!
```