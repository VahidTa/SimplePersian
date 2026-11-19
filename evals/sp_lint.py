#!/usr/bin/env python3
"""Deterministic Simple Persian violation counter for benchmark runs and hooks.

Counts mechanical violations that regexes can catch: sentence length,
colloquial contractions, bureaucratic verbs/passives, banned modals/hedges,
Finglish verbs/nouns, semicolons, em-dashes, bad abbreviations, Persian
orthography defects (Arabic ي/ك, Latin comma/question mark, broken می space),
slop phrases, trailing conditions, and synonym rotation.

Known ceiling: this is a regex pass, not a morphological analyzer or parser.
It undercounts nuanced grammar issues and can miscount sentence bounds in
unusual Markdown. Numbers from this tool compare two texts run through the same
version; they are not a formal compliance verdict.

Usage:
  python3 sp_lint.py --type procedural file.md
  cat text.md | python3 sp_lint.py --type descriptive -
  python3 sp_lint.py --type descriptive --detail file.md
  python3 sp_lint.py --self-test
"""
import json
import pathlib
import re
import sys
from collections import Counter

# Persian letters, marks, and joiners excluding punctuation (، ؛ ؟) and digits.
FA_WORD_CHAR = r"\u0621-\u065f\u066e-\u06d3\u06d5\u200c\u200d"
WB_L = rf"(?<![{FA_WORD_CHAR}])"
WB_R = rf"(?![{FA_WORD_CHAR}])"

PERSIAN_LETTER = re.compile(r"[\u0621-\u064a\u067e\u0686\u0698\u06a9\u06af\u06cc]")

COLLOQUIAL = re.compile(
    WB_L
    + r"(?:میشه|می‌شه|نمیشه|نمی‌شه|بشه|نشه|می‌خواد|میخواد|نمی‌خواد|نمیخواد|"
    r"می‌تونه|میتونه|نمی‌تونه|نمیتونه|می‌کنه|میکنه|نمی‌کنه|نمیکنه|"
    r"می‌کنن|میکنن|می‌کنین|میکنین|بکنین|کنین|بزنین|بدین|بگیرین|"
    r"بفرستین|بخونین|بنویسین|می‌ره|میره|میاد|می‌یاد|میده|می‌ده|"
    r"نمی‌ده|نمیده|واسه|توی|چطوری|چجوری|اینجوری|اونجوری|اینا|اونا|"
    r"چیه|کدوم|هیچی|دیگه|بذار|بذارید|نذارید|می‌ذاره|میذاره|بگم|بگیم|بگین)"
    + WB_R
)

BUREAUCRATIC_VERB = re.compile(
    WB_L
    + r"(?:می‌باشد|می‌باشند|میباشد|میباشند|می‌گردد|می‌گردند|میگردد|میگردند|"
    r"گردید|گردیده|خواهد\s+گردید|می‌نماید|می‌نمایند|مینماید|مینمایند|"
    r"نمایید|نمائید|بفرمایید|فرمایید|"
    r"مورد\s+[\u0621-\u065f\u066e-\u06d3\u200c]+(?:\s+[\u0621-\u065f\u066e-\u06d3\u200c]+){0,2}\s+قرار\s+(?:می‌گیرد|گیرد|گرفت|دهید|داد|بگیرد)|"
    r"اقدام\s+به\s+[\u0621-\u065f\u066e-\u06d3\u200c]+(?:\s+[\u0621-\u065f\u066e-\u06d3\u200c]+){0,2}\s+(?:کنید|نمایید|می‌کند|کرد|می‌کنند|کردند)|"
    r"نسبت\s+به\s+[\u0621-\u065f\u066e-\u06d3\u200c]+(?:\s+[\u0621-\u065f\u066e-\u06d3\u200c]+){0,2}\s+اقدام|"
    r"صورت\s+(?:می‌پذیرد|پذیرفت|می‌گیرد|گرفت)|"
    r"انجام\s+(?:می‌گیرد|می‌پذیرد|پذیرفت)|"
    r"به\s+عمل\s+(?:می‌آید|آمد|آورید)|"
    r"توسط)"
    + WB_R
)

BANNED_MODAL = re.compile(
    WB_L
    + r"(?:ممکن\s+است|شاید|احتمالاً|احتمالا|بهتر\s+است|"
    r"توصیه\s+می‌شود|توصیه\s+میشود|پیشنهاد\s+می‌شود|پیشنهاد\s+میشود|"
    r"بایستی|می‌بایست|میبایست|لازم\s+است)"
    + WB_R
)

FINGLISH_VERB = re.compile(
    WB_L
    + r"(?:(?:چک|ران|فیکس|ست|دلیت|سیو|لاگین|ریستارت|اپدیت|آپدیت|لود|پارس|کانفیگ)"
    r"\s+(?:کنید|کنیم|کنند|کند|کرد|کردن|کرده|می‌کند|میکند|می‌شود|میشود|شد|شده)|"
    r"کانفیگ(?:ها|های|ِ)?|ارور(?:ها|های|ی)?|آپشن(?:ها|های)?|اپشن(?:ها|های)?)"
    + WB_R
)

BAD_ABBREV_LATIN = re.compile(r"(?<![A-Za-z])(e\.g\.|i\.e\.|etc\.?)(?=[\s,،)]|$)", re.I)
BAD_ABBREV_FA = re.compile(WB_L + r"(?:و\s*غیره|و\s*امثالهم|الخ)" + WB_R)

ARABIC_CHAR = re.compile(r"[\u064a\u0643]+")
LATIN_PUNCT = re.compile(r"[\u0621-\u065f\u066e-\u06d3\u06d5][,?]")
BROKEN_MI = re.compile(
    WB_L
    + r"ن?می[ \t]+(?:شود|شوند|شوی|شوید|شوم|شد|کند|کنند|کنی|کنید|کنم|کرد|"
    r"دهد|دهند|دهی|دهید|دهم|داد|تواند|توانند|توانی|توانید|توانم|توانست|"
    r"رود|روند|روی|روید|روم|رفت|آید|آیند|آیید|آمد|گیرد|گیرند|گیرید|گرفت|"
    r"سازد|ساخت|نویسد|نوشت|خواند|فرستد|فرستاد|بندد|بست|ماند|خواست|خواهد|"
    r"داند|دانست|گوید|گفت|گذارد|گذاشت|افتد|افتاد|برد|آورد|زند|زد|"
    r"دارد|داشت|بیند|دید|رسد|رسید|پردازد|یابد|یافت|افزاید|کاهد|پذیرد|"
    r"باشید|باشند|باشد)"
    + WB_R
)

SLOP_CORE_TERMS = [
    "به‌طور یکپارچه",
    "به‌راحتی",
    "به‌سادگی",
    "شایان ذکر است",
    "قدرتمند",
    "تحول‌آفرین",
    "حیاتی",
]
SLOP_TSV = pathlib.Path(__file__).resolve().parent / "slop.tsv"


def _term_to_regex(term):
    """Compile a Persian slop phrase allowing space/ZWNJ variation and optional he-hamza."""
    esc = re.escape(term)
    esc = esc.replace(r"\ ", r"[\u0654]?[\s\u200c]+")
    esc = esc.replace("\u200c", r"[\s\u200c]?")
    return esc


def slop_pattern():
    """Union of the measured core list and evals/slop.tsv (term, category, swap)."""
    terms = list(SLOP_CORE_TERMS)
    if SLOP_TSV.exists():
        for line in SLOP_TSV.read_text(encoding="utf-8").splitlines():
            term = line.split("\t")[0].strip()
            if term and term not in terms:
                terms.append(term)
    alts = "|".join(_term_to_regex(t) for t in terms)
    return re.compile(WB_L + "(?:" + alts + ")" + WB_R)


SLOP = slop_pattern()
TRAILING_COND = re.compile(rf"(?:[ \t]+|\n){WB_L}(اگر|در[ \t]+صورتی[ \t]+که|چنانچه){WB_R}")
LEADING_COND = re.compile(rf"^(?:حتی\s+)?(?:اگر|در\s+صورتی\s+که|چنانچه){WB_R}")
DASH = re.compile(
    r"—|(?<![\d\u06f0-\u06f9])–(?![\d\u06f0-\u06f9])"
    r"|(?<= )--(?= )|(?<=[^\s\d\u06f0-\u06f9]{2}) - (?=[^\s\d\u06f0-\u06f9]{2})"
)
SEMICOLON = re.compile(r"[;؛]")

ROTATION_SETS = [
    ("config-settings", re.compile(WB_L + r"(پیکربندی|تنظیمات|کانفیگ)(?:‌ها|های|ِ)?" + WB_R)),
    ("verify-confirm", re.compile(WB_L + r"(مطمئن\s+شوید|اطمینان\s+حاصل|صحت[\u200c ]?سنجی|ت[اأ]یید)(?:ِ|‌ها)?" + WB_R)),
    ("error-fault", re.compile(WB_L + r"(خطا|ارور|ایراد|اشکال)(?:‌ها|های|ی|ِ)?" + WB_R)),
]

LIMITS = {"procedural": 20, "descriptive": 25}

ALL_CATEGORIES = (
    "sentence_over_limit",
    "colloquial",
    "bureaucratic_verb",
    "banned_modal",
    "finglish_verb",
    "semicolon",
    "em_dash",
    "bad_abbrev",
    "orthography",
    "slop_word",
    "trailing_condition",
    "synonym_rotation",
)


def normalize_persian(text):
    """Normalize Arabic ي/ك to Persian ی/ک (1-to-1 length preserving)."""
    return text.replace("\u064a", "\u06cc").replace("\u0643", "\u06a9")


def strip_code(text):
    """Strip code blocks, inline code, headings, URLs, and table formatting while preserving line count."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    text = re.sub(r"`[^`\n]+`", " CODESPAN ", text)
    text = re.sub(r"^#+\s.*$", " ", text, flags=re.M)
    text = re.sub(r"https?://\S+", " URL ", text)
    text = re.sub(r"^\s*\|[\s:|-]+\|\s*$", " ", text, flags=re.M)
    text = re.sub(
        r"^\s*\|(.*)\|\s*$",
        lambda m: ". ".join(c.strip() for c in m.group(1).split("|") if c.strip()) + ". ",
        text,
        flags=re.M,
    )
    return text


def has_persian(text, min_chars=15):
    """Return True if prose (outside code and headings) has at least min_chars Persian letters."""
    prose = strip_code(text)
    return len(PERSIAN_LETTER.findall(prose)) >= min_chars


def sentences(text):
    """Split prose into sentence units, keeping list items as independent sentences."""
    text = re.sub(
        r"^\s*([-*]|(?:\d+|[\u06f0-\u06f9]+)\.)\s+(.*?)([.!؟?:])?\s*$",
        lambda m: m.group(2) + (m.group(3) or ".") + " ",
        text,
        flags=re.M,
    )
    parts = re.split(r"(?<=[.!؟?:])\s+", text)
    return [p.strip() for p in parts if len(p.strip().split()) >= 2]


def _normalize_stem(label, raw):
    stem = re.sub(r"\s+", " ", raw.strip())
    if label == "verify-confirm":
        stem = stem.replace("أ", "ا").replace("\u200c", " ")
    return stem


def _analyze(text, text_type):
    raw_body = strip_code(text)
    body = normalize_persian(raw_body)
    sents = sentences(body)
    limit = LIMITS[text_type]
    hits = []

    def add(category, m, snippet=None):
        line = body.count("\n", 0, m.start()) + 1
        hits.append({"category": category, "text": (snippet or m.group(0)).strip(), "line": line})

    def locate(sentence, search_from):
        start = body.find(sentence, search_from)
        return start if start != -1 else search_from

    def add_sentence(category, sentence, start):
        line = body.count("\n", 0, start) + 1
        text_out = sentence if len(sentence) <= 80 else sentence[:80] + "…"
        hits.append({"category": category, "text": text_out, "line": line})

    pos = 0
    lengths = []
    for s in sents:
        pos = locate(s, pos)
        n = len(s.split())
        lengths.append(n)
        if n > limit:
            add_sentence("sentence_over_limit", s, pos)
        m = TRAILING_COND.search(s)
        if m:
            line_start = s.rfind("\n", 0, m.start()) + 1
            if m.start() - line_start >= 4 and not LEADING_COND.match(s):
                add_sentence("trailing_condition", s, pos)
        pos += max(len(s), 1)

    for m in COLLOQUIAL.finditer(body):
        add("colloquial", m)
    for m in BUREAUCRATIC_VERB.finditer(body):
        add("bureaucratic_verb", m)
    for m in BANNED_MODAL.finditer(body):
        add("banned_modal", m)
    for m in FINGLISH_VERB.finditer(body):
        add("finglish_verb", m)
    for m in SEMICOLON.finditer(body):
        add("semicolon", m)
    for m in DASH.finditer(body):
        add("em_dash", m)
    for m in BAD_ABBREV_LATIN.finditer(body):
        add("bad_abbrev", m)
    for m in BAD_ABBREV_FA.finditer(body):
        add("bad_abbrev", m)
    for m in ARABIC_CHAR.finditer(raw_body):
        add("orthography", m)
    for m in LATIN_PUNCT.finditer(body):
        add("orthography", m)
    for m in BROKEN_MI.finditer(body):
        add("orthography", m)
    for m in SLOP.finditer(body):
        add("slop_word", m)
    for name, rx in ROTATION_SETS:
        seen = {}
        for m in rx.finditer(body):
            stem = _normalize_stem(name, m.group(1))
            seen.setdefault(stem, m)
        for m in list(seen.values())[1:]:
            add("synonym_rotation", m, f"{m.group(0)} ({name})")

    hits.sort(key=lambda h: h["line"])
    counts = {cat: 0 for cat in ALL_CATEGORIES}
    for h in hits:
        counts[h["category"]] += 1
    words = max(1, len(body.split()))
    return hits, counts, words, sents, lengths


def lint_detail(text, text_type):
    """Return every violation hit with category, matched text, and 1-based line number."""
    hits, _, _, _, _ = _analyze(text, text_type)
    return hits


def lint(text, text_type):
    """Return summary violation counts and metrics for procedural or descriptive prose."""
    _, counts, words, sents, lengths = _analyze(text, text_type)
    total = sum(counts.values())
    return {
        "type": text_type,
        "words": words,
        "sentences": len(sents),
        "mean_sentence_words": round(sum(lengths) / max(1, len(lengths)), 1),
        "longest_sentence_words": max(lengths, default=0),
        "violations": counts,
        "violations_total": total,
        "violations_per_100w": round(100.0 * total / words, 2),
    }


BOLD = re.compile(r"\*\*[^*\n]+\*\*")
HEADER = re.compile(r"^#{1,6}\s", re.M)
BULLET = re.compile(r"^\s*(?:[-*+]|\d+[.)]|[\u06f0-\u06f9]+[.)])\s", re.M)


def reader_check(text):
    """Count visible defects in a Persian chat reply.

    `sentences` is reported for reference and is not part of `visible_total`.
    """
    text = text.replace("\r\n", "\n")
    prose = re.sub(r"```.*?```", lambda m: "\n" * m.group(0).count("\n"), text, flags=re.S)
    prose = re.sub(r"`[^`\n]+`", " CODESPAN ", prose)
    prose_no_md = re.sub(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|[\u06f0-\u06f9]+[.)]\s|\|)", "", prose, flags=re.M)
    prose_no_md = re.sub(r"^\s*[\s:|-]+$", "", prose_no_md, flags=re.M)
    sents = [p for p in re.split(r"(?<=[.!؟?])[\"')\]]*\s+|\n+", prose_no_md) if len(p.strip().split()) >= 2]
    norm_prose = normalize_persian(prose)
    counts = {
        "sentences": len(sents),
        "em_dash": len(DASH.findall(prose)),
        "bold_spans": len(BOLD.findall(prose)),
        "headers": len(HEADER.findall(prose)),
        "bullets": len(BULLET.findall(prose)),
        "colloquial": len(COLLOQUIAL.findall(norm_prose)),
    }
    words = max(1, len(prose_no_md.split()))
    visible = counts["em_dash"] + counts["bold_spans"] + counts["headers"] + counts["bullets"]
    return {"type": "reply", "words": words, "counts": counts, "visible_total": visible}


SLOP_FIXTURE = """با استفاده از سازوکار قدرتمند و تحول‌آفرین ما، تلاش‌های ناموفق به صورت خودکار دوباره اجرا می‌گردد، به طوری که این فرآیند توسط تیم ما به طور یکپارچه طراحی شده است تا همه خطاها را به‌خوبی مدیریت کند و با سرعت بالا و قابلیت‌های فراوان در تمام محیط‌های عملیاتی و تولیدی بدون هیچ وقفه‌ای اجرا شود.
بهتر است شما تنظیمات را چک کنید؛ همچنین میشه گفت کانفیگِ زمان انتظار را ببینید، و غیره.
در صورتی که این مشکل ادامه داشت با پشتیبانی تماس بگیرید. با پشتیبانی تماس بگیرید اگر خطا ادامه داشت.
این يك خطای ساده است, و می شود آن را دید؟"""

CLEAN_FIXTURE = """سامانه بارگذاری ناموفق را دوباره اجرا می‌کند. این فرایند داده‌ها را درست نگه می‌دارد.

اگر خطا ادامه پیدا کرد، مطمئن شوید که گذرواژه درست است. سپس با پشتیبانی تماس بگیرید."""

ORTHO_FIXTURE = """این متن دارای ي عربی و ك عربی است.
در اینجا ویرگول لاتین, و علامت سوال لاتین? دیده می شود.
"""

DASH_FIXTURE = """استقرار شکست خورد — دیسک پر بود.
بارگذاری شکست خورد -- توکن منقضی شد.
تلاش دوباره شکست خورد - درگاه بسته بود.
از --force در محیط اصلی استفاده نکنید.
بازه 5 - 10 دقیقه است.
بازه ۵–۱۰ دقیقه و فصل 2024–2025 است.
روی تخته x - y = z بنویسید.
از پرچم `--config sqlpipe.yaml` استفاده کنید.
درپوش را بردارید:
   -   چهار پیچ را شل کنید.
"""

TABLE_FIXTURE = """\
| ستون اول | ستون دوم | ستون سوم |
|----------|----------|----------|
| متن کوتاه در خانه اول جدول برای بررسی دقیق | متن کوتاه در خانه دوم جدول | خانه سوم |
| داده بیشتر در این ردیف از جدول | داده دیگر در اینجا | مقدار پایانی |
"""

LIST_FIXTURE = """\
موردهای زیر در دسترس هستند:

- مورد نخست بدون نقطه در پایان خط اول
- مورد دوم بدون نقطه در پایان خط دوم
- مورد سوم بدون نقطه در پایان خط سوم

جمله بعدی متن است.
"""

CODEBLOCK_LINE_FIXTURE = """\
```python
def run():
    # می شود
    return 1
```
شما باید این فایل را بررسی نمایید.
"""

REPLY_FIXTURE = """**بله** — وضعیت بد است.

## چرا
- تاخیر بالا می‌رود.
- کاربرها منتظر می‌مانند.

اکنون آن را بررسی کنین. سپس مقیاس بدهید."""


def self_test():
    slop = lint(SLOP_FIXTURE, "procedural")
    clean = lint(CLEAN_FIXTURE, "procedural")
    dashes = lint(DASH_FIXTURE, "procedural")
    ortho = lint(ORTHO_FIXTURE, "descriptive")

    assert slop["violations"]["sentence_over_limit"] >= 1, slop
    assert slop["violations"]["colloquial"] >= 1, slop
    assert slop["violations"]["bureaucratic_verb"] >= 1, slop
    assert slop["violations"]["banned_modal"] >= 1, slop
    assert slop["violations"]["finglish_verb"] >= 1, slop
    assert slop["violations"]["semicolon"] == 1, slop
    assert slop["violations"]["bad_abbrev"] >= 1, slop
    assert slop["violations"]["orthography"] >= 3, slop
    assert slop["violations"]["slop_word"] >= 3, slop
    assert slop["violations"]["trailing_condition"] >= 1, slop
    assert slop["violations"]["synonym_rotation"] >= 1, slop
    assert clean["violations_total"] == 0, clean

    assert ortho["violations"]["orthography"] == 5, ortho
    assert dashes["violations"]["em_dash"] == 3, dashes

    r = reader_check(REPLY_FIXTURE)["counts"]
    assert (r["sentences"], r["em_dash"], r["bold_spans"], r["headers"], r["bullets"], r["colloquial"]) == (5, 1, 1, 1, 2, 1), r
    assert reader_check("بله. وضعیت بد است چون تاخیر بالا می‌رود. اکنون مقیاس بدهید.")["visible_total"] == 0

    tricky = "او گفت \"توقف کن.\" سپس خراب شد.\n\n```\n# عنوان نیست\n**ضخیم نیست**\n- فهرست نیست\n```\n"
    t = reader_check(tricky)["counts"]
    assert (t["sentences"], t["headers"], t["bold_spans"], t["bullets"]) == (2, 0, 0, 0), t

    cell = lint("| ستون | مقدار |\n|---|---|\n| بهتر است سرویس را اجرا کنید | درست |\n", "descriptive")["violations"]
    assert cell["banned_modal"] == 1 and cell["sentence_over_limit"] == 0, cell

    assert sentences("- پیچ‌ها را شل کنید.\n- سپس ادامه بدهید") == ["پیچ‌ها را شل کنید.", "سپس ادامه بدهید."]
    assert lint(TABLE_FIXTURE, "descriptive")["violations"]["sentence_over_limit"] == 0
    assert lint(LIST_FIXTURE, "descriptive")["violations"]["sentence_over_limit"] == 0

    assert has_persian("این یک متن فارسی است برای آزمایش.")
    assert not has_persian("This is pure English markdown without Persian prose.")
    assert not has_persian("# فقط یک عنوان\n\nThis body is English.")

    # Line number must remain exact after a multi-line fenced code block.
    cb_detail = lint_detail(CODEBLOCK_LINE_FIXTURE, "descriptive")
    assert len(cb_detail) == 1 and cb_detail[0]["line"] == 6 and cb_detail[0]["category"] == "bureaucratic_verb", cb_detail

    # Exact parity between lint_detail and lint counts.
    detail = lint_detail(SLOP_FIXTURE, "procedural")
    assert len(detail) == slop["violations_total"], (len(detail), slop["violations_total"])
    assert all(h["line"] >= 1 and h["text"] for h in detail), detail
    detail_counts = Counter(h["category"] for h in detail)
    assert detail_counts == {k: v for k, v in slop["violations"].items() if v}, (detail_counts, slop["violations"])

    print("self-test OK:", slop["violations_total"], "violations in slop fixture, 0 in clean")


USAGE = "usage: sp_lint.py [--type procedural|descriptive|reply] [--gate] [--detail] (FILE|-) | --self-test"


def main():
    args = sys.argv[1:]
    if "--self-test" in args:
        self_test()
        return 0
    gate = "--gate" in args
    if gate:
        args.remove("--gate")
    show_detail = "--detail" in args
    if show_detail:
        args.remove("--detail")
    text_type = "descriptive"
    if "--type" in args:
        i = args.index("--type")
        if i + 1 >= len(args):
            sys.exit("missing value after --type\n" + USAGE)
        text_type = args[i + 1]
        del args[i : i + 2]
    if text_type != "reply" and text_type not in LIMITS:
        sys.exit(f"unknown --type {text_type!r} (expected procedural, descriptive, or reply)\n{USAGE}")
    if len(args) != 1:
        sys.exit(USAGE)
    src = args[0]
    if src == "-":
        text = sys.stdin.read()
    else:
        try:
            with open(src, encoding="utf-8") as fh:
                text = fh.read()
        except OSError as err:
            sys.exit(str(err))
    if text_type == "reply":
        report = reader_check(text)
    else:
        report = lint(text, text_type)
        if show_detail:
            report["hits"] = lint_detail(text, text_type)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    total = report["visible_total"] if text_type == "reply" else report["violations_total"]
    return 1 if gate and total else 0


if __name__ == "__main__":
    sys.exit(main())
