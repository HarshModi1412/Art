"""Rendering for the legal pages, kept apart from the words themselves.

legal.py holds the text and the rules it comes from. This turns that structure
into a page. Splitting them means the wording can be reviewed by a person who
does not read Python, and the page can be restyled without touching a policy.

Three properties this rendering has to have, and they are the reason it is
hand-written rather than pulled from a template library:

  * **No third-party requests.** No Google Fonts, no CDN, no analytics on a
    legal page. A privacy policy that leaks your IP address to three companies
    while you read it is its own punchline, and the Munich ruling on embedded
    Google Fonts makes it a real, if small, liability.
  * **Readable without stylesheets and without JavaScript.** These pages have to
    work for a screen reader, for a regulator printing them, and for the person
    whose connection dropped halfway through. So: real headings in order, one
    h1, no interactivity required to read anything.
  * **Honest when incomplete.** If the operator's details are not configured the
    page says so at the top in plain words rather than printing a blank space or
    a placeholder that looks like a name.
"""
from __future__ import annotations

from backend.core import legal


def esc(v) -> str:
    return (str(v if v is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# Dark mode included, because the app has one and a legal page that flashes
# white at midnight is the kind of small jarring thing people remember.
_CSS = """
:root{--bg:#fbfaf8;--surface:#fff;--ink:#16181d;--ink-2:#454a55;--ink-3:#6b7280;
--line:#e4e2dc;--accent:#3f4a6b;--warn-bg:#fdf4e3;--warn:#7a5a1c}
@media(prefers-color-scheme:dark){:root{--bg:#12151c;--surface:#191d26;--ink:#e8eaef;
--ink-2:#adb6c4;--ink-3:#909bad;--line:#242a36;--accent:#9ba6ee;--warn-bg:#2a2110;--warn:#f0b429}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:40px 22px 80px}
a{color:var(--accent)}
a:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.skip{position:absolute;left:-9999px}
.skip:focus{left:8px;top:8px;background:var(--surface);padding:8px 12px;border:1px solid var(--line);z-index:9}
header.top{border-bottom:1px solid var(--line);padding-bottom:16px;margin-bottom:28px}
header.top a{text-decoration:none;font-weight:600}
h1{font-size:28px;line-height:1.2;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:17px;margin:34px 0 8px;letter-spacing:-.005em}
p{margin:0 0 12px;color:var(--ink-2)}
.meta{color:var(--ink-3);font-size:13.5px;margin:0 0 28px}
.gap{background:var(--warn-bg);color:var(--warn);border:1px solid var(--warn);
border-radius:8px;padding:12px 14px;margin:0 0 24px;font-size:14px}
.gap ul{margin:8px 0 0;padding-left:20px}
.gap b{color:var(--warn)}
table{width:100%;border-collapse:collapse;font-size:14px;margin:8px 0 20px}
th,td{text-align:left;padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:12px;letter-spacing:.05em;text-transform:uppercase;color:var(--ink-3)}
.scroll{overflow-x:auto}
nav.docs{border-top:1px solid var(--line);margin-top:44px;padding-top:20px;font-size:14px}
nav.docs h2{margin-top:0}
nav.docs ul{list-style:none;padding:0;margin:0}
nav.docs li{margin-bottom:9px}
nav.docs .s{color:var(--ink-3);display:block;font-size:13px}
footer.id{border-top:1px solid var(--line);margin-top:36px;padding-top:18px;
font-size:13.5px;color:var(--ink-3)}
footer.id p{color:var(--ink-3);margin:0 0 5px}
.note{font-size:13px;color:var(--ink-3);border-left:3px solid var(--line);padding-left:12px;margin-top:28px}
"""


def _gap_notice(missing: list[dict]) -> str:
    if not missing:
        return ""
    items = "".join(f"<li>{esc(m['label'])}</li>" for m in missing)
    return (f'<div class="gap"><b>This page is not finished.</b> '
            f'{len(missing)} required detail(s) about the business are not set '
            f'yet, so this policy cannot name who operates this service. It must '
            f'not be published in this state.<ul>{items}</ul></div>')


def _sections(sections) -> str:
    out = []
    for heading, paras in sections:
        out.append(f"<h2>{esc(heading)}</h2>")
        for p in paras:
            out.append(f"<p>{esc(p)}</p>")
    return "\n".join(out)


def _cookie_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    body = "".join(
        f"<tr><td><code>{esc(r['name'])}</code></td><td>{esc(r['kind'])}</td>"
        f"<td>{esc(r['purpose'])}</td><td>{esc(r['category'])}</td>"
        f"<td>{esc(r['life'])}</td></tr>" for r in rows)
    return ('<div class="scroll"><table><thead><tr><th>Name</th><th>What it is</th>'
            '<th>What it does</th><th>Category</th><th>How long</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def _nav(current: str) -> str:
    items = "".join(
        f'<li><a href="/legal/{esc(d["slug"])}">{esc(d["title"])}</a>'
        f'<span class="s">{esc(d["summary"])}</span></li>'
        for d in legal.DOCUMENTS if d["slug"] != current)
    return f'<nav class="docs"><h2>The other documents</h2><ul>{items}</ul></nav>'


def _identity_footer() -> str:
    lines = "".join(f"<p>{esc(x)}</p>" for x in legal.index()["identity"])
    return f'<footer class="id">{lines}</footer>'


def _shell(title: str, body: str, description: str, path: str) -> str:
    """One h1, headings in order, no external requests, no script needed."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(title)} | {esc(legal.PRODUCT_NAME)}</title>
<meta name="description" content="{esc(description)}" />
<meta name="robots" content="index, follow" />
<link rel="canonical" href="{esc(path)}" />
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<style>{_CSS}</style>
</head>
<body>
<a class="skip" href="#doc">Skip to the document</a>
<div class="wrap">
<header class="top"><a href="/">{esc(legal.PRODUCT_NAME)}</a></header>
<main id="doc">
{body}
</main>
</div>
</body>
</html>"""


def page(slug: str, base_url: str = "") -> str | None:
    d = legal.document(slug)
    if not d:
        return None
    body = [
        f"<h1>{esc(d['title'])}</h1>",
        f'<p class="meta">Last reviewed {esc(d["reviewed_on"])}. '
        f'{esc(d["summary"])}</p>',
        _gap_notice(d["missing"]),
        _sections(d["sections"]),
        _cookie_table(d["cookie_table"]),
        '<p class="note">This is written to cover the obligations we know apply '
        'to us, and it names the rule behind each one so it can be checked. It '
        'is not legal advice, and it is not a substitute for having a lawyer '
        'read it.</p>',
        _nav(slug),
        _identity_footer(),
    ]
    return _shell(d["title"], "\n".join(x for x in body if x),
                  d["summary"], f"{base_url}/legal/{slug}")


def hub(base_url: str = "") -> str:
    ix = legal.index()
    items = "".join(
        f'<li><a href="/legal/{esc(d["slug"])}">{esc(d["title"])}</a>'
        f'<span class="s">{esc(d["summary"])}</span></li>'
        for d in ix["documents"])
    body = [
        "<h1>Legal</h1>",
        f'<p class="meta">Everything we publish about how this service works, '
        f'what we do with your data, and who to contact. Last reviewed '
        f'{esc(ix["reviewed_on"])}.</p>',
        _gap_notice(ix["missing"]),
        f'<nav class="docs" style="border-top:none;margin-top:0;padding-top:0">'
        f'<ul>{items}</ul></nav>',
        _identity_footer(),
    ]
    return _shell("Legal", "\n".join(x for x in body if x),
                  f"Privacy policy, terms of use, refund policy and grievance "
                  f"contact for {legal.PRODUCT_NAME}.", f"{base_url}/legal")


# ---------------------------------------------------------------------------
# A seller's own shop
# ---------------------------------------------------------------------------
def seller_page(shop_name: str, handle: str, legal_details: dict, slug: str,
                base_url: str = "", store_path: str = "") -> str | None:
    """One of the three documents a shop publishes, in the shop's own name.

    Served from the app rather than rendered by the storefront's JavaScript on
    purpose. A policy that only exists once a bundle has executed is not
    published in any sense a regulator or a crawler would accept.
    """
    docs = legal.seller_docs(shop_name, legal_details)
    d = next((x for x in docs if x["slug"] == slug), None)
    if not d:
        return None
    gaps = legal.seller_missing(legal_details)
    shop = shop_name or "This shop"
    others = "".join(
        f'<li><a href="{esc(store_path)}/legal/{esc(x["slug"])}">'
        f'{esc(x["title"])}</a></li>' for x in docs if x["slug"] != slug)
    gap_html = ""
    if gaps:
        li = "".join(f"<li>{esc(g['label'])}</li>" for g in gaps)
        gap_html = (f'<div class="gap"><b>This shop has not filled in its '
                    f'details yet.</b> Indian law requires a shop to show who '
                    f'runs it and how to reach them. Until these are set this '
                    f'page cannot say.<ul>{li}</ul></div>')
    body = [
        f"<h1>{esc(d['title'])}</h1>",
        f'<p class="meta">{esc(shop)}. Last updated {esc(legal.REVIEWED_ON)}.</p>',
        gap_html,
        _sections(d["sections"]),
        f'<nav class="docs"><h2>Also on this shop</h2><ul>{others}'
        f'<li><a href="{esc(store_path)}">Back to the shop</a></li></ul></nav>',
    ]
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(d['title'])} | {esc(shop)}</title>
<meta name="description" content="{esc(d['title'])} for {esc(shop)}." />
<meta name="robots" content="index, follow" />
<link rel="canonical" href="{esc(base_url)}{esc(store_path)}/legal/{esc(slug)}" />
<style>{_CSS}</style>
</head>
<body>
<a class="skip" href="#doc">Skip to the document</a>
<div class="wrap">
<header class="top"><a href="{esc(store_path) or '/'}">{esc(shop)}</a></header>
<main id="doc">
{"".join(x for x in body if x)}
</main>
</div>
</body>
</html>"""
