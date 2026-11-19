import json
import os
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
HOOK = HERE / "lint_hook.py"
CLEAN_ENV = {"CLAUDE_CONFIG_DIR": "/nonexistent/claude-config", "SIMPLE_PERSIAN_LINT_EXCLUDE": ""}
SLOP_FA = "بهتر است شما به سادگی این ابزار قدرتمند را چک کنید که به صورت خودکار توسط سیستم اجرا می‌گردد.\n"


def run(event, env=None):
    r = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(event),
        capture_output=True,
        text=True,
        env={**os.environ, **CLEAN_ENV, **(env or {})},
    )
    return r.returncode, r.stdout, r.stderr


def write_file(directory, content, name="notes.md"):
    path = pathlib.Path(directory, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)


def post(path, **event):
    return {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {"file_path": path}, **event}


def test_post_tool_use_flags_a_slop_persian_markdown_file():
    with tempfile.TemporaryDirectory() as d:
        code, out, err = run(post(write_file(d, SLOP_FA)))
    assert code == 2 and "Simple Persian violations" in err, (code, err)


def test_post_tool_use_prints_the_offending_text_and_line_number():
    with tempfile.TemporaryDirectory() as d:
        path = write_file(d, "# عنوان\n\nبهتر است این فایل را بررسی نمایید.\n")
        code, out, err = run(post(path))
    assert code == 2, (code, err)
    assert "line 3, banned_modal: بهتر است" in err, err
    assert "line 3, bureaucratic_verb: نمایید" in err, err


def test_post_tool_use_ignores_clean_persian_and_non_markdown():
    with tempfile.TemporaryDirectory() as d:
        clean_md = write_file(d, "مهاجرت را اجرا کنید. سپس سرویس را دوباره راه‌اندازی کنید.\n", "clean.md")
        py_file = write_file(d, "print('سلام دنیا')\n", "x.py")
        assert run(post(clean_md))[0] == 0
        assert run(post(py_file))[0] == 0


def test_post_tool_use_skips_english_only_markdown_files():
    with tempfile.TemporaryDirectory() as d:
        en_md = write_file(d, "You should simply leverage this robust tool — it's super helpful.\n", "en.md")
        code, out, err = run(post(en_md))
    assert code == 0 and err == "", (code, err)


def test_post_tool_use_skips_the_claude_config_dir():
    with tempfile.TemporaryDirectory() as d:
        path = write_file(pathlib.Path(d, "projects", "repo", "memory"), SLOP_FA, "MEMORY.md")
        assert run(post(path))[0] == 2, "a Persian memory file outside any config dir still lints"
        assert run(post(path), env={"CLAUDE_CONFIG_DIR": d})[0] == 0


def test_post_tool_use_skips_a_dot_claude_directory():
    with tempfile.TemporaryDirectory() as d:
        path = write_file(pathlib.Path(d, ".claude", "agent-memory", "reviewer"), SLOP_FA, "MEMORY.md")
        assert run(post(path))[0] == 0


def test_post_tool_use_honours_the_exclude_globs():
    with tempfile.TemporaryDirectory() as d:
        path = write_file(d, SLOP_FA)
        assert run(post(path))[0] == 2
        globs = os.pathsep.join(["~/no-such-file.md", f"{d}/*.md"])
        assert run(post(path), env={"SIMPLE_PERSIAN_LINT_EXCLUDE": globs})[0] == 0


def test_post_tool_use_resolves_a_relative_path_against_the_event_cwd():
    with tempfile.TemporaryDirectory() as d:
        write_file(d, SLOP_FA)
        assert run(post("notes.md", cwd=d))[0] == 2


def test_post_tool_use_lints_a_path_that_escapes_a_dot_claude_directory():
    with tempfile.TemporaryDirectory() as d:
        write_file(d, SLOP_FA)
        pathlib.Path(d, ".claude").mkdir()
        assert run(post(str(pathlib.Path(d, ".claude", "..", "notes.md"))))[0] == 2


def test_post_tool_use_skips_a_symlink_into_a_dot_claude_directory():
    with tempfile.TemporaryDirectory() as d:
        link = pathlib.Path(d, "notes.md")
        link.symlink_to(write_file(pathlib.Path(d, ".claude"), SLOP_FA, "MEMORY.md"))
        assert run(post(str(link)))[0] == 0


def test_post_tool_use_skips_a_symlinked_dot_claude_directory():
    with tempfile.TemporaryDirectory() as d:
        write_file(pathlib.Path(d, "dotfiles"), SLOP_FA, "MEMORY.md")
        pathlib.Path(d, ".claude").symlink_to(pathlib.Path(d, "dotfiles"))
        assert run(post(str(pathlib.Path(d, ".claude", "MEMORY.md"))))[0] == 0


def test_post_tool_use_matches_a_glob_through_a_symlinked_directory():
    with tempfile.TemporaryDirectory() as d:
        write_file(pathlib.Path(d, "store"), SLOP_FA)
        pathlib.Path(d, "notes").symlink_to(pathlib.Path(d, "store"))
        path = str(pathlib.Path(d, "notes", "notes.md"))
        assert run(post(path))[0] == 2
        assert run(post(path), env={"SIMPLE_PERSIAN_LINT_EXCLUDE": f"{d}/notes/*"})[0] == 0


def test_stop_flags_slop_persian_reply_and_never_blocks():
    bad = "سوال خوبی است! **نکته** — این روش قدرتمند میشه. امیدوارم این توضیح مفید بوده باشد."
    code, out, err = run({"hook_event_name": "Stop", "last_assistant_message": bad})
    assert code == 0 and "systemMessage" in out, (code, out)
    msg = json.loads(out)["systemMessage"]
    assert "opener" in msg and "closer" in msg and "slop" in msg and "bold" in msg and "em-dash" in msg and "colloquialism" in msg, msg


def test_stop_skips_english_only_replies():
    en = "Great question! **Here** — this robust solution helps. I hope this helps!"
    code, out, err = run({"hook_event_name": "Stop", "last_assistant_message": en})
    assert code == 0 and out.strip() == "", (code, out)


def test_stop_is_silent_on_a_clean_persian_reply():
    clean = "ساخت به دلیل پر بودن دیسک شکست خورد. دو گیگابایت فضا آزاد کنید و دوباره اجرا کنید."
    code, out, err = run({"hook_event_name": "Stop", "last_assistant_message": clean})
    assert code == 0 and out.strip() == "", (code, out)


def test_garbage_stdin_exits_zero():
    r = subprocess.run([sys.executable, str(HOOK)], input="not json", capture_output=True, text=True)
    assert r.returncode == 0


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
