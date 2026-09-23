"""Find, and optionally replace, em dashes inside the text of JavaScript strings.

WHY THIS EXISTS
---------------
Brand.md section 7 bans em dashes on every surface a seller reads. The app's
own screens are built from string and template literals in smart.js, which had
about 264 lines of them. Doing that by hand across 12,000 lines is how a typo
lands in live copy, and a plain search-and-replace would also rewrite code
comments, which are not copy. So this walks the file the way a JS parser does
and only ever touches text that is inside a string.

WHAT IT UNDERSTANDS
  * '...' and "..." strings, with escapes
  * `...` template literals, including ${ ... } holes, nested to any depth
  * // and /* */ comments (left alone)
  * regex literals, told apart from division by what comes before the slash,
    because /[&<>"']/g must not be read as the start of a string

NEVER TOUCHED: a string passed to .split(), .indexOf(), .includes(),
.startsWith(), .endsWith(), .replace() or .replaceAll(). Those are matching
something another piece of code wrote (the first run of this tool rewrote
.split(" \u2014 ") on task titles the server still writes with an em dash,
which quietly stopped the deadline splitting off). They are reported instead.

HOW TEXT IS REWRITTEN (only with --write)
  * " — " between words becomes ", "
  * a lone "—" used as a "no value" marker becomes the en dash "–"
  * anything else is reported and left for a person to decide

Run:  python scripts/sweep_em_dashes.py path/to/file.js            report only
      python scripts/sweep_em_dashes.py path/to/file.js --write    rewrite
"""
from __future__ import annotations

import io
import re
import sys

EM = "—"
EN = "–"
_REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_WORDS = {"return", "typeof", "case", "do", "else", "in", "of", "yield",
                "await", "void", "delete", "throw", "new", "instanceof"}


def scan(src: str):
    """Yield (kind, start, end) spans: kind is 'code', 'str' or 'comment'.

    Only the TEXT of a string is reported as 'str'; the quote marks, and the
    ${ } holes of a template (which are code again), are 'code'.
    """
    i, n = 0, len(src)
    spans = []
    stack = []            # template nesting: each entry is the brace depth inside ${ }
    last_sig, last_word = "", ""
    code_start = 0

    def flush_code(upto):
        if upto > code_start:
            spans.append(("code", code_start, upto))

    while i < n:
        c = src[i]
        # ---- inside a ${ } hole, a closing brace may end the hole ----------
        if stack and c == "}" and stack[-1] == 0:
            stack.pop()
            i += 1
            # back into the template's text
            flush_code(i)
            j = i
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "`":
                    break
                if src[j] == "$" and j + 1 < n and src[j + 1] == "{":
                    break
                j += 1
            spans.append(("str", i, j))
            if j < n and src[j] == "`":
                code_start = j
                i = j + 1
                last_sig = "`"
            else:
                stack.append(0)
                code_start = j
                i = j + 2
                last_sig = "{"
            continue
        if stack and c == "{":
            stack[-1] += 1
        elif stack and c == "}":
            stack[-1] -= 1
        # ---- comments -------------------------------------------------------
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            flush_code(i)
            j = src.find("\n", i)
            j = n if j < 0 else j
            spans.append(("comment", i, j))
            i = code_start = j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            flush_code(i)
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            spans.append(("comment", i, j))
            i = code_start = j
            continue
        # ---- regex literal ----------------------------------------------------
        if c == "/" and (last_sig in _REGEX_AFTER or last_sig == "" or last_word in _REGEX_WORDS):
            j, in_class = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    in_class = True
                elif src[j] == "]":
                    in_class = False
                elif src[j] == "/" and not in_class:
                    break
                j += 1
            j += 1
            while j < n and (src[j].isalnum()):
                j += 1
            i = j
            last_sig, last_word = "/", ""
            continue
        # ---- strings ----------------------------------------------------------
        if c in ("'", '"'):
            flush_code(i + 1)
            j = i + 1
            while j < n and src[j] != c and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            spans.append(("str", i + 1, j))
            code_start = j
            i = j + 1
            last_sig, last_word = c, ""
            continue
        if c == "`":
            flush_code(i + 1)
            j = i + 1
            while j < n:
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "`":
                    break
                if src[j] == "$" and j + 1 < n and src[j + 1] == "{":
                    break
                j += 1
            spans.append(("str", i + 1, j))
            if j < n and src[j] == "`":
                code_start = j
                i = j + 1
                last_sig = "`"
            else:
                stack.append(0)
                code_start = j
                i = j + 2
                last_sig = "{"
            last_word = ""
            continue
        # ---- plain code: remember what the last meaningful token was --------
        if not c.isspace():
            if c.isalnum() or c in "_$":
                j = i
                while j < n and (src[j].isalnum() or src[j] in "_$"):
                    j += 1
                last_word = src[i:j]
                last_sig = "a"
                i = j
                continue
            last_sig, last_word = c, ""
        i += 1
    flush_code(n)
    return spans


def _between(m: re.Match) -> str:
    """What a " — " between words becomes.

    "Draft — only you can see it" is a label and its explanation, and reads
    best as "Draft: only you can see it". Mid-sentence, "the smallest quantity
    they will sell — 0 if none" reads best with a comma. So: a colon when the
    clause before the dash is a short capitalised label, a comma otherwise.
    """
    if m.start() == 0:
        return ", "                                # continues text before a ${ } hole
    seg = m.string[:m.start()]
    cut = max(seg.rfind(">"), seg.rfind(". "), seg.rfind("("), seg.rfind("\n"), seg.rfind('"'))
    clause = seg[cut + 1:].strip()
    words = clause.split()
    return ": " if 1 <= len(words) <= 3 and clause[:1].isupper() else ", "


def rewrite(text: str) -> tuple[str, list[str]]:
    """Replace em dashes in one piece of string text. Returns (new, unhandled)."""
    if EM not in text:
        return text, []
    if text.strip() == EM:
        return text.replace(EM, EN), []           # "no value" marker
    # "— pick an item —" and "— not linked to a product yet —" in an <option>
    out = re.sub(f">{EM} ([^<]+?) {EM}<",
                 lambda m: ">" + m.group(1)[:1].upper() + m.group(1)[1:] + "<", text)
    out = out.replace(f">{EM}<", f">{EN}<")        # an empty cell or option
    out = out.replace(f'placeholder="{EM}"', f'placeholder="{EN}"')
    if out.startswith(f"{EM} ") and "\n" not in out and "<" not in out:
        out = f"({out[2:]})"                       # a hint that opens with a dash
    # a muted note after a tag: <span>— sells out at zero</span> -> (sells out at zero)
    out = re.sub(f"(>[ \\t]*){EM} ([^<]*?)([ \\t]*<)",
                 lambda m: f"{m.group(1)}({m.group(2)}){m.group(3)}", out)
    out = re.sub(f" {EM}(\\r?\\n)", ",\\1", out)   # a dash at a line break
    out = re.sub(f" {EM} ", _between, out)
    left = [out] if EM in out else []
    return out, left


_MATCHERS = (".split(", ".indexOf(", ".lastIndexOf(", ".includes(", ".startsWith(",
             ".endsWith(", ".replace(", ".replaceAll(")


def _is_matcher_arg(src: str, a: int) -> bool:
    """Is the string starting at `a` an argument to a matching method?"""
    before = src[max(0, a - 16):a - 1].rstrip()
    return before.endswith(_MATCHERS) or any(before.endswith(m.rstrip("(")) for m in _MATCHERS)


def run(path: str, write: bool) -> int:
    src = io.open(path, encoding="utf-8").read()
    spans = scan(src)
    pieces, changed, unhandled, comment_em = [], 0, [], 0
    for kind, a, b in spans:
        chunk = src[a:b]
        if kind == "str" and EM in chunk and _is_matcher_arg(src, a):
            unhandled.append((src.count("\n", 0, a) + 1, "left alone, used for matching: " + chunk))
        elif kind == "str" and EM in chunk:
            new, left = rewrite(chunk)
            changed += chunk.count(EM) - new.count(EM)
            unhandled += [(src.count("\n", 0, a) + 1, x.strip()[:90]) for x in left]
            chunk = new
        elif kind == "comment":
            comment_em += chunk.count(EM)
        pieces.append(chunk)
    # Anything between spans (quote marks, regex bodies) is copied as is.
    out, pos = [], 0
    for (kind, a, b), piece in zip(spans, pieces):
        out.append(src[pos:a])
        out.append(piece)
        pos = b
    out.append(src[pos:])
    new_src = "".join(out)
    print(f"{path}: {changed} em dashes in strings rewritten, "
          f"{len(unhandled)} strings need a person, {comment_em} in comments left alone")
    for line, text in unhandled[:60]:
        print(f"  line {line}: {text}")
    if write:
        io.open(path, "w", encoding="utf-8", newline="\n").write(new_src)
    return len(unhandled)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(1 if run(args[0], "--write" in sys.argv) and "--strict" in sys.argv else 0)
