#!/usr/bin/env python3
"""HNX26PSI09 - AI Software Engineering Agent.
Loop: baseline tests -> pick files -> LLM proposes edits -> apply -> re-test
      -> keep only if nothing regressed and failures went down, else revert.
Usage: python agent.py <repo_path> "<task>" [--test-cmd "..."] [--ext .py,.java]
"""
import argparse, json, os, pathlib, re, shlex, subprocess, sys, time

MAX_ATTEMPTS = 3
SMALL_REPO_CHARS = 30000
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache"}
REPORT_DIR = pathlib.Path(__file__).parent / "reports"


def sh(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


# ---------- tests ----------
def run_tests(repo, test_cmd=None):
    """Returns (returncode, output, passed_set, failed_set)."""
    if test_cmd:
        rc, out = sh(shlex.split(test_cmd), repo)
        return rc, out, set(), ({"test-suite"} if rc != 0 else set())
    rc, out = sh([sys.executable, "-m", "pytest", "-q", "-rA", "--tb=short",
                  "-p", "no:cacheprovider"], repo)
    passed = set(re.findall(r"^PASSED (\S+)", out, re.M))
    failed = set(re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M))
    return rc, out, passed, failed


# ---------- files ----------
def is_test(rel):
    p = pathlib.Path(rel)
    return ("test" in p.name.lower()) or bool({"tests", "test"} & set(p.parts))


def code_files(repo, exts):
    out = []
    for p in repo.rglob("*"):
        if p.is_file() and p.suffix in exts:
            if not (set(p.relative_to(repo).parts) & SKIP_DIRS):
                out.append(p)
    return sorted(out)


def build_context(repo, exts, task, test_output):
    files = code_files(repo, exts)
    texts = {str(f.relative_to(repo)).replace("\\", "/"): f.read_text(encoding="utf-8", errors="ignore")
             for f in files}
    if sum(len(t) for t in texts.values()) > SMALL_REPO_CHARS:
        listing = "\n".join(f"{n} ({len(t)} chars)" for n, t in texts.items())
        pick = llm(f"""Task: {task}
Test output:
{test_output[-3000:]}
Repo files:
{listing}
Choose at most 6 files needed to understand and complete the task.
Reply ONLY JSON: {{"files": ["path1", "path2"]}}""")
        texts = {n: texts[n] for n in pick.get("files", []) if n in texts}
    parts = []
    for n, t in texts.items():
        tag = " (READ-ONLY TEST FILE - do not edit)" if is_test(n) else ""
        parts.append(f"### {n}{tag}\n{t}")
    return "\n\n".join(parts)


def apply_edits(repo, edits):
    changed = []
    for e in edits:
        rel = e["file"].replace("\\", "/")
        target = (repo / rel).resolve()
        if repo not in target.parents:
            raise ValueError(f"unsafe path refused: {rel}")
        if target.exists() and is_test(rel):
            raise ValueError(f"editing existing test file refused: {rel}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(e["content"], encoding="utf-8")
        changed.append(rel)
    return changed


def revert(repo):
    sh(["git", "checkout", "--", "."], repo)
    sh(["git", "clean", "-fdq"], repo)


# ---------- LLM ----------
def parse_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    return json.loads(text)


def llm(prompt):
    import time
    provider = os.getenv("LLM_PROVIDER", "gemini")

    if provider == "ollama":
        return _ollama(prompt)

    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    cfg = types.GenerateContentConfig(response_mime_type="application/json")
    models = [m for m in (os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
                          os.getenv("GEMINI_FALLBACK_MODEL")) if m]
    last_err = None
    for model in models:
        for wait in (0, 5, 15, 30):
            time.sleep(wait)
            try:
                resp = client.models.generate_content(model=model, contents=prompt, config=cfg)
                return parse_json(resp.text)
            except Exception as e:
                last_err = e
                if "503" not in str(e) and "429" not in str(e):
                    break   # not a busy-server error, so try the next model
                print(f"  [{model}] busy, retrying...")
    print("  Gemini unavailable, falling back to offline Ollama")
    try:
        return _ollama(prompt)
    except Exception:
        raise RuntimeError(f"All LLM options failed: {last_err}")


def _ollama(prompt):
    import ollama
    r = ollama.chat(model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
                    messages=[{"role": "user", "content": prompt}], format="json")
    return parse_json(r["message"]["content"])


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("repo")
    ap.add_argument("task")
    ap.add_argument("--test-cmd", default=None, help="custom test command (non-pytest)")
    ap.add_argument("--ext", default=".py", help="comma list, e.g. .py,.java")
    a = ap.parse_args()

    repo = pathlib.Path(a.repo).resolve()
    exts = set(a.ext.split(","))
    if sh(["git", "status", "--porcelain"], repo)[1].strip():
        sys.exit("Working tree not clean. Commit or stash first.")

    log = [f"# Agent report\n\n**Task:** {a.task}\n"]
    _, base_out, base_pass, base_fail = run_tests(repo, a.test_cmd)
    print(f"[baseline] passing={len(base_pass)} failing={len(base_fail)}")
    log.append(f"**Baseline:** {len(base_pass)} passing, {len(base_fail)} failing "
               f"({', '.join(sorted(base_fail)) or 'none'})\n")

    feedback, success = "", False
    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"[attempt {attempt}] asking LLM...")
        context = build_context(repo, exts, a.task, base_out)
        plan = llm(f"""You are a careful software engineer.
Task: {a.task}

Current test output:
{base_out[-4000:]}

{('Previous attempt failed: ' + feedback) if feedback else ''}

Source files:
{context}

Rules:
- Make the SMALLEST change that completes the task.
- Use only imports, functions and APIs that exist in the files shown or the standard library.
- NEVER edit existing test files. You may add new files.
- Do not break behaviour that currently works.
Reply ONLY JSON:
{{"explanation": "root cause and fix in 2-3 sentences",
  "edits": [{{"file": "relative/path", "content": "FULL new file content"}}]}}""")
        try:
            changed = apply_edits(repo, plan["edits"])
        except Exception as e:
            feedback = f"Edit rejected: {e}"
            log.append(f"## Attempt {attempt}: rejected - {e}\n")
            revert(repo)
            print("  rejected:", e)
            continue

        rc, out, now_pass, now_fail = run_tests(repo, a.test_cmd)
        regressions = base_pass - now_pass
        improved = len(now_fail) < len(base_fail) or (not base_fail and rc == 0)
        print(f"  files={changed} passing={len(now_pass)} failing={len(now_fail)} "
              f"regressions={len(regressions)}")
        if not regressions and improved:
            sh(["git", "add", "-A"], repo)
            c_rc, c_out = sh(["git", "commit", "-m", f"agent: {a.task[:60]}"], repo)
            diff = sh(["git", "diff", "HEAD~1", "HEAD"], repo)[1] if c_rc == 0 else "(commit failed)"
            log.append(f"## Attempt {attempt}: SUCCESS\n**Explanation:** {plan['explanation']}\n"
                       f"**Files changed:** {changed}\n**After:** {len(now_pass)} passing, "
                       f"{len(now_fail)} failing, 0 regressions\n\n```diff\n{diff}\n```\n")
            success = True
            print("SUCCESS:", plan["explanation"])
            break
        feedback = (f"regressions={sorted(regressions)}; still failing={sorted(now_fail)}\n"
                    f"{out[-2500:]}")
        log.append(f"## Attempt {attempt}: reverted\nRegressions: {sorted(regressions)}; "
                   f"failing: {sorted(now_fail)}\n")
        revert(repo)
        print("  reverted (no improvement or regression)")

    if not success:
        print("FAILED: no safe fix found. Repo left unchanged.")
        log.append("**Result: no safe fix found. Repo left unchanged.**\n")
    REPORT_DIR.mkdir(exist_ok=True)
    report = REPORT_DIR / f"report_{int(time.time())}.md"
    report.write_text("\n".join(log), encoding="utf-8")
    print("Report:", report)


if __name__ == "__main__":
    main()
