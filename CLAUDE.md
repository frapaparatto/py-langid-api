# CLAUDE.md

## AI Usage Rules

**Root cause analysis protocol**

When something breaks, do not look for the solution. Look for the cause. AI is forbidden for the entire duration of this protocol.

- Debugging without search engines: write the hypothesis on paper first (what is happening and why), then verify it. Hypothesis and verify cycle, not search and copy.
- Read real postmortems: Google SRE Book, SRE Weekly, Cloudflare blog. Study how senior engineers trace from anomaly to root cause in distributed systems.
- 5 Whys applied to code: when a bug is found, ask why five times. Start from the symptom and reach the architecture.
- Deliberate practice: use AI to generate code with hard-to-find bugs, study the why behind a bug, and learn associated concepts.

**When AI cannot write code:**
- New concepts not yet studied or implemented manually
- CSAPP labs and from-scratch implementations
- Debugging: manual debugging always, reach the root cause independently
- Architecture decisions: AI gives feedback after a position exists, never as the first answer
- AI never replaces manual debugging, documentation reading, or bottom-up code understanding. Slowing down now to develop these skills is worth more than short-term speed.

**When AI can write code (all four conditions must be true simultaneously):**
1. The concept has already been studied and implemented at least once manually. This is mechanical repetition, not learning.
2. Scope is limited to one function or equivalent block. If the impulse is to expand to "just this class" or "just this layer," stop.
3. Before asking, write comment-specs in the code: what the function does, what arguments it accepts, the logical steps. The comments are the spec. AI executes, it does not think.
4. Before accepting output: read every line, explain it mentally. If any line cannot be explained, do not commit it. Understand it or rewrite it.

**When AI can be consulted:**
- After implementation is complete, for feedback and pattern review
- After reading documentation and forming a hypothesis
- After trying 2-3 approaches independently
- Before any question, a position already exists. AI enters only for comparison and feedback, never as the first answer.
- If still stuck after a 20-minute timer: AI uses Socratic method only, questions and challenges to understanding, never the solution.
- Only after implementation is complete: for feedback, pattern review, or re-implementing something from scratch with deeper understanding.

**Debugging rule:**
If debugging assistance is requested, AI must not identify the bug or point to the line. AI asks guiding questions only: what does this function return when called with X, what does the log say at this point, what is the value of this variable before this call. The developer reaches the root cause independently. AI confirms or challenges the conclusion only after it has been stated.

**Commit messages and pull requests:**
AI may write commit messages only for refactor, chore, and docs commits. For any commit involving a feature or fix, the developer writes the message. AI may give feedback and correct grammar only after a draft exists. Same rule applies to PR descriptions.


## Code Behaviour

- Before writing any code: ask about any doubts, propose a plan with the list of files to change and the approach, wait for explicit approval. Do not read or edit files until the plan is confirmed.
- Changes must be scoped. One concern per edit session.
- If a change involves a concept not yet studied or implemented by the user, flag it explicitly and defer to manual implementation.
- Before making changes: search the codebase for every call site and occurrence affected. List them in a numbered checklist. Wait for confirmation of completeness, then edit each one and check it off.
- After the plan is executed, run: `uv run pytest` and `uv run ruff check .`


## Audit and Review Behaviour

- When asked to audit, review, or report: do NOT modify any files unless explicitly instructed. Produce read-only analysis first. Wait for confirmation before editing.
- Before writing any documentation output: confirm (1) target file path, (2) whether to create new or append, (3) heading and section format. Wait for approval, then write.


## Daily Log Template

When asked to create a daily log entry, use this template. File goes in `docs/daily_logs/`. Never edit past entries.

```markdown
## YYYY-MM-DD

**Active branch:** feature/X-description
**Issue:** #X
**Hours logged:** X

### What I built
Concrete working code produced this session. Be specific:
"Implemented the /identify-language endpoint with input validation"
is useful. "Worked on the API stuff" is not.

### What I learned
Python and framework concepts encountered, surprises, idioms understood
for the first time. This is the most important field for long-term retention.

### Blockers / open questions
Anything that slowed you down. Unresolved questions. Things that
need research before the next session.

### Next session
The exact first action for the next session. One sentence, specific
enough that you can open your editor and start without thinking.
```

Commit the log entry with: `docs(log): add YYYY-MM-DD session notes`


## Documentation Locations

- Always confirm the target file before writing documentation.
- ADRs: `docs/adr/`
- Personal todos and capture notes: `docs/personal/todo.md`
- Daily logs: `docs/daily_logs/`
- Architecture reference: `docs/architecture.md`


## Code Style

- Write comments only for non-obvious behaviour, constraints, or the reasoning behind an implementation. Do not comment what the code already says.
- No hyphens, long dashes, or em dashes in markdown files or comments. Use commas, colons, or plain text instead.
- Docstrings on all public functions and classes. Use the plain docstring style without reStructuredText or Google-style tags unless the project explicitly adopts one.


## Error Handling Strategy

Python has no `std::optional`. The idiomatic substitutes are:
- Return `None` for expected absence (a search that finds nothing). The caller checks for `None` explicitly.
- Raise a specific exception for unexpected failures or constraint violations.

Two coexisting Python conventions to know:
- LBYL (Look Before You Leap): check preconditions before performing an operation. Equivalent to the C++ defensive check pattern.
- EAFP (Easier to Ask Forgiveness than Permission): attempt the operation, catch the exception if it fails. Idiomatic Python when the failure case is rare and the check would duplicate work.

Use LBYL for validation at API boundaries (input arriving from outside the system). Use EAFP for I/O and operations where checking and doing cannot be separated atomically.

Strategy by error type:
- `assert` for programmer errors: invariants that must never be false if the code is correct. Removed when Python runs with `-O`. Same principle as C++ `NDEBUG`.
- `raise ValueError` for validation errors: invalid input, constraint violations, illegal state.
- `raise RuntimeError` for infrastructure and I/O errors where a more specific exception does not exist.
- Use specific built-in exceptions (`FileNotFoundError`, `TypeError`, `KeyError`) when they match precisely. Do not raise generic `Exception`.
- FastAPI HTTP exceptions: use `fastapi.HTTPException` with an explicit `status_code` at the router boundary only. Service and domain layers raise plain Python exceptions. The router catches them and converts to HTTP responses.
- Never let a raw unhandled exception reach the HTTP response. A global exception handler in `main.py` catches anything the router did not handle and returns a structured JSON error.


## Testing Conventions

To be written after the testing milestone is complete and the approach has been studied and implemented manually.


## Architecture Rules

To be filled as the project evolves and after an overview of the full implementation exists.


## Git Conventions

- Conventional Commits format: `<type>(<scope>): <short description>`
- Types: feat, fix, refactor, test, docs, chore, style, perf, build, ci
- Scopes: api, router, model, schema, validation, logging, config, docker, test, ci
- Subject line: imperative mood, no capital after colon, no period, max 72 chars
- Body: explain why, not what. Wrap at 72 chars. Blank line between subject and body.
- Do not add co-authored-by lines. All commits are authored by the developer alone.
