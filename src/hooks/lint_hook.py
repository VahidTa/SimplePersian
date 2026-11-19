#!/usr/bin/env python3
"""Advisory Simple Persian writing checks for Claude Code hooks. Never blocks.

PostToolUse (Write|Edit on a .md file): if the prose contains Persian text,
lint the file with evals/sp_lint.py and, when it has violations, print the
offending text and line number for each hit (capped at MAX_HOOK_HITS) to stderr
and exit 2 so the model sees it. English-only Markdown files and agent-internal
Markdown (such as files under .claude or CLAUDE_CONFIG_DIR) are skipped. Set
SIMPLE_PERSIAN_LINT_EXCLUDE to skip more paths.

Stop: read `last_assistant_message`. If the reply contains Persian text, check
the reply register (em-dash, bold spans, colloquialisms, slop words, and filler
openers/closers) and return a systemMessage only when the reply breaks it.
Always exit 0, so the session never loops.
"""
import fnmatch
import json
import os
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT / "evals"))

MAX_HOOK_HITS = 12
CLAUDE_DIR = ".claude"
FA_W = r"\u0621-\u065f\u066e-\u06d3\u06d5\u200c\u200d"
OPENERS = re.compile(
    rf"^\s*[\W_]*(?:سوال\s+(?:بسیار\s+)?(?:خوبی|عالی|بجایی)(?:\s+است)?|حتماً|حتما|البته(?=[,،!:])|کاملاً\s+درست\s+می‌گویید|با\s+کمال\s+میل|خوشحال\s+می‌شوم)(?![{FA_W}])"
)
CLOSERS = re.compile(
    rf"(?<![{FA_W}])(?:امیدوارم.*?(?:مفید|کمکتان|کمک\s+کرده)|اگر\s+سوال\s+دیگری\s+دارید|در\s+صورت\s+نیاز\s+به\s+راهنمایی|موفق\s+باشید)(?![{FA_W}])"
)


def load_linter():
    try:
        import sp_lint  # noqa: WPS433

        return sp_lint
    except Exception:  # noqa: BLE001
        return None


def strip_code(text):
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    return re.sub(r"`[^`]*`", " ", text)


def absolute(path, cwd=None):
    """Make the path absolute. The harness can send it relative to the session directory."""
    return pathlib.Path(cwd or ".", pathlib.Path(path).expanduser()).absolute()


def variants(path):
    """The path as written and the path with symlinks resolved."""
    return {pathlib.Path(os.path.normpath(path)), path.resolve()}


def excluded(target):
    """True for agent-internal Markdown and for paths the user excludes."""
    config_dirs = variants(absolute(os.environ.get("CLAUDE_CONFIG_DIR") or f"~/{CLAUDE_DIR}"))
    raw = os.environ.get("SIMPLE_PERSIAN_LINT_EXCLUDE", "").split(os.pathsep)
    patterns = [os.path.expanduser(p) for p in raw if p]
    for form in variants(target):
        if CLAUDE_DIR in form.parts or any(form.is_relative_to(d) for d in config_dirs):
            return True
        if any(fnmatch.fnmatch(str(form), p) for p in patterns):
            return True
    return False


def post_tool_use(event):
    path = (event.get("tool_input") or {}).get("file_path") or ""
    if not path.endswith(".md"):
        return 0
    target = absolute(path, event.get("cwd"))
    if excluded(target):
        return 0
    lint = load_linter()
    if lint is None:
        return 0
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return 0
    if not lint.has_persian(text, min_chars=15):
        return 0
    report = lint.lint(text, "descriptive")
    if not report["violations_total"]:
        return 0
    detail = lint.lint_detail(text, "descriptive")
    lines = [f"simple-persian: {target.name} has {report['violations_total']} Simple Persian violations."]
    for h in detail[:MAX_HOOK_HITS]:
        lines.append(f"  line {h['line']}, {h['category']}: {h['text']}")
    if len(detail) > MAX_HOOK_HITS:
        lines.append(f"  and {len(detail) - MAX_HOOK_HITS} more hit(s).")
    lines.append("Fix these hits in the file you just wrote, then continue.")
    sys.stderr.write("\n".join(lines) + "\n")
    return 2


def stop(event):
    reply = event.get("last_assistant_message") or ""
    lint = load_linter()
    if lint is None or not lint.has_persian(reply, min_chars=4):
        return 0
    norm_reply = lint.normalize_persian(reply)
    problems = []
    c = lint.reader_check(reply)["counts"]
    for key, label in (("em_dash", "em-dash"), ("bold_spans", "bold span"), ("colloquial", "colloquialism")):
        if c[key]:
            problems.append(f"{c[key]} {label}(s)")
    slop = lint.lint(strip_code(reply), "descriptive")["violations"].get("slop_word", 0)
    if slop:
        problems.append(f"{slop} slop word(s)")
    if OPENERS.search(norm_reply):
        problems.append("a filler opener")
    if CLOSERS.search(norm_reply):
        problems.append("a filler closer")
    if problems:
        print(json.dumps({"systemMessage": "simple-persian reply check: " + "; ".join(problems) + "."}, ensure_ascii=False))
    return 0


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:  # noqa: BLE001
        return 0
    try:
        name = event.get("hook_event_name", "")
        if name == "PostToolUse":
            return post_tool_use(event)
        if name == "Stop":
            return stop(event)
    except Exception:  # noqa: BLE001
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
