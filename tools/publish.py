#!/usr/bin/env python3
"""Publish AI design digests to the Daily Design GitHub Pages site.

Usage:  python3 /workspace/daily-design/tools/publish.py [--no-push] [--src DIR]

1. Copies the 7 AM and noon HTML editions found in the source folder (default /workspace/ai-design-daily)
   into editions/<date>/<slot>.html (+ <slot>-header.<ext>, <slot>-thumb.jpg).
2. Copies the 6 PM "best" and 8 PM "hottest" reports as plain Markdown to reports/<date>/<slot>.md,
   with their header image embedded at the top via a relative link.
3. Injects the site navigation bar / prev-next / footer into the 7 AM and noon HTML editions (idempotent).
4. Keeps per-edition metadata in data/meta/<date>/<slot>.json and rebuilds data/index.json
   (editions, calendar, facets, totals) plus monthly item shards data/items/<YYYY-MM>.json.
5. Runs a public-safety scan, then commits and pushes as GreatCreations.
"""
import argparse, datetime as dt, html, json, os, re, shutil, subprocess, sys, unicodedata
from urllib.parse import urlparse, quote

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SRC = "/workspace/ai-design-daily"
SITE_URL = "https://greatcreations.github.io/daily-design/"
REPO_BLOB = "https://github.com/GreatCreations/daily-design/blob/main/"
REPORT_SLOTS = {"best", "hottest"}  # these stay plain Markdown reports
TOOL_VERSION = 3  # bump to force every source edition to be reprocessed
NAV_VERSION = 2   # bump to force nav re-injection on every HTML edition
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
#dd-nav button.dd-tts{appearance:none;cursor:pointer;font:inherit;color:#ecebe8;display:inline-flex;align-items:center;gap:6px;padding:7px 11px;min-height:32px;
border-radius:999px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.04);white-space:nowrap;font-weight:600}
#dd-nav button.dd-tts[hidden]{display:none}
#dd-nav button.dd-tts:hover,#dd-nav button.dd-tts.on{border-color:var(--dd-accent);background:rgba(255,255,255,.08)}
#dd-nav button.dd-tts:focus-visible,#dd-nav a:focus-visible{outline:2px solid var(--dd-accent);outline-offset:2px}
#dd-nav .tts-i{color:var(--dd-accent);font-size:10px}
#dd-foot{clear:both;display:flex;flex-wrap:wrap;gap:10px;justify-content:center;align-items:center;padding:28px 16px 90px;
background:#09090c;border-top:2px solid var(--dd-accent);font:600 14px/1.3 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
#dd-foot a{color:#ecebe8!important;text-decoration:none!important;padding:10px 16px;border-radius:999px;border:1px solid rgba(255,255,255,.14)}
#dd-foot a.dd-home{background:var(--dd-accent);color:#0b0b0e!important;border-color:transparent;font-weight:800}
@media (max-width:620px){#dd-nav{gap:6px;padding:0 8px}#dd-nav .dd-lab{font-size:12px}#dd-nav .dd-t,#dd-nav .tts-l{display:none}#dd-nav a,#dd-nav button.dd-tts{padding:7px 9px}}
</style>
<script>(function(){function fix(){var h=document.getElementById('dd-nav');if(!h)return;var H=h.offsetHeight;
var els=document.body.getElementsByTagName('*');for(var i=0;i<els.length;i++){var e=els[i];if(e.closest('#dd-nav'))continue;
var cs=getComputedStyle(e);if((cs.position==='sticky'||cs.position==='fixed')&&cs.top==='0px'&&cs.bottom!=='0px'){e.style.top=H+'px';}}}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',fix);else fix();})();</script>%s""" % (
        STYLE_START, color, NAV_H + 64, NAV_H, NAV_H, STYLE_END)


# read-aloud control (browser speech, assets/tts.js); hidden until the script confirms support
TTS_BUTTONS = ('<button class="dd-tts" id="dd-tts-play" type="button" hidden aria-label="Listen: read this page aloud" aria-pressed="false">'
               '<span class="tts-i" aria-hidden="true">▶</span><span class="tts-l">Listen</span></button>'
               '<button class="dd-tts" id="dd-tts-stop" type="button" hidden aria-label="Stop reading">'
               '<span aria-hidden="true">■</span><span class="tts-l">Stop</span></button>'
               '<script src="../../assets/tts.js" defer></script>')


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
           '<span class="dd-lab"><b>%s</b>%s · %s</span>%s%s%s</nav>%s\n') % (
        NAV_START, esc(s["time"]), esc(s["name"]), esc(nice_date(ed["date"])), TTS_BUTTONS,
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


# ---------------------------------------------------------------- Markdown reports
def report_markdown(md, date, slot, header_name):
    """6 PM / 8 PM reports stay plain Markdown. Put the header image at the top with a
    relative link (it sits next to the .md in reports/<date>/) and drop any older header ref."""
    lines = md.replace("\r\n", "\n").split("\n")
    hdr_re = re.compile(r"^\s*!\[[^\]]*\]\(([^)\s]+)\)\s*$")
    keep = []
    for l in lines:
        m = hdr_re.match(l)
        if m and ("-header" in os.path.basename(m.group(1)) or os.path.basename(m.group(1)) == header_name):
            continue
        keep.append(l)
    if header_name:
        img = "![%s header](%s)" % (SLOTS[slot]["name"], header_name)
        h1 = next((i for i, l in enumerate(keep) if re.match(r"^#\s+", l)), None)
        if h1 is None:
            keep[0:0] = [img, ""]
        else:
            keep[h1 + 1:h1 + 1] = ["", img]
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(keep)).strip() + "\n"
    return scrub(out)


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
# Repo-side state: every published edition has a metadata record in
#   data/meta/<YYYY-MM-DD>/<slot>.json   (edition fields + its parsed items + source hash + nav)
# so the index is always rebuilt from what is in the repo, even after the source folder is
# cleaned out. The browser loads data/index.json (editions, facets, calendar, totals) and
# fetches items lazily from monthly shards data/items/<YYYY-MM>.json.

def sha(path):
    import hashlib
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_if_changed(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == text:
        return False
    open(path, "w", encoding="utf-8").write(text)
    return True


def jdump(obj, pretty=False):
    if pretty:
        return json.dumps(obj, ensure_ascii=False, indent=1) + "\n"
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")) + "\n"


def tag_item(it, date, slot, n, href, kind):
    it.update(id="%s-%s-%d" % (date, slot, n), date=date, slot=slot, edition=href, edition_kind=kind)
    tags = [t for t in [it["medium"], it["type"], slot, date] if t]
    if it["kind"] and canon_type(it["kind"]) != it["kind"].lower():
        tags.append(it["kind"].lower())
    if it["older"]: tags.append("older")
    if it["section"] and "try" in it["section"].lower(): tags.append("try today")
    it["tags"] = tags
    return {k: it[k] for k in ("id", "title", "url", "note", "medium", "type", "kind", "tags", "source", "author",
                               "engagement", "item_date", "links", "edition", "edition_kind", "date", "slot")}


def process_source(src, date, slot, files, deny_changed=False):
    """Build one edition from the source folder. Returns its metadata record."""
    md = open(files["md"], encoding="utf-8").read() if "md" in files else ""
    is_page = "html" in files and slot not in REPORT_SLOTS
    if not is_page and not md:
        log("skipping %s %s: reports need a .md file" % (date, slot)); return None
    sub = "editions" if is_page else "reports"
    outdir = os.path.join(REPO, sub, date)
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
    if is_page:
        doc = scrub(open(files["html"], encoding="utf-8").read())
        headline, summary = html_meta(doc)
        path = "editions/%s/%s.html" % (date, slot); href = path
        # store the clean (nav-free) page; nav is injected in the nav pass
        write_if_changed(os.path.join(REPO, path), doc)
    else:
        headline, summary = md_meta(md)
        path = "reports/%s/%s.md" % (date, slot); href = REPO_BLOB + path
        if write_if_changed(os.path.join(REPO, path), report_markdown(md, date, slot, header_name)):
            log("wrote", path, "(%d items)" % len(items))
    if not headline:
        headline = md_meta(md)[0] if md else SLOTS[slot]["name"]
    kind = "page" if is_page else "report"
    ed = dict(date=date, slot=slot, time=SLOTS[slot]["time"], title=SLOTS[slot]["name"], kind=kind,
              headline=headline, summary=summary, path=path, url=href,
              header=("%s/%s/%s" % (sub, date, header_name)) if header_name else None,
              thumb=("%s/%s/%s" % (sub, date, thumb_name)) if thumb_name else None,
              item_count=len(items))
    meds = sorted({it["medium"] for it in items if it["medium"]})
    ed["tags"] = [slot, date] + meds + (["report"] if kind == "report" else [])
    recs = [tag_item(it, date, slot, n, href, kind) for n, it in enumerate(items, 1)]
    return dict(edition=ed, items=recs, src_hash={k: sha(v) for k, v in files.items()},
                tool_version=TOOL_VERSION, nav=None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=DEFAULT_SRC)
    ap.add_argument("--no-push", action="store_true", help="rebuild and scan, but do not commit or push")
    ap.add_argument("--rebuild", action="store_true", help="reprocess every source edition even if unchanged")
    args = ap.parse_args()
    src = args.src
    meta_dir = os.path.join(REPO, "data", "meta")

    # 1. new or changed source editions -> repo + metadata
    found = {}
    if os.path.isdir(src):
        for fn in sorted(os.listdir(src)):
            m = FILE_RE.match(fn)
            if m:
                found.setdefault((m.group(1), m.group(2)), {})[m.group(3)] = os.path.join(src, fn)
    for (date, slot), files in sorted(found.items()):
        mpath = os.path.join(meta_dir, date, slot + ".json")
        old = json.load(open(mpath, encoding="utf-8")) if os.path.exists(mpath) else None
        hashes = {k: sha(v) for k, v in files.items()}
        if old and not args.rebuild and old.get("src_hash") == hashes and old.get("tool_version") == TOOL_VERSION:
            continue
        rec = process_source(src, date, slot, files)
        if not rec:
            continue
        if old and old["edition"]["kind"] != rec["edition"]["kind"]:  # slot changed format
            stale = os.path.join(REPO, old["edition"]["path"])
            if os.path.exists(stale): os.remove(stale)
        write_if_changed(mpath, jdump(rec, pretty=True))
        log("%s %s %s (%d items)" % ("updated" if old else "added", date, slot, rec["edition"]["item_count"]))

    # 2. load every edition record in the repo
    recs = []
    if os.path.isdir(meta_dir):
        for d in sorted(os.listdir(meta_dir)):
            for f in sorted(os.listdir(os.path.join(meta_dir, d))):
                if f.endswith(".json"):
                    recs.append(json.load(open(os.path.join(meta_dir, d, f), encoding="utf-8")))
    if not recs:
        log("no editions yet"); return 1
    recs.sort(key=lambda r: (r["edition"]["date"], SLOTS[r["edition"]["slot"]]["order"]))

    # 3. nav pass: only pages whose prev/next changed (or that were just rewritten) are touched
    pages = [r for r in recs if r["edition"]["kind"] == "page"]
    for i, r in enumerate(pages):
        e = r["edition"]
        prev = pages[i - 1]["edition"] if i > 0 else None
        nxt = pages[i + 1]["edition"] if i + 1 < len(pages) else None
        nav = [prev and prev["path"], nxt and nxt["path"], NAV_VERSION]
        dest = os.path.join(REPO, e["path"])
        doc = open(dest, encoding="utf-8").read()
        if r.get("nav") == nav and NAV_START in doc:
            continue
        if write_if_changed(dest, inject_nav(doc, e, prev, nxt)):
            log("nav", e["path"])
        r["nav"] = nav
        write_if_changed(os.path.join(meta_dir, e["date"], e["slot"] + ".json"), jdump(r, pretty=True))

    # 4. index.json + monthly item shards
    editions = [r["edition"] for r in reversed(recs)]  # newest first
    shards = {}
    for r in recs:
        shards.setdefault(r["edition"]["date"][:7], []).extend(r["items"])
    items_dir = os.path.join(REPO, "data", "items")
    os.makedirs(items_dir, exist_ok=True)
    for month, its in shards.items():
        its.sort(key=lambda it: (it["date"], SLOTS[it["slot"]]["order"]), reverse=True)
        write_if_changed(os.path.join(items_dir, month + ".json"), jdump({"month": month, "items": its}))
    for f in os.listdir(items_dir):
        if f.endswith(".json") and f[:-5] not in shards:
            os.remove(os.path.join(items_dir, f))
    days = {}
    for e in editions:
        days.setdefault(e["date"], []).append(e["slot"])
    tagset = sorted({t for r in recs for it in r["items"] for t in it["tags"]} | {t for e in editions for t in e["tags"]})
    total_items = sum(len(v) for v in shards.values())
    data = dict(
        version=2,
        site=dict(name="Daily Design", url=SITE_URL, repo_blob=REPO_BLOB),
        totals=dict(editions=len(editions), items=total_items, tags=len(tagset), days=len(days),
                    months=len(shards), first=min(days), last=max(days)),
        facets=dict(
            medium=[dict(key=k, label=l) for k, l, _ in MEDIUMS],
            type=TYPES,
            slot=[dict(key=k, label="%s · %s" % (v["time"], v["name"]), color=v["color"], order=v["order"])
                  for k, v in SLOTS.items()]),
        calendar=[dict(date=d, slots=sorted(v, key=lambda s: SLOTS[s]["order"])) for d, v in sorted(days.items(), reverse=True)],
        shards=[dict(month=m, path="data/items/%s.json" % m, items=len(v),
                     editions=sum(1 for e in editions if e["date"][:7] == m)) for m, v in sorted(shards.items(), reverse=True)],
        editions=editions)
    write_if_changed(os.path.join(REPO, "data", "index.json"), jdump(data))
    for legacy in ("index.js",):
        lp = os.path.join(REPO, "data", legacy)
        if os.path.exists(lp): os.remove(lp)
    open(os.path.join(REPO, ".nojekyll"), "a").close()
    log("index: %d editions over %d days, %d items in %d monthly shards, %d tags" % (
        len(editions), len(days), total_items, len(shards), len(tagset)))

    # 5. safety scan of everything new or changed since the last commit
    changed = None
    if os.path.isdir(os.path.join(REPO, ".git")):
        out = git("status", "--porcelain", "-uall", capture=True)
        changed = [os.path.join(REPO, l[3:].strip().strip('"')) for l in out.splitlines() if l[:2].strip() != "D"]
        changed = [p for p in changed if os.path.isfile(p)]
    if changed is None:  # not a git checkout: scan everything
        changed = []
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs if d != ".git"]
            changed += [os.path.join(root, f) for f in files]
    scan = [p for p in changed if p.endswith((".html", ".json", ".js", ".css", ".md", ".txt", ".py"))]
    deny = load_denylist(src)
    tools_dir = os.sep + "tools" + os.sep
    vendor_dir = os.sep + "vendor" + os.sep
    site_files = [p for p in scan if tools_dir not in p and vendor_dir not in p]
    other = [p for p in scan if tools_dir in p or vendor_dir in p]
    # the publisher source and vendored libraries contain generic patterns (regexes, licence
    # e-mails), so they are checked against the private denylist only
    bad = safety_scan(site_files, deny) + safety_scan(other, deny, base=False)
    if bad:
        log("SAFETY SCAN FAILED; nothing committed:")
        for b in bad[:40]:
            log("  ", b)
        return 2
    log("safety scan clean (%d changed files)" % len(scan))

    if args.no_push:
        return 0
    ensure_credentials()
    git("add", "-A")
    if not git("status", "--porcelain", capture=True).strip():
        log("nothing new to publish"); return 0
    stamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M %Z").strip()
    latest = recs[-1]["edition"]
    git("commit", "-q", "-m", "Publish editions through %s %s (%s)" % (latest["date"], latest["slot"], stamp))
    git("push", "-q", "origin", "HEAD:main")
    log("pushed. Live in ~1 min at", SITE_URL)
    return 0


if __name__ == "__main__":
    sys.exit(main())
