# Simple Persian hooks

The Claude Code and Codex plugins include a `SessionStart` hook. The hook loads the Simple Persian writing rules when a session starts, resumes, clears, or compacts. You do not need to name the skill.

The hook needs Node.js. Both plugins run `src/hooks/simple-persian-activate.js` with the `node` command.

## Install

Claude Code:

```bash
claude plugin marketplace add VahidTa/SimplePersian
claude plugin install simple-persian@simple-persian
```

Codex:

```bash
codex plugin marketplace add VahidTa/SimplePersian
codex plugin add simple-persian@simple-persian
```

Codex asks you to review and trust the hook before its first run. Open `/hooks` to approve it.

## What the hook sends

The hook writes the fenced rule block of `prompts/system-prompt.md` to standard output. The page title, the paste instructions, and the word-budget variant stay out. The full skill, `skills/simple-persian/SKILL.md`, is longer, and Claude Code caps hook output at 10,000 characters. Output over the cap goes to a file and the model gets only a preview. The condensed rules fit, and the hook names the full skill path so the model can read it for a compliance check or strict mode.

Codex applies its own cap to hook context. The `additionalContextLimit: 0` setting in `.codex-plugin/hooks.json` turns off the spill-to-disk threshold. It does not remove the cap. The condensed rules fit under it.

If the hook cannot read the prompt file, it tries the next location. If every location fails, it prints a short fallback rule set and exits 0. The session still starts.

## Where each harness loads the hook

- Claude Code: the `hooks` field in `.claude-plugin/plugin.json`.
- Codex: `.codex-plugin/hooks.json`, named by the `hooks` field in `.codex-plugin/plugin.json`. The marketplace catalog is `.agents/plugins/marketplace.json`.

## Test

From the repository root:

```bash
node --test src/hooks/simple-persian-activate.test.js
```

## Advisory writing checks (Claude Code)

Two more hooks run under Claude Code, both advisory. Neither one blocks. Both hooks inspect the language first and silently exit 0 on English-only Markdown files and English-only replies:

- `PostToolUse` on `Write` and `Edit`: when the file is Markdown and contains Persian prose, `src/hooks/lint_hook.py` lints it with `evals/sp_lint.py` and prints a summary of violations to stderr.
- `Stop`: when `last_assistant_message` contains Persian text, the same script checks the reply register and returns a `systemMessage` if the reply uses em-dashes, bold spans, colloquialisms, slop words, or filler openers/closers.

Codex runs only the `SessionStart` hook. Test the checks with `python3 src/hooks/test_lint_hook.py`.

## What the file check skips

The `PostToolUse` check skips:

- Non-Markdown files and English-only Markdown files (fewer than 15 Persian letters outside code and headings).
- Every path under the Claude configuration directory (`CLAUDE_CONFIG_DIR`, falling back to `~/.claude`).
- Every path with a `.claude` directory component, such as agent memory files or skills.
- Every path that matches a glob in `SIMPLE_PERSIAN_LINT_EXCLUDE`.

A symlink does not defeat a skip. The check tests the absolute path in two forms, as written and with symlinks resolved.

`SIMPLE_PERSIAN_LINT_EXCLUDE` holds glob patterns separated by the platform path separator (`:` on Linux and macOS, `;` on Windows). Leading `~` expands to your home directory:

```bash
export SIMPLE_PERSIAN_LINT_EXCLUDE="$HOME/notes/*:*/CHANGELOG.md"
```

To turn the file check off, set the variable to `*`. The `Stop` reply check stays on for Persian replies.
