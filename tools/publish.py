#!/usr/bin/env python3
"""Publish AI design digests to the Daily Design GitHub Pages site.

Usage:  python3 /workspace/daily-design/tools/publish.py [--no-push] [--src DIR]

1. Copies every edition found in the source folder (default /workspace/ai-design-daily)
   into editions/<date>/<slot>.html (+ <slot>-header.<ext>, <slot>-thumb.jpg).
2. Converts Markdown-only reports (6 PM "best", 8 PM "hottest") into styled HTML pages.
3. Injects the site navigation bar / prev-next / footer into every edition (idempotent).
4. Rebuilds data/index.json (+ data/index.js) from the edition Markdown sources.
5. Runs a public-safety scan, then commits and pushes as GreatCreations.
"""
import argparse, datetime as dt, html, json, os, re, shutil, subprocess, sys, unicodedata
from urllib.parse import urlparse, quote

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = "/workspace/ai-design-daily"
SITE_URL = "https://greatcreations.github.io/daily-design/"
GH_USER = "GreatCreations"

SLOTS = {
    "morning": dict(order=0, time="7 AM", name="AI Design Daily", color="#f5a524"),
    "noon":    dict(order=1, time="Noon", name="AI Design in Use", color="#22e0cf"),
    "best":    dict(order=2, time="6 PM", name="Best of the Day", color="#9b6bff"),
    "hottest": dict(order=3, time="8 PM", name="Hottest Right Now", color="#ff5a2e"),
}
FILE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-(morning|noon|best|hottest)\.(html|md)$")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")

MEDIUMS = [  # key, label, heading keywords
    ("image", "Image", r"\bimage|visual|photo|illustrat"),
    ("video", "Video", r"\bvideo|animation|film|motion"),
    ("3d", "3D", r"\b3d\b|modell?ing|render"),
    ("code", "Code/UI", r"\bcode|\bui\b|web design|interface"),
    ("sound", "Sound", r"\bsound|music|audio|voice"),
    ("games", "Games", r"\bgames?\b|gaming"),
    ("mashups", "Mashups", r"mashup|connector|agent creative|studio"),
]
TYPES = ["tutorial", "repo/tool", "showcase", "news", "update", "buzz",
         "case study", "breakdown", "workflow", "result"]
KIND_MAP = {  # source wording -> canonical type
    "tutorial": "tutorial", "guide": "tutorial", "reference shelf": "tutorial", "how-to": "tutorial",
    "repo/tool": "repo/tool", "repo": "repo/tool", "tool": "repo/tool", "repo in use": "repo/tool",
    "tool in use": "repo/tool", "showcase": "showcase", "finished project": "showcase",
    "news": "news", "festival": "news", "launch": "news", "update": "update",
    "buzz": "buzz", "backlash": "buzz", "viral": "buzz", "signal": "buzz", "community": "buzz",
    "discussion": "buzz", "case study": "case study", "client work": "case study",
    "client-style ad": "case study", "breakdown": "breakdown", "workflow": "workflow",
    "honest result": "result", "result": "result",
}
SKIP_SECTION = re.compile(r"(?i)read first|six stories|stories to read|method|caveat|how this edition")
DOMAIN_NAMES = {
    "x.com": "X", "twitter.com": "X", "youtube.com": "YouTube", "youtu.be": "YouTube",
    "github.com": "GitHub", "huggingface.co": "Hugging Face", "producthunt.com": "Product Hunt",
    "news.ycombinator.com": "Hacker News", "reddit.com": "Reddit", "behance.net": "Behance",
    "artstation.com": "ArtStation", "dribbble.com": "Dribbble", "store.steampowered.com": "Steam",
}

# ---- public-safety: scrubs applied to published HTML, then a hard scan -------------
SCRUBS = [
    (re.compile(r"\s*·\s*Research for [A-Z][\w ]{0,40}?(?=\s*·)"), ""),
    (re.compile(r"\s*·\s*compiled by Research\b"), ""),
    (re.compile(r"(?i)\bcompiled by Research\b\.?\s*"), ""),
]
FORBIDDEN = [
    r"/workspace\b", r"/home/box", r"/cursor/stores", r"file://", r"\bstore-[0-9a-f]{8}-",
    r"gh[pousr]_[A-Za-z0-9]{20,}", r"github_pat_", r"xox[abprs]-", r"\bsk-[A-Za-z0-9]{20,}",
    r"(?i)slack\.com", r"(?i)docs\.google\.com|drive\.google\.com",
    r"(?i)compiled by research|research for ",
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.(?:com|net|org|io|ai|co|dev|app)\b",
]
ALLOW_EMAIL = re.compile(r"users\.noreply\.github\.com")


def log(*a):
    print("[publish]", *a, flush=True)


def esc(s):
    return html.escape(s or "", quote=True)


def slugify(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "s"


def strip_md(s):
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"\*\*|__|`", "", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)([^*]+?)\*", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def strip_tags(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", s))).strip()


def nice_date(d):
    return dt.date.fromisoformat(d).strftime("%a %b %-d, %Y")


def medium_of(text):
    t = text.lower()
    for key, _, pat in MEDIUMS:
        if re.search(pat, t):
            return key
    return ""


def canon_type(kind):
    k = (kind or "").strip().lower()
    if k in KIND_MAP:
        return KIND_MAP[k]
    for word, t in KIND_MAP.items():
        if word in k:
            return t
    return ""


def source_of(url):
    host = urlparse(url).netloc.lower().removeprefix("www.").removeprefix("m.")
    for d, name in DOMAIN_NAMES.items():
        if host == d or host.endswith("." + d):
            return name
    return host


# ---------------------------------------------------------------- Markdown → HTML
def md_inline(s):
    codes = []
    def keep(m):
        codes.append("<code>%s</code>" % esc(m.group(1)))
        return "\x00%d\x00" % (len(codes) - 1)
    s = re.sub(r"`([^`]+)`", keep, s)
    s = esc(s)
    s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", r'<img src="\2" alt="\1" loading="lazy">', s)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<em>\1</em>", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], s)


def md_to_html(md, skip_images=()):
    out, para, lst, quote_ = [], [], None, []
    lines = md.replace("\r\n", "\n").split("\n")

    def flush_para():
        if para:
            out.append("<p>%s</p>" % md_inline(" ".join(para)))
            para.clear()

    def flush_list():
        nonlocal lst
        if lst:
            tag, items = lst
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % i for i in items), tag))
            lst = None

    def flush_quote():
        if quote_:
            out.append("<blockquote>%s</blockquote>" % md_inline(" ".join(quote_)))
            quote_.clear()

    def flush_all():
        flush_para(); flush_list(); flush_quote()

    i = 0
    while i < len(lines):
        raw = lines[i]; line = raw.rstrip()
        if not line.strip():
            flush_para(); flush_quote()
            # keep list open across a blank line if the next line continues it
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if lst and not re.match(r"^\s{0,3}([-*+]|\d+[.)])\s", nxt):
                flush_list()
            i += 1; continue
        img = re.match(r"^\s*!\[[^\]]*\]\(([^)\s]+)\)\s*$", line)
        if img and os.path.basename(img.group(1)) in skip_images:
            i += 1; continue
        h = re.match(r"^(#{1,6})\s+(.*)$", line)
        if h:
            flush_all()
            lvl = len(h.group(1))
            if lvl == 1:
                i += 1; continue  # page title is rendered in the hero
            txt = h.group(2).strip()
            out.append('<h%d id="%s">%s</h%d>' % (lvl, slugify(strip_md(txt)), md_inline(txt), lvl))
            i += 1; continue
        if re.match(r"^\s*(-{3,}|\*{3,}|_{3,})\s*$", line):
            flush_all(); out.append("<hr>"); i += 1; continue
        if line.lstrip().startswith(">"):
            flush_para(); flush_list()
            quote_.append(line.lstrip()[1:].strip()); i += 1; continue
        if "|" in line and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            flush_all()
            cells = lambda l: [c.strip() for c in l.strip().strip("|").split("|")]
            head = cells(line); i += 2; rows = []
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                rows.append(cells(lines[i])); i += 1
            out.append('<div class="tbl"><table><thead><tr>%s</tr></thead><tbody>%s</tbody></table></div>' % (
                "".join("<th>%s</th>" % md_inline(c) for c in head),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % md_inline(c) for c in r) for r in rows)))
            continue
        m = re.match(r"^\s{0,3}([-*+]|\d+[.)])\s+(.*)$", line)
        if m:
            flush_para(); flush_quote()
            tag = "ol" if m.group(1)[0].isdigit() else "ul"
            if not lst or lst[0] != tag:
                flush_list(); lst = (tag, [])
            lst[1].append(md_inline(m.group(2)))
            i += 1; continue
        if lst and raw[:1] in (" ", "\t"):
            sep = "<br>" if lst[1][-1].endswith("") and lines[i - 1].endswith("  ") else " "
            lst[1][-1] += sep + md_inline(line.strip()); i += 1; continue
        flush_list(); flush_quote()
        para.append(line.strip()); i += 1
    flush_all()
    return "\n".join(out)


# ---------------------------------------------------------------- item extraction
LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
DATE_SEG = re.compile(r"^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}(, \d{4})?$")
ENG_SEG = re.compile(r"[♥👁★🔁🔖💬▲]|\b(likes?|views?|stars?|points?|pts|bookmarks?|upvotes?)\b", re.I)


def list_blocks(md):
    section, medium, skip, cur, blocks = "", "", False, None, []
    def flush():
        nonlocal cur
        if cur: blocks.append(cur)
        cur = None
    for raw in md.replace("\r\n", "\n").split("\n"):
        h = re.match(r"^(#{1,6})\s+(.*)$", raw)
        if h:
            flush()
            lvl, txt = len(h.group(1)), strip_md(h.group(2))
            if lvl <= 2:
                section, medium, skip = txt, medium_of(txt), bool(SKIP_SECTION.search(txt))
            else:
                medium = medium_of(txt) or medium_of(section)
                if SKIP_SECTION.search(txt): skip = True
            continue
        m = re.match(r"^\s{0,3}(?:[-*+]|\d+[.)])\s+(.*)$", raw)
        if m:
            flush(); cur = dict(lines=[m.group(1)], section=section, medium=medium, skip=skip)
        elif cur and raw[:1] in (" ", "\t") and raw.strip():
            cur["lines"].append(raw.strip())
        else:
            flush()
    flush()
    return blocks


def parse_block(b):
    first = b["lines"][0]
    text = "\n".join(b["lines"])
    links = LINK_RE.findall(text)
    if not links:
        return None
    older = "⏪" in first
    head = first.replace("⏪", "").strip()
    title = url = kind = rest = who = platform = idate = ""
    eng = []
    m = re.match(r"^\*{0,2}\[([^\]]+)\]\((https?://[^)\s]+)\)\*{0,2}\s*(.*)$", head)
    if m:  # "[Title](url), type. note"  or  "**[Title](url)**: note"
        title, url, rest = m.group(1), m.group(2), m.group(3)
        tm = re.match(r"^,\s*([a-z][a-z/ -]{1,20}?)\.\s*(.*)$", rest)
        if tm and canon_type(tm.group(1)):
            kind, rest = tm.group(1), tm.group(2)
        else:
            rest = re.sub(r"^[:,\s—–-]+", "", rest)
        note = " ".join([rest] + b["lines"][1:])
    else:
        bm = re.match(r"^\*\*(.+?)\*\*\s*(.*)$", head)
        if bm:  # "**Title** · who · Oct 14 · X · *Kind* · ♥ 15"
            title, meta = bm.group(1), bm.group(2)
            for seg in [s.strip() for s in meta.split("·") if s.strip()]:
                km = re.match(r"^\*([^*]+)\*$", seg)
                if km: kind = km.group(1)
                elif ENG_SEG.search(seg) and re.search(r"\d", seg): eng.append(seg)
                elif DATE_SEG.match(seg): idate = seg
                elif LINK_RE.search(seg): pass
                elif not who: who = seg
                elif not platform: platform = seg
            src = [u for t, u in links if t.strip().lower() in ("source", "link", "open source")]
            url = src[0] if src else links[0][1]
            body = []
            for l in b["lines"][1:]:
                if l.lower().startswith("tools:"):
                    body.append(re.sub(r"\s*·\s*\[.*$", "", l).strip())
                else:
                    body.append(l)
            note = " ".join(body)
        else:
            title, url = links[0]
            note = strip_md(text)
    extras = [(t, u) for t, u in links if u != url and t.strip().lower() not in ("source", "link")]
    note = strip_md(note)
    ctype = canon_type(kind)
    if not ctype and b["section"]:
        s = b["section"].lower()
        ctype = "update" if "update" in s else "buzz" if "talking" in s else "tutorial" if "try" in s else ""
    return dict(title=strip_md(title), url=url, note=note, kind=strip_md(kind), type=ctype,
                medium=b["medium"], section=strip_md(b["section"]), author=who,
                source=platform or source_of(url), engagement=" · ".join(eng),
                item_date=idate, older=older,
                links=[dict(label=strip_md(t), url=u) for t, u in extras])


def parse_items(md):
    blocks = list_blocks(md)
    items = [parse_block(b) for b in blocks if not b["skip"]]
    items = [i for i in items if i]
    if not items:
        items = [i for i in (parse_block(b) for b in blocks) if i]
    seen, out = set(), []
    for it in items:
        key = (it["title"], it["url"])
        if key not in seen:
            seen.add(key); out.append(it)
    return out


# ---------------------------------------------------------------- nav injection
NAV_START, NAV_END = "<!--dd-nav:start-->", "<!--dd-nav:end-->"
FOOT_START, FOOT_END = "<!--dd-foot:start-->", "<!--dd-foot:end-->"
STYLE_START, STYLE_END = "<!--dd-style:start-->", "<!--dd-style:end-->"
NAV_H = 46


def nav_css(color):
    return """%s<style id="dd-style">
:root{--dd-accent:%s}
html{scroll-padding-top:%dpx}
body{padding-top:%dpx!important}
#dd-nav,#dd-nav *,#dd-foot,#dd-foot *{box-sizing:border-box;margin:0;letter-spacing:normal;text-transform:none}
#dd-nav{position:fixed;top:0;left:0;right:0;height:%dpx;z-index:2147483000;display:flex;align-items:center;gap:10px;padding:0 14px;
background:rgba(9,9,12,.92);-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);border-bottom:1px solid rgba(255,255,255,.09);
box-shadow:inset 0 -2px 0 var(--dd-accent);font:600 13px/1.2 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#ecebe8}
#dd-nav a{color:#ecebe8!important;text-decoration:none!important;display:inline-flex;align-items:center;gap:6px;padding:7px 11px;border-radius:999px;
border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.04);white-space:nowrap;font-weight:600}
#dd-nav a:hover{border-color:var(--dd-accent);background:rgba(255,255,255,.08)}
#dd-nav a.dd-home{background:var(--dd-accent);color:#0b0b0e!important;border-color:transparent;font-weight:800}
#dd-nav .dd-lab{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#b9b6ae;font-weight:500}
#dd-nav .dd-lab b{color:var(--dd-accent);font-weight:800;margin-right:6px}
#dd-nav .dd-off,#dd-foot .dd-off{opacity:.35;pointer-events:none}
#dd-foot{clear:both;display:flex;flex-wrap:wrap;gap:10px;justify-content:center;align-items:center;padding:28px 16px 90px;
background:#09090c;border-top:2px solid var(--dd-accent);font:600 14px/1.3 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
#dd-foot a{color:#ecebe8!important;text-decoration:none!important;padding:10px 16px;border-radius:999px;border:1px solid rgba(255,255,255,.14)}
#dd-foot a.dd-home{background:var(--dd-accent);color:#0b0b0e!important;border-color:transparent;font-weight:800}
@media (max-width:620px){#dd-nav{gap:6px;padding:0 8px}#dd-nav .dd-lab{font-size:12px}#dd-nav .dd-t{display:none}#dd-nav a{padding:7px 9px}}
</style>
<script>(function(){function fix(){var h=document.getElementById('dd-nav');if(!h)return;var H=h.offsetHeight;
var els=document.body.getElementsByTagName('*');for(var i=0;i<els.length;i++){var e=els[i];if(e.closest('#dd-nav'))continue;
var cs=getComputedStyle(e);if((cs.position==='sticky'||cs.position==='fixed')&&cs.top==='0px'&&cs.bottom!=='0px'){e.style.top=H+'px';}}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',fix);else fix();})();</script>%s""" % (
        STYLE_START, color, NAV_H + 64, NAV_H, NAV_H, STYLE_END)


def nav_link(ed, cls, label, arrow_first):
    if not ed:
        return '<a class="%s dd-off" aria-disabled="true">%s</a>' % (cls, label)
    href = "../%s/%s.html" % (ed["date"], ed["slot"])
    tip = "%s · %s %s" % (nice_date(ed["date"]), SLOTS[ed["slot"]]["time"], SLOTS[ed["slot"]]["name"])
    return '<a class="%s" href="%s" title="%s">%s</a>' % (cls, href, esc(tip), label)


def inject_nav(doc, ed, prev, nxt):
    for a, b in ((NAV_START, NAV_END), (FOOT_START, FOOT_END), (STYLE_START, STYLE_END)):
        doc = re.sub(re.escape(a) + ".*?" + re.escape(b) + r"\n?", "", doc, flags=re.S)
    s = SLOTS[ed["slot"]]
    bar = ('%s<nav id="dd-nav" aria-label="Daily Design"><a class="dd-home" href="../../index.html">← <span class="dd-t">Back to </span>index</a>'
           '<span class="dd-lab"><b>%s</b>%s · %s</span>%s%s</nav>%s\n') % (
        NAV_START, esc(s["time"]), esc(s["name"]), esc(nice_date(ed["date"])),
        nav_link(prev, "dd-prev", '‹ <span class="dd-t">Prev</span>', True),
        nav_link(nxt, "dd-next", '<span class="dd-t">Next</span> ›', False), NAV_END)
    foot = ('%s<div id="dd-foot">%s<a class="dd-home" href="../../index.html">← Back to the Daily Design index</a>%s</div>%s\n') % (
        FOOT_START, nav_link(prev, "dd-prev", "‹ Previous edition", True),
        nav_link(nxt, "dd-next", "Next edition ›", False), FOOT_END)
    doc = re.sub(r"</head>", lambda m: nav_css(s["color"]) + "\n</head>", doc, count=1, flags=re.I)
    doc = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + bar, doc, count=1, flags=re.I)
    idx = doc.lower().rfind("</body>")
    doc = doc[:idx] + foot + doc[idx:] if idx >= 0 else doc + foot
    return doc


# ---------------------------------------------------------------- report page template
def report_page(ed, body_html, header_name):
    s = SLOTS[ed["slot"]]
    hdr = '<img class="r-hdr" src="%s" alt="%s header image">' % (esc(header_name), esc(s["name"])) if header_name else ""
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s · %(date)s · Daily Design</title>
<meta name="description" content="%(summary)s">
<link rel="stylesheet" href="../../assets/site.css">
</head><body class="report" style="--acc:%(color)s">
<main class="r-wrap">
<header class="r-hero">%(hdr)s
<div class="r-kick"><span class="dot"></span>%(time)s · %(name)s · %(nicedate)s</div>
<h1>%(headline)s</h1>
%(lead)s
<div class="r-meta">%(count)d items</div>
</header>
<article class="r-body">
%(body)s
</article>
</main>
</body></html>
""" % dict(title=esc(s["name"]), date=ed["date"], summary=esc(ed["summary"]), color=s["color"], hdr=hdr,
           time=esc(s["time"]), name=esc(s["name"]), nicedate=esc(nice_date(ed["date"])),
           headline=esc(ed["headline"]), lead=('<p class="r-lead">%s</p>' % esc(ed["summary"])) if ed["summary"] else "",
           count=ed["item_count"], body=body_html)


# ---------------------------------------------------------------- helpers
def find_header(src, date, slot, md_text):
    for ext in IMG_EXT:
        p = os.path.join(src, "%s-%s-header%s" % (date, slot, ext))
        if os.path.exists(p):
            return p
    if md_text:
        for ref in re.findall(r"!\[[^\]]*\]\(([^)\s]+)\)", md_text):
            p = os.path.join(src, ref)
            if not ref.startswith("http") and os.path.exists(p):
                return p
    return None


def make_thumb(src_img, dest):
    if os.path.exists(dest) and os.path.getmtime(dest) >= os.path.getmtime(src_img):
        return True
    try:
        from PIL import Image
        im = Image.open(src_img).convert("RGB")
        im.thumbnail((900, 900))
        im.save(dest, "JPEG", quality=80, optimize=True, progressive=True)
        return True
    except Exception as e:  # PIL missing: fall back to the full header
        log("thumbnail skipped:", e)
        return False


def copy_if_changed(a, b):
    if not os.path.exists(b) or open(a, "rb").read() != open(b, "rb").read():
        shutil.copyfile(a, b)


def html_meta(doc):
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", doc, re.S | re.I)
    lead = (re.search(r'<p class="[^"]*\b(?:standfirst|lead|dek)\b[^"]*"[^>]*>(.*?)</p>', doc, re.S)
            or re.search(r"<header[^>]*>.*?<p[^>]*>(.*?)</p>", doc, re.S))
    return (strip_tags(h1.group(1)) if h1 else ""), (strip_tags(lead.group(1)) if lead else "")


def md_meta(md):
    t = re.search(r"^#\s+(.+)$", md, re.M)
    q = re.search(r"^>\s*(.+(?:\n>.*)*)", md, re.M)
    summary = strip_md(re.sub(r"^>\s?", "", q.group(1), flags=re.M)) if q else ""
    if not summary:
        for para in re.split(r"\n\s*\n", re.sub(r"^#.*$", "", md, flags=re.M)):
            p = para.strip()
            if p and not re.match(r"^([-*+>|!]|\d+[.)]|---)", p):
                summary = strip_md(p); break
    return (strip_md(t.group(1)) if t else ""), summary


def scrub(doc):
    for rx, rep in SCRUBS:
        doc = rx.sub(rep, doc)
    return doc


def load_denylist(src):
    """Extra private patterns (one regex per line) kept OUTSIDE the public repo, e.g.
    <src>/.publish-denylist. Use it for internal names that must never be published."""
    pats = []
    for p in (os.path.join(src, ".publish-denylist"), os.path.expanduser("~/.daily-design-denylist")):
        if os.path.exists(p):
            pats += [l.strip() for l in open(p, encoding="utf-8") if l.strip() and not l.startswith("#")]
    return pats


def safety_scan(paths, extra=(), base=True):
    bad = []
    for p in paths:
        try:
            txt = open(p, encoding="utf-8").read()
        except (UnicodeDecodeError, IsADirectoryError):
            continue
        txt = re.sub(r"data:[\w/+.-]+;base64,[A-Za-z0-9+/=]+", "", txt)
        for pat in (list(FORBIDDEN) if base else []) + list(extra):
            for m in re.finditer(pat, txt):
                if ALLOW_EMAIL.search(m.group(0)):
                    continue
                bad.append("%s: %r near %r" % (os.path.relpath(p, REPO), m.group(0),
                                                txt[max(0, m.start() - 40):m.end() + 40]))
    return bad


def git(*args, check=True, capture=False):
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    r = subprocess.run(["git", "-C", REPO] + list(args), env=env, text=True,
                       capture_output=capture, check=check)
    return r.stdout if capture else r.returncode


def ensure_credentials():
    helper = ('!f() { test "$1" = get && echo username=x-access-token && '
              'echo "password=$(gh auth token -u %s)"; }; f' % GH_USER)
    for key in ("credential.helper", "credential.https://github.com.helper"):
        subprocess.run(["git", "-C", REPO, "config", "--local", "--unset-all", key], capture_output=True)
        git("config", "--local", key, "")
        git("config", "--local", "--add", key, helper)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--no-push", action="store_true", help="build and commit nothing; just regenerate files")
    args = ap.parse_args()
    src = args.src

    found = {}
    for fn in sorted(os.listdir(src)):
        m = FILE_RE.match(fn)
        if m:
            found.setdefault((m.group(1), m.group(2)), {})[m.group(3)] = os.path.join(src, fn)
    if not found:
        log("no editions found in", src); return 1
    eds = []
    for (date, slot), files in found.items():
        md = open(files["md"], encoding="utf-8").read() if "md" in files else ""
        eds.append(dict(date=date, slot=slot, files=files, md=md))
    eds.sort(key=lambda e: (e["date"], SLOTS[e["slot"]]["order"]))

    all_items = []
    for e in eds:
        date, slot, md = e["date"], e["slot"], e["md"]
        outdir = os.path.join(REPO, "editions", date)
        os.makedirs(outdir, exist_ok=True)
        hdr_src = find_header(src, date, slot, md)
        header_name = thumb_name = None
        if hdr_src:
            header_name = "%s-header%s" % (slot, os.path.splitext(hdr_src)[1].lower())
            copy_if_changed(hdr_src, os.path.join(outdir, header_name))
            thumb_name = "%s-thumb.jpg" % slot
            if not make_thumb(hdr_src, os.path.join(outdir, thumb_name)):
                thumb_name = header_name
        items = parse_items(md) if md else []
        if "html" in e["files"]:
            doc = scrub(open(e["files"]["html"], encoding="utf-8").read())
            headline, summary = html_meta(doc)
        else:
            doc = None
            headline, summary = md_meta(md)
        if not headline:
            headline = md_meta(md)[0] if md else SLOTS[slot]["name"]
        e.update(doc=doc, header=header_name, thumb=thumb_name, items=items, headline=headline,
                 summary=summary, item_count=len(items), path="editions/%s/%s.html" % (date, slot))
        for n, it in enumerate(items, 1):
            it.update(id="%s-%s-%d" % (date, slot, n), date=date, slot=slot, edition=e["path"])
            tags = [t for t in [it["medium"], it["type"], slot, date] if t]
            if it["kind"] and canon_type(it["kind"]) != it["kind"].lower():
                tags.append(it["kind"].lower())
            if it["older"]: tags.append("older")
            if it["section"] and "try" in it["section"].lower(): tags.append("try today")
            it["tags"] = tags
            all_items.append(it)

    # write pages with prev/next
    for i, e in enumerate(eds):
        prev = eds[i - 1] if i > 0 else None
        nxt = eds[i + 1] if i + 1 < len(eds) else None
        if e["doc"] is None:
            md_body = e["md"]
            q = re.search(r"^>\s*.+(?:\n>.*)*\n?", md_body, re.M)
            if q and e["summary"] and strip_md(re.sub(r"^>\s?", "", q.group(0), flags=re.M)) == e["summary"]:
                md_body = md_body[:q.start()] + md_body[q.end():]  # lead already shown in the hero
            body = md_to_html(md_body, skip_images={os.path.basename(f) for f in os.listdir(src)
                                                      if f.startswith("%s-%s-header" % (e["date"], e["slot"]))})
            e["doc"] = scrub(report_page(e, body, e["header"]))
        out = inject_nav(e["doc"], e, prev, nxt)
        dest = os.path.join(REPO, e["path"])
        if not os.path.exists(dest) or open(dest, encoding="utf-8").read() != out:
            open(dest, "w", encoding="utf-8").write(out)
            log("wrote", e["path"], "(%d items)" % e["item_count"])

    editions_json = []
    for e in reversed(eds):
        meds = sorted({it["medium"] for it in e["items"] if it["medium"]})
        editions_json.append(dict(
            date=e["date"], slot=e["slot"], time=SLOTS[e["slot"]]["time"], title=SLOTS[e["slot"]]["name"],
            headline=e["headline"], summary=e["summary"], path=e["path"],
            header=("editions/%s/%s" % (e["date"], e["header"])) if e["header"] else None,
            thumb=("editions/%s/%s" % (e["date"], e["thumb"])) if e["thumb"] else None,
            item_count=e["item_count"], tags=[e["slot"], e["date"]] + meds))
    tagset = sorted({t for it in all_items for t in it["tags"]} | {t for ed in editions_json for t in ed["tags"]})
    data = dict(
        site=dict(name="Daily Design", url=SITE_URL),
        totals=dict(editions=len(editions_json), items=len(all_items), tags=len(tagset),
                    days=len({e["date"] for e in eds})),
        facets=dict(
            medium=[dict(key=k, label=l) for k, l, _ in MEDIUMS],
            type=TYPES,
            slot=[dict(key=k, label="%s · %s" % (v["time"], v["name"]), color=v["color"]) for k, v in SLOTS.items()],
            date=sorted({e["date"] for e in eds}, reverse=True)),
        editions=editions_json,
        items=[{k: it[k] for k in ("id", "title", "url", "note", "medium", "type", "kind", "tags", "source",
                                   "author", "engagement", "item_date", "links", "edition", "date", "slot")}
               for it in all_items])
    js = json.dumps(data, ensure_ascii=False, indent=1)
    os.makedirs(os.path.join(REPO, "data"), exist_ok=True)
    open(os.path.join(REPO, "data", "index.json"), "w", encoding="utf-8").write(js + "\n")
    open(os.path.join(REPO, "data", "index.js"), "w", encoding="utf-8").write("window.DD_DATA=" + js + ";\n")
    open(os.path.join(REPO, ".nojekyll"), "a").close()
    log("index: %d editions, %d items, %d tags" % (len(editions_json), len(all_items), len(tagset)))

    # safety scan of everything that will be published
    scan = []
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if f.endswith((".html", ".json", ".js", ".css", ".md", ".txt", ".py")):
                scan.append(os.path.join(root, f))
    deny = load_denylist(src)
    tools_dir = os.sep + "tools" + os.sep
    site_files = [p for p in scan if tools_dir not in p]
    tool_files = [p for p in scan if tools_dir in p]
    # the publisher source necessarily contains the generic patterns, so tools/ is
    # checked against the private denylist only
    bad = safety_scan(site_files, deny) + safety_scan(tool_files, deny, base=False)
    if bad:
        log("SAFETY SCAN FAILED; nothing committed:")
        for b in bad[:40]:
            log("  ", b)
        return 2
    log("safety scan clean (%d files)" % len(scan))

    if args.no_push:
        return 0
    ensure_credentials()
    git("add", "-A")
    if not git("status", "--porcelain", capture=True).strip():
        log("nothing new to publish"); return 0
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip()
    latest = eds[-1]
    git("commit", "-q", "-m", "Publish editions through %s %s (%s)" % (latest["date"], latest["slot"], stamp))
    git("push", "-q", "origin", "HEAD:main")
    log("pushed. Live in ~1 min at", SITE_URL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
