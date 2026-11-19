#!/usr/bin/env python3
"""Benchmark the simple-persian skill across models.

For each model x condition x scenario, runs a headless `claude -p` call,
lints the output with sp_lint.py, and aggregates to results.json +
RESULTS.md. Resumable: existing raw result files are skipped.

Requires: Claude Code CLI logged in. No API key needed.

Usage:
  python3 evals/run_bench.py                 # full matrix
  python3 evals/run_bench.py --smoke         # 1 model x 2 scenarios
  python3 evals/run_bench.py --report-only   # rebuild RESULTS.md from raw/
  python3 evals/run_bench.py --judge         # blind pairwise judge pass
  python3 evals/run_bench.py --effort low    # override effort level
  python3 evals/run_bench.py --results-dir D # write to D instead of evals/results/
"""
import json
import pathlib
import subprocess
import sys
import time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sp_lint  # noqa: E402

SKILL = HERE.parent / "skills" / "simple-persian" / "SKILL.md"
RESULTS = HERE / "results"
RAW = RESULTS / "raw"
MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-6",
]
JUDGE_MODEL = "claude-opus-4-6"
CONDITIONS = ("baseline", "skill")
DEFAULT_EFFORT = "low"


def call_claude(prompt, model, timeout=300, effort=DEFAULT_EFFORT):
    cmd = [
        "claude", "-p", prompt, "--model", model,
        "--output-format", "json", "--setting-sources", "",
        "--disallowedTools", "Bash,Read,Write,Edit,Glob,Grep,WebFetch,WebSearch",
    ]
    if effort:
        cmd += ["--effort", effort]
    t0 = time.time()
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, cwd="/tmp")
    if proc.returncode != 0:
        raise RuntimeError(f"{model}: {proc.stderr[:300]}")
    env = json.loads(proc.stdout)
    if isinstance(env, list):
        env = next(m for m in env if m.get("type") == "result")
    if env.get("is_error"):
        raise RuntimeError(f"{model}: {str(env.get('result'))[:300]}")
    usage = env.get("usage", {})
    return {
        "text": env.get("result", ""),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "thinking_tokens": usage.get("output_tokens_details", {}).get("thinking_tokens"),
        "effort": effort,
        "duration_ms": env.get("duration_ms", int(1000 * (time.time() - t0))),
        "cost_usd": env.get("total_cost_usd"),
    }


def build_prompt(scenario, condition, skill_text):
    if condition == "baseline":
        return scenario["prompt"]
    return (
        "Follow these Persian writing instructions exactly, including the self-check step:\n\n"
        + skill_text
        + "\n\n---\n\nTask: "
        + scenario["prompt"]
        + "\n\nReturn only the final Persian text, with no rule commentary."
    )


def generate(models, scenarios, effort):
    skill_text = SKILL.read_text(encoding="utf-8")
    RAW.mkdir(parents=True, exist_ok=True)
    todo = [(m, c, s) for m in models for c in CONDITIONS for s in scenarios]
    for i, (model, cond, sc) in enumerate(todo, 1):
        out = RAW / f"{model}__{cond}__{sc['id']}.json"
        if out.exists():
            prior = json.loads(out.read_text(encoding="utf-8")).get("effort")
            if prior is not None and prior != effort:
                print(f"  kept {out.name}: recorded at effort {prior}", flush=True)
            continue
        print(f"[{i}/{len(todo)}] {model} {cond} {sc['id']}", flush=True)
        try:
            res = call_claude(build_prompt(sc, cond, skill_text), model, effort=effort)
        except Exception as exc:  # noqa: BLE001
            print(f"  FAILED: {exc}", flush=True)
            continue
        res.update(model=model, condition=cond, scenario=sc["id"], type=sc["type"])
        res["lint"] = sp_lint.lint(res["text"], sc["type"])
        out.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
        time.sleep(2)


def aggregate():
    rows = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(RAW.glob("*.json")) if "__judge__" not in p.name]
    per_model = {}
    for r in rows:
        m = per_model.setdefault(r["model"], {c: [] for c in CONDITIONS})
        m[r["condition"]].append(r)
    table = []
    seen_models = sorted(per_model.keys(), key=lambda x: (MODELS.index(x) if x in MODELS else len(MODELS), x))
    for model in seen_models:
        row = {"model": model}
        for cond in CONDITIONS:
            runs = per_model[model][cond]
            if not runs:
                continue
            row[f"{cond}_viol_per_100w"] = round(sum(r["lint"]["violations_per_100w"] for r in runs) / len(runs), 2)
            row[f"{cond}_mean_sentence"] = round(sum(r["lint"]["mean_sentence_words"] for r in runs) / len(runs), 1)
            row[f"{cond}_output_tokens"] = round(sum(r["output_tokens"] or 0 for r in runs) / len(runs))
            row[f"{cond}_n"] = len(runs)
        b, s = row.get("baseline_viol_per_100w"), row.get("skill_viol_per_100w")
        if b:
            row["reduction_pct"] = round(100 * (b - s) / b, 1)
        table.append(row)
    meta = {
        "efforts": sorted({r.get("effort") or "unrecorded" for r in rows}),
        "max_thinking_tokens": max((r.get("thinking_tokens") or 0 for r in rows), default=0),
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "results.json").write_text(
        json.dumps({"generated": time.strftime("%Y-%m-%d"), "models": table, "runs": len(rows), **meta}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return table, meta


def judge_summary():
    files = sorted(RAW.glob("*__judge__*.json"))
    per_model, wins, ties, losses = {}, 0, 0, 0
    skill_sum = base_sum = valid = recorded_effort = 0
    for p in files:
        d = json.loads(p.read_text(encoding="utf-8"))
        recorded_effort += "judge_effort" in d
        o1, o2 = d["order1_base_first"], d["order2_skill_first"]
        if not o1 or not o2:
            continue
        skill = (o1["b_score"] + o2["a_score"]) / 2
        base = (o1["a_score"] + o2["b_score"]) / 2
        valid += 1
        skill_sum += skill
        base_sum += base
        w = per_model.setdefault(d["model"], [0, 0, 0])
        if skill > base:
            wins += 1
            w[0] += 1
        elif skill == base:
            ties += 1
            w[1] += 1
        else:
            losses += 1
            w[2] += 1
    if not valid:
        return []
    lines = [
        "",
        "## Judge pass (blind pairwise)",
        "",
        f"For each model x scenario pair, {JUDGE_MODEL} scored the baseline text and",
        "the skill text on a 0-10 rubric, twice in both orders.",
        "",
        f"Result: the skill output scored higher in {wins} of {valid} pairs, tied in {ties}, and lost in {losses}. "
        f"Mean rubric score: {skill_sum / valid:.2f} with the skill, {base_sum / valid:.2f} without.",
        "",
        "| Model | Skill wins | Ties | Losses |",
        "|---|---|---|---|",
    ]
    for m, (w, t, l) in sorted(per_model.items()):
        lines.append(f"| {m} | {w} | {t} | {l} |")
    lines += [
        "",
        f"Recorded judge_effort: {recorded_effort} of {len(files)} judge files.",
    ]
    return lines


def report(table, meta, effort):
    ok = [r for r in table if "reduction_pct" in r]
    avg = round(sum(r["reduction_pct"] for r in ok) / max(1, len(ok)), 1)
    n = sum(r.get("baseline_n", 0) + r.get("skill_n", 0) for r in table)
    lines = [
        "# Benchmark results",
        "",
        f"**{avg}% fewer Simple Persian linter violations per 100 words with the skill, across "
        f"{len(ok)} model(s) ({n} generations).**",
        "",
        "| Model | Baseline viol/100w | Skill viol/100w | Reduction | Baseline sent. len | Skill sent. len | Output tok (base->skill) |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for r in ok:
        lines.append(
            f"| {r['model']} | {r['baseline_viol_per_100w']} | {r['skill_viol_per_100w']} "
            f"| {r['reduction_pct']}% | {r['baseline_mean_sentence']} | {r['skill_mean_sentence']} "
            f"| {r['baseline_output_tokens']} -> {r['skill_output_tokens']} |"
        )
    lines += judge_summary()
    lines += [
        "",
        "## Method notes",
        "",
        "- `sp_lint.py` is a regex pass, not a morphological grammar parser.",
        f"- Reasoning effort pinned to `{effort}`.",
        f"- Max `thinking_tokens` observed: {meta['max_thinking_tokens']}.",
        "",
        "Reproduce: `python3 evals/run_bench.py` (requires Claude Code CLI logged in).",
    ]
    (RESULTS / "RESULTS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:12]))


def judge(scenarios, effort):
    import itertools
    rubric = (
        "Score the two Persian technical texts A and B on: (1) clarity and lack of ambiguity "
        "for a reader outside the field, (2) every instruction is concrete and executable, "
        "(3) standard written Persian free of AI slop, bureaucratic padding, and colloquialisms. "
        'Reply with JSON only: {"a_score": 0-10, "b_score": 0-10}'
    )
    for model, sc in itertools.product(MODELS, scenarios):
        pair = {}
        for cond in CONDITIONS:
            p = RAW / f"{model}__{cond}__{sc['id']}.json"
            if p.exists():
                pair[cond] = json.loads(p.read_text(encoding="utf-8"))["text"]
        if len(pair) != 2:
            continue
        out = RAW / f"{model}__judge__{sc['id']}.json"
        if out.exists():
            continue
        scores = []
        for a, b in ((pair["baseline"], pair["skill"]), (pair["skill"], pair["baseline"])):
            res = call_claude(f"{rubric}\n\nTEXT A:\n{a}\n\nTEXT B:\n{b}", JUDGE_MODEL, effort=effort)
            try:
                scores.append(json.loads(res["text"].strip().strip("`json\n")))
            except json.JSONDecodeError:
                scores.append(None)
        out.write_text(
            json.dumps(
                {
                    "model": model,
                    "scenario": sc["id"],
                    "judge_effort": effort,
                    "order1_base_first": scores[0],
                    "order2_skill_first": scores[1],
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"judged {model} {sc['id']}", flush=True)


def flag(name, default=None):
    for i, a in enumerate(sys.argv):
        if a == name and i + 1 < len(sys.argv):
            return sys.argv[i + 1]
        if a.startswith(name + "="):
            return a.split("=", 1)[1]
    return default


def main():
    global RESULTS, RAW
    scenarios = json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))
    effort = flag("--effort", DEFAULT_EFFORT)
    if rd := flag("--results-dir"):
        RESULTS = pathlib.Path(rd).resolve()
        RAW = RESULTS / "raw"
    if "--smoke" in sys.argv:
        generate([MODELS[0]], scenarios[:2], effort)
    elif "--judge" in sys.argv:
        judge(scenarios, effort)
        return
    elif "--report-only" not in sys.argv:
        generate(MODELS, scenarios, effort)
    report(*aggregate(), effort)


if __name__ == "__main__":
    main()
