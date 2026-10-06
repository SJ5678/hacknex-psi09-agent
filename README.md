# HNX26PSI09: Safe AI Software Engineering Agent

An agent that reads a codebase, makes a requested change or bug fix, and
**only keeps the change if existing tests still pass and failures decrease**.

## How it works
1. Run the test suite -> record baseline (passing / failing).
2. Select relevant files (all if the repo is small, LLM-picked if large).
3. LLM proposes minimal edits (JSON). Existing test files are read-only.
4. Apply edits, re-run tests.
5. Regression or no improvement -> `git` revert and retry (max 3). Else commit.
6. Write an evidence report (explanation, files, before/after, diff) to `reports/`.

## Tech and declared resources
- Python 3.x, pytest, git
- LLM: Google Gemini via `google-genai` (models: gemini-3.8-flash , gemini-3.7-flash , optional local ollama )
- Optional offline: Ollama + qwen2.5-coder:7b
- AI assistants were used for [what], and we reviewed and understand all code.
- Demo repository `demo/shop_demo` was written by us.

## Install
    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt
    set GEMINI_API_KEY=<your key>

## Run
    python make_demo.py demo_work
    python agent.py demo_work "Fix the failing test: adding the same item twice must accumulate quantity"

## Reproduce results
Sample input: the task above. Sample output: `reports/report_*.md`
Run 1: 4 passing / 1 failing -> 5 passing / 0 failing, 0 regressions.
Run 2: 3 passing / 2 failing → 5 passing / 0 failing, 0 regressions, two bugs fixed in one attempt.
[Paste your actual numbers and one screenshot.]

## Safety features
- Refuses path escapes and edits to existing tests
- Reverts any change that breaks a previously passing test
- Clean git working tree required before running

## Scope note
**Built (MVP):** loop above, tested on [N] seeded bugs and 1 feature.
**Stretch goals NOT built:** auto-generated tests, non-Python parsing, big-repo code search.

## Limitations
Whole-file rewrites, up to 3 attempts, depends on the LLM's quality and on tests existing.

## Team
1.SJ
2.NM
3.US
4.KS

