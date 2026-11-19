# Changelog

## 1.0.0, 2026-11-19

- Initial release of Simple Persian (`VahidTa/SimplePersian`), inspired by `AminBlg/SimpleEnglish` and ASD-STE100 Issue 9.
- Added `skills/simple-persian/SKILL.md` with two registers (Document and Reply) and two modes (Plain and Strict), plus four Persian reference guides (`rule-catalog.md`, `strict-vocabulary.md`, `word-swaps.md`, `use-cases.md`).
- Added standalone prompt (`prompts/system-prompt.md`), Claude Code output style (`output-styles/simple-persian.md`), and Persian examples (`examples/before-after.md`).
- Added Claude Code and Codex plugin manifests (`.claude-plugin/`, `.codex-plugin/`, `.agents/plugins/`) and language-aware hooks (`src/hooks/simple-persian-activate.js`, `src/hooks/lint_hook.py`) that apply only to Persian text.
- Added deterministic Persian linter (`evals/sp_lint.py`), slop lexicon (`evals/slop.tsv`), document/reply scenarios, pressure tests, and benchmark runners.
