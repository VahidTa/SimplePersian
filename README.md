<p align="center">
  <strong>Plain, unambiguous Persian technical prose instead of AI slop and bureaucratic padding.</strong>
</p>

<p align="center">
  An agent skill that makes LLMs write clear Persian technical docs and chat replies,<br>
  inspired by <a href="https://www.asd-ste100.org/">ASD-STE100 Simplified Technical English</a> and <a href="https://github.com/AminBlg/SimpleEnglish">AminBlg/SimpleEnglish</a>.<br>
  Plain Persian by default, controlled vocabulary on request. Applies only to Persian output.
</p>

<p align="center">
  <a href="README.fa.md"><img src="https://img.shields.io/badge/README-%D9%81%D8%A7%D8%B1%D8%B3%DB%8C-teal?style=flat" alt="Persian README"></a>
  <a href="https://agentskills.io"><img src="https://img.shields.io/badge/SKILL.md-open_standard-blue?style=flat" alt="Agent Skills"></a>
  <a href="skills/simple-persian/SKILL.md"><img src="https://img.shields.io/badge/version-1.0.0-blue?style=flat" alt="version 1.0.0"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-lightgrey?style=flat" alt="Apache-2.0"></a>
</p>

[نسخهٔ فارسی (README.fa.md)](README.fa.md)

Works in agents that read the [Agent Skills standard](https://agentskills.io): Claude Code, Cursor, VS Code Copilot, OpenAI Codex, Gemini CLI, Goose, OpenCode, and others. Zero external dependencies, Apache-2.0.

## Install

Any agent, with the [skills CLI](https://github.com/vercel-labs/skills):

```bash
npx skills add VahidTa/SimplePersian
```

This installs the skill only. It does not install the session hook or the output style below. Use the Claude Code plugin for those.

Claude Code plugin, with the `SessionStart`, `PostToolUse`, and `Stop` hooks plus the output style:

```bash
claude plugin marketplace add VahidTa/SimplePersian && claude plugin install simple-persian@simple-persian
```

The output style is named `simple-persian:simple-persian`. Select it with `/config` under Output style, or put `{"outputStyle": "simple-persian:simple-persian"}` in `~/.claude/settings.json`.

Codex plugin, with the `SessionStart` hook:

```bash
codex plugin marketplace add VahidTa/SimplePersian
codex plugin add simple-persian@simple-persian
```

Codex asks you to trust the hook before its first run. The hooks need Node.js (and Python 3 for the Claude Code `PostToolUse` and `Stop` advisory checks). Details in [`src/hooks/README.md`](src/hooks/README.md).

No skill support? Paste the rule block of [`prompts/system-prompt.md`](prompts/system-prompt.md) into your system prompt, `AGENTS.md`, or `.cursorrules`. The file ends with a short token-budget variant for tight context limits.

## Language scope

Developers who write Persian docs still run English sessions most of the time. Simple Persian is scoped so it activates only when writing, rewriting, or replying in Persian and never forces English sessions into Persian. The Claude Code `PostToolUse` and `Stop` hooks also detect Persian characters before linting, so English-only Markdown files and English replies are skipped silently.

## See it

Left is typical unedited AI Persian output. Right is the same content rewritten with Simple Persian rules.

<table>
<tr>
<th width="50%">Without skill</th>
<th width="50%">With skill</th>
</tr>
<tr>
<td valign="top" dir="rtl">

> ابزار sqlpipe یک راه‌حل قدرتمند و جامع است که به شما امکان می‌دهد به‌طور یکپارچه و بدون دردسر جداول Postgres را به S3 منتقل نمایید. قبل از شروع کار، بهتر است اطمینان حاصل کنید که دسترسی‌های AWS شما به‌درستی پیکربندی شده‌اند — این امر برای جلوگیری از خطاهای احتمالی بسیار حیاتی می‌باشد.

</td>
<td valign="top" dir="rtl">

> ابزار `sqlpipe` جدول‌های Postgres را به S3 کپی می‌کند و به یک فایل پیکربندی نیاز دارد.
>
> پیش از شروع، مطمئن شوید که گواهی‌های AWS شما درست هستند. اگر گواهی‌ها نادرست باشند، سرویس S3 بارگذاری را با خطای دسترسی رد می‌کند.

</td>
</tr>
</table>

More rewrites in [`examples/before-after.md`](examples/before-after.md): READMEs, troubleshooting guides, error messages, incident reports, and release notes.

## The rules

Two registers live in [`skills/simple-persian/SKILL.md`](skills/simple-persian/SKILL.md). The full 53-rule catalog adapted to Persian software prose lives in [`rule-catalog.md`](skills/simple-persian/references/rule-catalog.md) for check mode and strict mode.

The reply, every Persian chat answer:

| Rule | What it removes |
|---|---|
| Prose by default: lists or tables only when content has that shape, no bold | Walls of formatting around simple answers |
| First sentence answers directly | Preamble and question restatement |
| No em-dashes (`—`) | Spliced half-thoughts |
| Define concept terms in a few words at first use | Undefined technical jargon |
| Standard written Persian, no openers or closers | Colloquialisms, `سوال خوبی است!`, `امیدوارم مفید بوده باشد` |

The document: Persian docs, READMEs, runbooks, error messages, release notes:

| Rule | What it removes |
|---|---|
| Max 20 words per instruction (`ـید`), 25 per description | Run-on translated sentences |
| Condition before command, separated with `،` | Trailing `... اگر خطا داد` that readers notice too late |
| Active voice, simple tenses (no `توسط` passive, no `گردید`) | Hidden actors and bureaucratic passives |
| No hedging (`ممکن است`, `شاید`, `بهتر است`, `توصیه می‌شود`, `لازم است`) | Ambiguous requirements; keep `باید` and `می‌توانید` |
| Standard orthography (`ی`, `ک`, `،`, `؟`, ZWNJ like `می‌شود`, `فایل‌ها`) | Arabic `ي`/`ك`, Latin `,`/`?`, broken `می شود` |
| No colloquialisms, bureaucratic verbs (`می‌باشد`, `نمایید`), or Finglish (`چک کنید`, `کانفیگ`) | Spoken/office clutter and lazy Finglish verbs |
| One word = one meaning across the whole document; max 3-noun ezafe chains | `پیکربندی`/`تنظیمات`/`کانفیگ` rotation and dense noun chains |
| State the fact, not its importance; no bold lead-ins or em-dashes | `به‌طور یکپارچه`, `شایان ذکر است`, `قدرتمند`, `نه تنها X، بلکه Y` |

Two modes. Plain, the default, enforces all of the rules above. Strict adds the controlled Persian verb and connector discipline from [`strict-vocabulary.md`](skills/simple-persian/references/strict-vocabulary.md) when you ask for strict mode, controlled Persian, STE, ASD-STE100, or compliance. The chat reply stays Plain in every mode.

## Linter and evaluations

`evals/sp_lint.py` is a zero-dependency Python linter that checks Persian documents and chat replies for mechanical violations (sentence length, colloquialisms, bureaucratic verbs, banned modals, Finglish, semicolons, em-dashes, bad abbreviations, Persian orthography, slop phrases from `evals/slop.tsv`, trailing conditions, and synonym rotation).

```bash
python3 evals/sp_lint.py --self-test
python3 evals/sp_lint.py --type descriptive --detail path/to/doc.md
python3 evals/sp_lint.py --type reply path/to/reply.txt
```

Benchmark runners and pressure tests live in `evals/`:

- [`evals/run_bench.py`](evals/run_bench.py): runs the 8 Persian writing tasks in [`evals/scenarios.json`](evals/scenarios.json) via headless `claude -p`.
- [`evals/run_reply_bench.py`](evals/run_reply_bench.py): runs the 8 Persian reply scenarios in [`evals/reply_scenarios.json`](evals/reply_scenarios.json).
- [`evals/pressure-tests.md`](evals/pressure-tests.md): manual prompt pressure tests and pass checklists.

## FAQ

Does this make text ASD-STE100 certified? No. ASD-STE100 covers English only, and no tool guarantees formal compliance. Simple Persian adapts the structural clarity principles of ASD-STE100 to Persian technical writing.

Will Persian docs sound too stiff or robotic? They sound clear, direct, and unambiguous. Keep literary voice and persuasion for blogs and marketing pages.

Why not just prompt "write simply in Persian"? "Simply" is vague; agents still emit bureaucratic verbs, colloquialisms, Arabic `ي`/`ك`, and 40-word sentences. Concrete rules and mechanical self-checks give agents an explicit spec.

## Contributing

Open an issue for questions, false positives in `evals/sp_lint.py`, or new Persian slop patterns. Before opening a pull request, run:

```bash
python3 evals/sp_lint.py --self-test
node --test src/hooks/simple-persian-activate.test.js
python3 src/hooks/test_lint_hook.py
```

## Credits and license

Inspired by [AminBlg/SimpleEnglish](https://github.com/AminBlg/SimpleEnglish) and the structural discipline of [ASD-STE100 Simplified Technical English](https://www.asd-ste100.org/). This is an independent project and is not affiliated with or endorsed by ASD, STEMG, or `AminBlg/SimpleEnglish`.

Licensed under the [Apache License 2.0](LICENSE).
