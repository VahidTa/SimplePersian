#!/usr/bin/env python3
"""Reply-register benchmark for Simple Persian: what a reader sees in a chat reply.

For each prompt in reply_scenarios.json, runs `claude -p` once per condition
(baseline plus each --skill label=path) and scores the reply with
sp_lint.reader_check and sp_lint.lint.

Usage:
  python3 evals/run_reply_bench.py --skill sp=prompts/system-prompt.md --out evals/results/reply-run
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sp_lint  # noqa: E402

FA_W = sp_lint.FA_WORD_CHAR
WB_L = sp_lint.WB_L
WB_R = sp_lint.WB_R
OPENER = re.compile(
    rf"^\s*\W*{WB_L}(?:سوال\s+(?:بسیار\s+)?(?:خوبی|عالی|بجایی)(?:\s+است)?|حتماً|حتما|البته|کاملاً\s+درست\s+می‌گویید|با\s+کمال\s+میل|خوشحال\s+می‌شوم){WB_R}"
)
CLOSER = re.compile(
    rf"{WB_L}(?:امیدوارم.*?(?:مفید|کمکتان|کمک\s+کرده)|اگر\s+سوال\s+دیگری\s+دارید|در\s+صورت\s+نیاز\s+به\s+راهنمایی|موفق\s+باشید){WB_R}"
)


def score(text):
    r = sp_lint.reader_check(text)
    lint = sp_lint.lint(text, "descriptive")
    out = dict(r["counts"])
    out.update(
        words=r["words"],
        visible_total=r["visible_total"],
        opener=bool(OPENER.search(text)),
        closer=bool(CLOSER.search(text)),
        slop_word=lint["violations"]["slop_word"],
        viol_per_100w=lint["violations_per_100w"],
    )
    return out


def extract_result(stdout):
    try:
        data = json.loads(stdout)
    except Exception:  # noqa: BLE001
        return stdout.strip()
    if isinstance(data, dict):
        return data.get("result", "")
    for item in reversed(data):
        if isinstance(item, dict) and item.get("type") == "result":
            return item.get("result", "")
    return ""


def generate(prompt, system, model, effort):
    cmd = [
        "claude", "-p", prompt, "--model", model,
        "--output-format", "json", "--setting-sources", "",
        "--disallowedTools", "Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch",
    ]
    if system:
        cmd += ["--append-system-prompt", system]
    if effort:
        cmd += ["--effort", effort]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd="/tmp")
    return extract_result(r.stdout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skill", action="append", default=[], help="label=path, repeatable")
    ap.add_argument("--model", default="claude-sonnet-4-6")
    ap.add_argument("--effort", default="low")
    ap.add_argument("--out", required=True)
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    conds = {"baseline": None}
    for item in a.skill:
        label, path = item.split("=", 1)
        conds[label] = pathlib.Path(path).read_text(encoding="utf-8")
    scen = json.loads((HERE / "reply_scenarios.json").read_text(encoding="utf-8"))
    rows = []
    for s in scen:
        for cond, system in conds.items():
            f = out / f"{cond}__{s['id']}.txt"
            if not f.exists() or not f.read_text(encoding="utf-8").strip():
                if a.report_only:
                    continue
                reply = generate(s["prompt"], system, a.model, a.effort)
                if "session limit" in reply or "Not logged in" in reply:
                    print(f"SKIP {f.name}: harness message, not cached", file=sys.stderr)
                    continue
                f.write_text(reply, encoding="utf-8")
            text = f.read_text(encoding="utf-8")
            if "session limit" in text or "Not logged in" in text:
                print(f"SKIP {f.name}: harness message, not a reply", file=sys.stderr)
                continue
            sc = score(text)
            sc.update(cond=cond, id=s["id"])
            rows.append(sc)
            print(
                f"{cond:9} {s['id']:12} sent={sc['sentences']:2} em={sc['em_dash']} "
                f"bold={sc['bold_spans']} hdr={sc['headers']} bul={sc['bullets']} words={sc['words']}",
                flush=True,
            )
    (out / "scores.json").write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    print()
    print("| condition | n | words | sentences | em-dash | bold | headers | bullets | openers | closers | linter viol/100w |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for cond in conds:
        rs = [r for r in rows if r["cond"] == cond]
        n = len(rs)
        if not n:
            continue
        print(
            f"| {cond} | {n} | {sum(r['words'] for r in rs)/n:.0f} | {sum(r['sentences'] for r in rs)/n:.1f} | "
            f"{sum(r['em_dash'] for r in rs)} | {sum(r['bold_spans'] for r in rs)} | {sum(r['headers'] for r in rs)} | {sum(r['bullets'] for r in rs)} | "
            f"{sum(r['opener'] for r in rs)} | {sum(r['closer'] for r in rs)} | {sum(r['viol_per_100w'] for r in rs)/n:.2f} |"
        )


if __name__ == "__main__":
    main()
