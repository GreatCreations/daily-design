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
SITE_URL = "https://studios.greatcreations.art/daily-design/"  # canonical base
REPO_BLOB = "https://github.com/GreatCreations/daily-design/blob/main/"
REPORT_SLOTS = {"best", "hottest"}  # these stay plain Markdown reports
TOOL_VERSION = 3  # bump to force every source edition to be reprocessed
NAV_VERSION = 8   # bump to force nav re-injection on every HTML edition
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
ALLOW_EMAIL = re.compile(r"users\.noreply\.github\.com|^dailydesign@greatcreations\.ca$")


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
ICON_START, ICON_END = "<!--dd-icon:start-->", "<!--dd-icon:end-->"
CREDIT_START, CREDIT_END = "<!--dd-credit:start-->", "<!--dd-credit:end-->"
STUDIO_NAME = "Great Creation Studios"
STUDIO_URL = "https://greatcreationstudios.greatcreations.art/"


CONTACT_EMAIL = "dailydesign@greatcreations.ca"  # public Daily Design address (shown on contact.html)
CONTACT_PATH = "contact.html"
SPON_START, SPON_END = "<!--dd-sponsor:start-->", "<!--dd-sponsor:end-->"
SPON2_START, SPON2_END = "<!--dd-sponsor-links:start-->", "<!--dd-sponsor-links:end-->"  # index: above Recent links
SPON_PLACEMENTS = ("top", "links")  # banner.placements; default ["top"]
SPONSORS_FILE = "sponsors.json"  # repo root; see README. Sponsors never affect rankings.


def mailto(subject):
    return "mailto:%s?subject=%s" % (CONTACT_EMAIL, quote(subject))


BRAND_COLS = ("#f5a524", "#22e0cf", "#9b6bff", "#ff5a2e")  # --amber, --aqua, --violet, --flame (7 AM, Noon, 6 PM, 8 PM)


def brand_html(prefix=""):
    """'Daily Design' as the DD logo plus letters cycling the four slot colors (space skipped). Screen readers get one
    'Daily Design' (role=img + aria-label); the logo and the letter spans are aria-hidden."""
    letters, n = [], 0
    for ch in "Daily Design":
        if ch == " ":
            letters.append(" ")
            continue
        letters.append('<span class="c%d">%s</span>' % (n % 4, ch))
        n += 1
    return ('<span class="dd-brand" role="img" aria-label="Daily Design"><img class="dd-brand-ic" src="%sassets/favicon.svg" alt="" '
            'aria-hidden="true" width="16" height="16"><span class="dd-brand-t" aria-hidden="true">%s</span></span>') % (prefix, "".join(letters))


def credit_html(prefix="", cls="dd-credit", contact=True):
    """Footer credit line (skipped by the Listen button via .dd-credit). prefix = path back to the site root.
    'Daily Design' is brand_html(): DD logo + letters in the four slot colors.
    The studio's icon is a vendored copy of its own favicon (assets/gcs-icon.png), decorative (alt="")."""
    return ('%s<p class="%s">%s is created and brought to you by '
            '<a href="%s" rel="noopener"><img class="dd-credit-ic" src="%sassets/gcs-icon.png" alt="" width="16" height="16">%s</a>.</p>'
            '%s%s') % (
        CREDIT_START, cls, brand_html(prefix), STUDIO_URL, prefix, STUDIO_NAME,
        ('<p class="dd-contactln"><a href="%s%s">Contact</a> · questions, tips, corrections and sponsorship</p>' % (prefix, CONTACT_PATH)) if contact else "",
        CREDIT_END)


def ensure_credit(doc):
    """Put exactly one credit inside <footer class="site"> (index and report pages)."""
    doc = re.sub(re.escape(CREDIT_START) + ".*?" + re.escape(CREDIT_END), "", doc, flags=re.S)
    m = re.search(r'(<footer class="site"><div class="wrap">.*?)(</div></footer>)', doc, re.S)
    if m:
        return doc[:m.end(1)] + credit_html() + doc[m.end(1):]
    idx = doc.lower().rfind("</body>")
    slim = '<footer class="site">' + '<div class="wrap">' + credit_html() + "</div></footer>\n"
    return doc[:idx] + slim + doc[idx:] if idx >= 0 else doc + slim


SPONSOR_CSS = """<style id="dd-spon-css">
.dd-spon,.dd-spon *,.dd-ban,.dd-ban *{box-sizing:border-box;margin:0;letter-spacing:normal;text-transform:none}
.dd-ban{--sc:var(--dd-accent,#f5a524);display:block;width:100%;font:500 14px/1.4 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;text-align:left}
.dd-ban .dd-ban-hd{display:flex;align-items:center;gap:8px;min-height:20px;margin:0 0 6px 2px}
.dd-ban button.dd-ban-mute{display:inline-flex;align-items:center;justify-content:center;width:22px;height:20px;padding:0;border:1px solid rgba(255,255,255,.18);border-radius:999px;
background:transparent;color:#b9b6ae;cursor:pointer;line-height:0}
.dd-ban button.dd-ban-mute:hover{color:#f1efe9;border-color:rgba(255,255,255,.35)}
.dd-ban button.dd-ban-mute:focus-visible{outline:2px solid var(--sc);outline-offset:2px}
.dd-ban button.dd-ban-mute.on{color:#0b0b0e;background:var(--sc);border-color:var(--sc)}
.dd-ban .dd-ban-mute .i-on,.dd-ban .dd-ban-mute.on .i-off{display:none}.dd-ban .dd-ban-mute.on .i-on{display:block}
.dd-ban .dd-ban-lab{display:block;margin:0;font:700 10px/1 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;letter-spacing:.16em;text-transform:uppercase;color:#8d8a83}
.dd-ban .dd-ban-box{position:relative;display:block;width:100%;aspect-ratio:4/1;overflow:hidden;border-radius:14px;border:1px solid rgba(255,255,255,.12);background:#111114;
container-type:inline-size;text-decoration:none!important;color:#f1efe9!important}
.dd-ban .dd-ban-box img,.dd-ban .dd-ban-box video{display:block;width:100%;height:100%;max-width:none;object-fit:cover}.dd-ban .dd-ban-box picture{display:block;width:100%;height:100%}.dd-ban .dd-ban-box video{pointer-events:none}.dd-ban video::-webkit-media-controls{display:none!important}
.dd-ban a.dd-ban-box:hover,.dd-ban a.dd-ban-box:focus-visible{border-color:var(--sc);outline:none}
.dd-ban .dd-ban-ph{border:1px dashed rgba(255,255,255,.22);
background:radial-gradient(120% 160% at 0% 0%,rgba(245,165,36,.16),transparent 55%),radial-gradient(120% 160% at 100% 100%,rgba(34,224,207,.12),transparent 55%),
repeating-linear-gradient(135deg,rgba(255,255,255,.035) 0 10px,transparent 10px 20px),#0f0f12}
.dd-ban .dd-ban-in{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1.1cqw;padding:0 6cqw;text-align:center}
.dd-ban .dd-ban-in b{font:800 clamp(15px,4.2cqw,46px)/1.05 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#f1efe9;letter-spacing:-.01em}
.dd-ban .dd-ban-in span{font:600 clamp(10.5px,1.55cqw,17px)/1.3 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#b9b6ae;letter-spacing:.04em}
.dd-ban .dd-ban-in .dd-ban-dim{display:inline-block;padding:.45em .9em;border:1px solid rgba(255,255,255,.18);border-radius:999px;color:#d5d1c8}
.dd-ban a.dd-ban-ph:hover .dd-ban-dim{border-color:var(--sc);color:#f1efe9}
.dd-ban .dd-ban-txt{flex-direction:row;justify-content:flex-start;gap:3cqw;text-align:left;padding:0 5cqw}
.dd-ban .dd-ban-txt img{flex:0 0 auto;width:13cqw;height:13cqw;border-radius:2cqw;object-fit:contain;background:#fff}
.dd-ban .dd-ban-txt span{display:block;font-weight:500;letter-spacing:0;color:#d5d1c8;font-size:clamp(11px,2cqw,22px)}
.dd-spon{--sc:var(--dd-accent,#f5a524);display:flex;align-items:center;flex-wrap:wrap;gap:8px 14px;margin-top:10px;padding:10px 14px;border:1px dashed rgba(255,255,255,.18);border-radius:14px;
background:rgba(255,255,255,.025);color:#b9b6ae;font:500 14px/1.4 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;text-align:left}
.dd-spon .dd-spon-txt{flex:1 1 220px;min-width:0;color:#d5d1c8}
.dd-spon .dd-spon-txt b{color:#f1efe9;font-weight:700}
.dd-spon a.dd-spon-btn{flex:0 0 auto;display:inline-flex;align-items:center;gap:6px;padding:8px 13px;border-radius:999px;border:1px solid var(--sc);color:#f1efe9!important;
text-decoration:none!important;font:600 13px/1.2 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;white-space:nowrap;background:transparent}
.dd-spon a.dd-spon-btn:hover,.dd-spon a.dd-spon-btn:focus-visible{background:rgba(255,255,255,.08);outline:none}
.dd-spon-wrap{margin:18px 0 0}
.dd-spon-wrap.dd-spon-rp{margin:0 0 16px}
.dd-spon-wrap.dd-spon-lk{margin:0 0 22px}
.dd-spon-wrap.dd-spon-ed{margin:0 0 22px;clear:both}
.dd-spon-strip{padding:12px 14px;background:#0b0b0e;border-bottom:1px solid rgba(255,255,255,.08)}
.dd-spon-strip>.dd-spon-in{max-width:1100px;margin:0 auto}
@media (max-width:620px){.dd-ban .dd-ban-box{border-radius:10px}.dd-spon{padding:9px 11px;gap:8px 10px;font-size:13.5px}.dd-spon a.dd-spon-btn{padding:7px 11px}}
</style>"""


def _in_dates(o, today):
    return not ((o.get("start") and today < o["start"]) or (o.get("end") and today > o["end"]))


def load_sponsor(slot="top"):
    """The first active sponsor in sponsors.json (inside its optional start/end dates) whose
    banner.placements (default ["top"]) includes slot ("top" or "links"), or None.
    The sponsor slot is display-only: nothing in it is read by item parsing or ranking."""
    p = os.path.join(REPO, SPONSORS_FILE)
    try:
        data = json.load(open(p, encoding="utf-8"))
    except (OSError, ValueError):
        return None
    today = dt.date.today().isoformat()
    for sp in data.get("sponsors", []):
        if not sp.get("active") or not sp.get("name") or not re.match(r"https?://", sp.get("url", "")):
            continue
        if not _in_dates(sp, today):
            continue
        ban = sp.get("banner") or {}
        places = ban.get("placements") or ["top"]
        if isinstance(places, str):
            places = [places]
        if slot not in places:
            continue
        sp = dict(sp, _banner=None)
        kind = (ban.get("type") or "image").lower()
        if (ban.get("active") and ban.get("image") and _in_dates(ban, today)
                and (kind != "video" or ban.get("poster"))):
            sp["_banner"] = ban
        return sp
    return None


def _asset(src, prefix):
    return src if re.match(r"https?://", src) else prefix + src.lstrip("/")


BANNER_VIDEO_JS = """<script>(function(){if(window.__ddBanV)return;window.__ddBanV=1;
function go(){var vs=[].slice.call(document.querySelectorAll("video.dd-ban-v"));if(!vs.length)return;
function btn(v){var b=v.closest(".dd-ban");return b&&b.querySelector(".dd-ban-mute")}
function sync(v){var b=btn(v);if(!b)return;b.setAttribute("aria-pressed",v.muted?"false":"true");b.setAttribute("aria-label",v.muted?"Unmute ad":"Mute ad");b.classList.toggle("on",!v.muted)}
function play(v){var p=v.play();if(p&&p.catch)p.catch(function(){})}
vs.forEach(function(v){v.muted=true;v.defaultMuted=true;v.loop=true;v.controls=false;v.removeAttribute("controls");sync(v);
 v.addEventListener("volumechange",function(){sync(v)});
 v.addEventListener("contextmenu",function(e){e.preventDefault()});
 v.addEventListener("pause",function(){if(!v.ended)play(v)});
 v.addEventListener("ended",function(){v.currentTime=0;play(v)});
 var b=btn(v);if(b)b.addEventListener("click",function(e){e.preventDefault();e.stopPropagation();v.muted=!v.muted;play(v);sync(v)});
 play(v)});
var CS=0;function css(){if(CS||document.getElementById("dd-fly-css"))return;CS=1;var s=document.createElement("style");s.id="dd-fly-css";s.textContent=
".dd-fly{position:fixed;left:0;top:0;margin:0;pointer-events:none;z-index:2147483600;will-change:transform,opacity;transform-origin:50% 50%;opacity:0}"+
".dd-fly span{position:absolute;inset:0;border-radius:50%;pointer-events:none}"+
".dd-fly .dd-fly-c{display:flex;align-items:center;justify-content:center;color:#fff;background:radial-gradient(circle at 30% 25%,#ffe3a3,#f5a524 38%,#ff4d8d 72%,#8b5cf6);box-shadow:0 0 0 4px rgba(255,255,255,.92),0 0 34px 10px rgba(245,165,36,.75),0 0 80px 26px rgba(255,77,141,.45)}"+
".dd-fly .dd-fly-c svg{display:block!important;width:64%;height:64%;margin-left:4%;filter:drop-shadow(0 2px 4px rgba(0,0,0,.45))}"+
".dd-fly .dd-fly-c .w1,.dd-fly .dd-fly-c .w2,.dd-fly .dd-fly-c .w3{animation:ddFlyW .6s ease-in-out infinite}.dd-fly .dd-fly-c .w2{animation-delay:.12s}.dd-fly .dd-fly-c .w3{animation-delay:.24s}"+
"@keyframes ddFlyW{0%,100%{opacity:.35}50%{opacity:1}}"+
".dd-fly .dd-fly-g{inset:-22%;background:radial-gradient(circle,rgba(255,226,150,.6),rgba(255,77,141,0) 66%);animation:ddFlyG .42s ease-in-out infinite alternate}"+
".dd-fly .dd-fly-r{border:4px solid #22e0cf;opacity:0;animation:ddFlyR .9s ease-out infinite}"+
".dd-fly .dd-fly-r.r2{animation-delay:.3s;border-color:#ffd27a}.dd-fly .dd-fly-r.r3{animation-delay:.6s;border-color:#ff4d8d}"+
"@keyframes ddFlyR{0%{transform:scale(1);opacity:.95}100%{transform:scale(2.2);opacity:0}}"+
"@keyframes ddFlyG{from{transform:scale(.88);opacity:.55}to{transform:scale(1.15);opacity:1}}"+
".dd-fly-hit{position:fixed;width:24px;height:24px;margin:-12px 0 0 -12px;border-radius:50%;pointer-events:none;z-index:2147483600;border:3px solid #ffd27a;box-shadow:0 0 18px 6px rgba(245,165,36,.85);animation:ddFlyHit .55s ease-out forwards}"+
"@keyframes ddFlyHit{0%{transform:scale(.5);opacity:1}100%{transform:scale(2.8);opacity:0}}"+
".dd-ban button.dd-ban-mute.dd-landed{animation:ddLand .5s cubic-bezier(.3,1.6,.5,1)}"+
"@keyframes ddLand{0%{transform:scale(1)}35%{transform:scale(1.6)}65%{transform:scale(.86)}100%{transform:scale(1)}}";
(document.head||document.body).appendChild(s)}
function fly(v,box,b){if(box.__ddFly)return;box.__ddFly=1;css();
 var S=Math.round(Math.max(64,Math.min(130,box.getBoundingClientRect().height*.8)));
 var el=document.createElement("div");el.className="dd-fly";el.setAttribute("aria-hidden","true");el.__ddBox=box;el.style.width=el.style.height=S+"px";
 var ic='<svg class="dd-fly-ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M2.5 9h4l5.5-4.8v15.6L6.5 15h-4z" fill="currentColor"/>'+
  '<path class="w1" d="M15 9a4.2 4.2 0 0 1 0 6" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" fill="none"/>'+
  '<path class="w2" d="M17.6 6.6a7.6 7.6 0 0 1 0 10.8" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" fill="none"/>'+
  '<path class="w3" d="M20.2 4.2a11 11 0 0 1 0 15.6" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" fill="none"/></svg>';
 el.innerHTML='<span class="dd-fly-r"></span><span class="dd-fly-r r2"></span><span class="dd-fly-r r3"></span><span class="dd-fly-g"></span><span class="dd-fly-c">'+ic+"</span>";
 document.body.appendChild(el);var T0=performance.now(),hit=0;
 function ez(t){return t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2}
 function step(now){var t=(now-T0)/1000,br=box.getBoundingClientRect(),bt=b.getBoundingClientRect();
  var sx=br.left+S*.62,sy=br.top+S*.62,ex=bt.left+bt.width/2,ey=bt.top+bt.height/2,es=Math.max(bt.width,bt.height)/S,x=sx,y=sy,sc=1,r=0,op=1,k;
  if(t<.3){k=t/.3;sc=k<.7?k/.7*1.2:1.2-(k-.7)/.3*.2;op=Math.min(1,k*3);r=-20*(1-k)}
  else if(t<.58){k=(t-.3)/.28;sc=1+.07*Math.sin(k*Math.PI*4);r=12*Math.sin(k*Math.PI*3)}
  else if(t<1.38){k=ez((t-.58)/.8);var u=1-k,cx=sx+(ex-sx)*.3+Math.min(240,br.width*.25),cy=Math.min(sy,ey)-Math.max(90,S*1.3);
   x=u*u*sx+2*u*k*cx+k*k*ex;y=u*u*sy+2*u*k*cy+k*k*ey;sc=1+(es-1)*k;r=360*k}
  else{x=ex;y=ey;sc=es;op=Math.max(0,1-(t-1.38)/.22)}
  el.style.transform="translate3d("+(x-S/2).toFixed(1)+"px,"+(y-S/2).toFixed(1)+"px,0) scale("+sc.toFixed(3)+") rotate("+r.toFixed(1)+"deg)";el.style.opacity=op;
  if(t>=1.38&&!hit){hit=1;var h=document.createElement("div");h.className="dd-fly-hit";h.setAttribute("aria-hidden","true");h.style.left=ex+"px";h.style.top=ey+"px";
   document.body.appendChild(h);setTimeout(function(){h.remove()},600);b.classList.remove("dd-landed");void b.offsetWidth;b.classList.add("dd-landed");
   setTimeout(function(){b.classList.remove("dd-landed")},520)}
  if(t<1.6)requestAnimationFrame(step);else{el.remove();box.__ddFly=0}}
 requestAnimationFrame(step)}
var touch=window.matchMedia&&(matchMedia("(hover: none)").matches||matchMedia("(pointer: coarse)").matches);
vs.forEach(function(v){var b=btn(v),box=v.closest(".dd-ban-box");if(!b||!box)return;
 if(touch&&window.IntersectionObserver){var arm=1;new IntersectionObserver(function(es){es.forEach(function(e){if(!e.isIntersecting||e.intersectionRatio<=0){arm=1;return}if(arm&&e.intersectionRatio>=.5){arm=0;fly(v,box,b)}})},{threshold:[0,.5,.75]}).observe(box)}
 else box.addEventListener("pointerenter",function(e){if(e.pointerType!=="touch")fly(v,box,b)})});
document.addEventListener("visibilitychange",function(){if(!document.hidden)vs.forEach(play)})}
if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",go);else go()})();</script>"""


MUTE_BTN = ('<button class="dd-ban-mute" type="button" aria-label="Unmute ad" aria-pressed="false" title="Sound on/off">'
            '<svg class="i-off" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/>'
            '<path d="M16 9l5 6M21 9l-5 6" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg>'
            '<svg class="i-on" viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M4 9h4l5-4v14l-5-4H4z" fill="currentColor"/>'
            '<path d="M16 8.5a5 5 0 0 1 0 7M18.5 6a8.5 8.5 0 0 1 0 12" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none"/></svg></button>')


def banner_has_audio(ban):
    """Whether a video banner has sound: probed with ffprobe for repo files, else the banner's "audio" flag."""
    src = ban.get("image") or ""
    if not re.match(r"https?://", src):
        f = os.path.join(REPO, src.lstrip("/"))
        if os.path.isfile(f) and shutil.which("ffprobe"):
            try:
                out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                                      "-of", "csv=p=0", f], capture_output=True, text=True, timeout=20).stdout
                return bool(out.strip())
            except (OSError, subprocess.SubprocessError):
                pass
    return bool(ban.get("audio"))


def placeholder_video(slot):
    """House video shown in an empty placement: sponsors.json "placeholders" -> {slot: {video, webm, poster, alt}}.
    Needs a poster and at least one of video (MP4) / webm, each an https URL or an existing repo file; otherwise None
    (the 'Your ad here' card is shown)."""
    try:
        ph = (json.load(open(os.path.join(REPO, SPONSORS_FILE), encoding="utf-8")).get("placeholders") or {}).get(slot) or {}
    except (OSError, ValueError):
        return None
    def ok(v):
        return bool(v) and (re.match(r"https?://", v) or os.path.isfile(os.path.join(REPO, v.lstrip("/"))))
    mp4, webm, poster = ph.get("video") or "", ph.get("webm") or "", ph.get("poster") or ""
    if not ok(poster) or not (ok(mp4) or ok(webm)):
        return None
    return {"type": "video", "image": mp4 if ok(mp4) else webm, "webm": webm if (ok(webm) and ok(mp4)) else "",
            "poster": poster, "alt": ph.get("alt") or "", "audio": ph.get("audio")}


def _vtype(src):
    return "video/webm" if src.lower().split("?")[0].endswith(".webm") else "video/mp4"


def banner_media(ban, prefix, alt):
    """The sponsor's banner media. type: "image" (default), "animated" (GIF / animated WebP) or "video" (MP4 / WebM).
    Animated plays right away; video autoplays muted on load, loops endlessly and has no controls (poster shows only until the first frame).
    Video is always muted, inline, looping, without controls, and only loads/plays when near the viewport."""
    kind = (ban.get("type") or "image").lower()
    src = _asset(ban["image"], prefix)
    poster = _asset(ban["poster"], prefix) if ban.get("poster") else ""
    if kind == "video" and poster:
        return ('<video class="dd-ban-v" autoplay muted playsinline webkit-playsinline loop preload="auto" disablepictureinpicture disableremoteplayback '
                'controlslist="nodownload nofullscreen noplaybackrate noremoteplayback" tabindex="-1" draggable="false" '
                'poster="%s" width="1200" height="300" aria-label="%s">%s<source src="%s" type="%s"></video>%s') % (
            esc(poster), esc(alt),
            ('<source src="%s" type="video/webm">' % esc(_asset(ban["webm"], prefix))) if ban.get("webm") else "",
            esc(src), _vtype(src), BANNER_VIDEO_JS)
    if kind == "animated":
        return '<img src="%s" alt="%s" width="1200" height="300" loading="eager" decoding="async" draggable="false">' % (esc(src), esc(alt))
    still = poster if kind == "video" else src  # a video without a poster is not shown as video
    return '<img src="%s" alt="%s" width="1200" height="300" loading="lazy" decoding="async">' % (esc(still), esc(alt))


def sponsor_html(prefix="", wrap="dd-spon-wrap", slot="top"):
    """Sponsor block near the top of the index, report pages and editions (between markers):
    1) the 4:1 landscape sponsor banner (1200x300): the sponsor's banner image, a text card if it has none,
       or with no active sponsor a placeholder 'Your ad here' template linking to the contact page;
    2) below it, a short 'Sponsor Daily Design' invite linking to the contact page."""
    sp = load_sponsor(slot)
    if sp and sp.get("_banner"):
        ban = sp["_banner"]
        url = ban.get("url") if re.match(r"https?://", ban.get("url") or "") else sp["url"]
        media = banner_media(ban, prefix, ban.get("alt") or ("Sponsored: " + sp["name"]))
        mute = MUTE_BTN if ("<video" in media and banner_has_audio(ban)) else ""
        banner = ('<div class="dd-ban" role="complementary" aria-label="Sponsored"><div class="dd-ban-hd"><span class="dd-ban-lab">Sponsored</span>%s</div>'
                  '<a class="dd-ban-box" href="%s" rel="sponsored noopener" target="_blank">%s</a></div>') % (mute, esc(url), media)
    elif sp:
        logo = sp.get("logo") or ""
        img = ('<img src="%s" alt="" width="120" height="120" loading="lazy">' % esc(_asset(logo, prefix))) if logo else ""
        banner = ('<div class="dd-ban" role="complementary" aria-label="Sponsored"><div class="dd-ban-hd"><span class="dd-ban-lab">Sponsored</span></div>'
                  '<a class="dd-ban-box" href="%s" rel="sponsored noopener" target="_blank"><span class="dd-ban-in dd-ban-txt">%s'
                  '<span><b>%s</b>%s</span></span></a></div>') % (
            esc(sp["url"]), img, esc(sp["name"]), ("<span>" + esc(sp["line"]) + "</span>") if sp.get("line") else "")
    elif placeholder_video(slot):
        ph = placeholder_video(slot)
        media = banner_media(ph, prefix, ph.get("alt") or "Advertise on Daily Design")
        mute = MUTE_BTN if ("<video" in media and banner_has_audio(ph)) else ""
        banner = ('<div class="dd-ban" role="complementary" aria-label="Advertising space"><div class="dd-ban-hd"><span class="dd-ban-lab">Ad space</span>%s</div>'
                  '<a class="dd-ban-box" href="%s%s#sponsor">%s</a></div>') % (mute, prefix, CONTACT_PATH, media)
    else:
        banner = ('<div class="dd-ban" role="complementary" aria-label="Advertising space"><div class="dd-ban-hd"><span class="dd-ban-lab">Ad space</span></div>'
                  '<a class="dd-ban-box dd-ban-ph" href="%s%s#sponsor"><span class="dd-ban-in"><b>Your ad here</b>'
                  '<span class="dd-ban-dim">1200 × 300 banner</span></span></a></div>') % (prefix, CONTACT_PATH)
    invite = ('<aside class="dd-spon" aria-label="Sponsor Daily Design">'
              '<span class="dd-spon-txt"><b>Sponsor Daily Design.</b> Reach people who make things with AI. '
              'Sponsors never affect what we pick or how it ranks.</span>'
              '<a class="dd-spon-btn" href="%s%s#sponsor">Get in touch →</a></aside>') % (prefix, CONTACT_PATH)
    start, end, css = (SPON2_START, SPON2_END, "") if slot == "links" else (SPON_START, SPON_END, SPONSOR_CSS)
    return ('%s%s<div class="%s"><div class="dd-spon-in">%s%s</div></div>%s') % (
        start, css, wrap, banner, invite, end)


def put_sponsor(doc, anchor_re, prefix="", wrap="dd-spon-wrap"):
    doc = re.sub(r"\n?" + re.escape(SPON_START) + ".*?" + re.escape(SPON_END) + r"\n?", "", doc, flags=re.S)
    return re.sub(anchor_re, lambda m: m.group(0) + "\n" + sponsor_html(prefix, wrap) + "\n", doc, count=1)


def icon_links(prefix):
    """Favicon + touch icon + manifest links. prefix is the path back to the site root ("" or "../../")."""
    a = prefix + "assets/"
    return ('%s<link rel="icon" href="%sfavicon.ico" sizes="32x32">'
            '<link rel="icon" href="%sfavicon.svg" type="image/svg+xml">'
            '<link rel="icon" href="%sfavicon-32.png" type="image/png" sizes="32x32">'
            '<link rel="apple-touch-icon" href="%sapple-touch-icon.png">'
            '<link rel="manifest" href="%ssite.webmanifest">%s') % (ICON_START, a, a, a, a, a, ICON_END)
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
#dd-foot .dd-credit{flex-basis:100%%;margin-top:14px;text-align:center;font:500 13px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#8d8a83}
#dd-foot .dd-credit-ic{display:inline-block;width:16px;height:16px;vertical-align:-3px;margin:0 5px 0 1px;border-radius:3px}
#dd-foot .dd-credit a{display:inline;white-space:nowrap;padding:0;border:0;border-radius:0;color:#ecebe8!important;text-decoration:underline!important;text-decoration-color:var(--dd-accent)!important;text-underline-offset:3px}
#dd-foot .dd-brand{white-space:nowrap;font-weight:700}#dd-foot .dd-brand-ic{display:inline-block;width:1.1em;height:1.1em;vertical-align:-.2em;margin:0 .3em 0 0;border-radius:3px}#dd-foot .dd-brand .c0{color:#f5a524}#dd-foot .dd-brand .c1{color:#22e0cf}#dd-foot .dd-brand .c2{color:#9b6bff}#dd-foot .dd-brand .c3{color:#ff5a2e}
#dd-foot .dd-contactln{flex-basis:100%%;margin-top:2px;text-align:center;font:500 13px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:#8d8a83}
#dd-foot .dd-contactln a{display:inline;padding:0;border:0;border-radius:0;color:#ecebe8!important;text-decoration:underline!important;text-decoration-color:var(--dd-accent)!important;text-underline-offset:3px;font-weight:700}
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


def inject_nav(doc, ed, prev, nxt, items=()):
    for a, b in ((NAV_START, NAV_END), (FOOT_START, FOOT_END), (STYLE_START, STYLE_END), (ICON_START, ICON_END), (CREDIT_START, CREDIT_END), (SPON_START, SPON_END), (SPON2_START, SPON2_END)):
        doc = re.sub(re.escape(a) + ".*?" + re.escape(b) + r"\n?", "", doc, flags=re.S)
    s = SLOTS[ed["slot"]]
    bar = ('%s<nav id="dd-nav" aria-label="Daily Design"><a class="dd-home" href="../../index.html">← <span class="dd-t">Back to </span>index</a>'
           '<span class="dd-lab"><b>%s</b>%s · %s</span>%s%s%s</nav>%s\n') % (
        NAV_START, esc(s["time"]), esc(s["name"]), esc(nice_date(ed["date"])), TTS_BUTTONS,
        nav_link(prev, "dd-prev", '‹ <span class="dd-t">Prev</span>', True),
        nav_link(nxt, "dd-next", '<span class="dd-t">Next</span> ›', False), NAV_END)
    foot = ('%s<div id="dd-foot">%s<a class="dd-home" href="../../index.html">← Back to the Daily Design index</a>%s%s</div>%s\n') % (
        FOOT_START, nav_link(prev, "dd-prev", "‹ Previous edition", True),
        nav_link(nxt, "dd-next", "Next edition ›", False), credit_html("../../"), FOOT_END)
    if ed.get("header"):  # the page may point at the source file name (<date>-<slot>-header.png); the repo copy is <slot>-header.png
        hb = os.path.basename(ed["header"])
        doc = doc.replace('src="%s-%s"' % (ed["date"], hb), 'src="%s"' % hb)
    doc = ensure_lang(strip_head_seo(doc))
    doc = re.sub(r"(<meta[^>]*charset[^>]*>)", lambda m: m.group(1) + "\n" + seo_block(ed, items), doc, count=1, flags=re.I)
    if SEO_START not in doc:
        doc = re.sub(r"(<head[^>]*>)", lambda m: m.group(1) + "\n" + seo_block(ed, items), doc, count=1, flags=re.I)
    doc = re.sub(r"</head>", lambda m: icon_links("../../") + "\n" + nav_css(s["color"]) + "\n</head>", doc, count=1, flags=re.I)
    doc = re.sub(r"(<body[^>]*>)", lambda m: m.group(1) + "\n" + bar + sponsor_html("../../", "dd-spon-strip") + "\n", doc, count=1, flags=re.I)
    # second ad spot (its own independent copy of the lower ad): just before the edition's in-numbers block (#charts)
    doc = re.sub(r'<section\b[^>]*\bid="charts"[^>]*>', lambda m: sponsor_html("../../", "dd-spon-wrap dd-spon-ed", "links") + "\n" + m.group(0), doc, count=1)
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


# ---------------------------------------------------------------- SEO, static report pages, sitemap, feed
SEO_START, SEO_END = "<!--dd-seo:start-->", "<!--dd-seo:end-->"
LATEST_START, LATEST_END = "<!--dd-latest:start-->", "<!--dd-latest:end-->"
STATIC_START, STATIC_END = "<!--dd-static:start-->", "<!--dd-static:end-->"
SITE_NAME = "Daily Design"
SITE_DESC = ("Four editions a day on how AI is changing creative work: image, video, 3D, code/UI, sound, games "
             "and mashups. Every edition and every link, searchable and tagged.")
SLOT_HOUR = {"morning": 7, "noon": 12, "best": 18, "hottest": 20}
MEDIUM_LABEL = {k: l for k, l, _ in MEDIUMS}


def abs_url(path):
    return SITE_URL + path.lstrip("/")


def clip(s, n):
    s = re.sub(r"\s+", " ", s or "").strip()
    if len(s) <= n:
        return s
    cut = s[:n - 1].rsplit(" ", 1)[0].rstrip(",;:·-—")
    return cut + "…"


def published_iso(ed):
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime(*map(int, ed["date"].split("-")), SLOT_HOUR[ed["slot"]],
                           tzinfo=ZoneInfo("America/Vancouver")).isoformat()
    except Exception:
        return ed["date"]


def public_path(ed):
    """The crawlable URL path of an edition: the HTML page, or the static page of a report."""
    return ed["path"] if ed["kind"] == "page" else "reports/%s/%s.html" % (ed["date"], ed["slot"])


def report_story(md):
    """First H2 of a report (its real headline), skipping section labels like 'Pick of the day'."""
    for m in re.finditer(r"^##\s+(.+)$", md, re.M):
        t = strip_md(m.group(1))
        t = re.sub(r"^[^\w\"'“]+", "", t).strip()
        if t and not re.match(r"(?i)(pick of the day|the ranked picks|blew up today|hottest this|method)", t):
            return t
    return ""


def seo_fields(ed, items=(), story=""):
    s = SLOTS[ed["slot"]]
    day = dt.date.fromisoformat(ed["date"]).strftime("%b %-d, %Y")
    if not story and ed["kind"] == "report":
        mdp = os.path.join(REPO, ed["path"])
        story = report_story(open(mdp, encoding="utf-8").read()) if os.path.exists(mdp) else ""
    lead = story or (ed["headline"] if ed["kind"] == "page" else "")
    title = ("%s · %s, %s · %s" % (lead, s["name"], day, SITE_NAME)) if lead else \
            ("%s · %s · %s" % (s["name"], day, SITE_NAME))
    desc = ed.get("summary") or ""
    if not desc:
        desc = "%s %s for %s: %d linked items on how AI is changing creative work." % (
            s["time"], s["name"], day, ed.get("item_count", 0))
    meds = [MEDIUM_LABEL[t] for t in ed.get("tags", []) if t in MEDIUM_LABEL]
    types = []
    for it in items:
        if it.get("type") and it["type"] not in types:
            types.append(it["type"])
    keywords = ["AI design", "generative AI", s["name"]] + meds + types[:6]
    return dict(title=title, desc=clip(desc, 158), headline=clip(lead or ed["headline"], 110),
                keywords=keywords, url=abs_url(public_path(ed)),
                image=abs_url(ed["header"]) if ed.get("header") else abs_url("assets/favicon-512.png"),
                published=published_iso(ed), section=s["name"])


def ld_json(obj):
    return ('<script type="application/ld+json">%s</script>' %
            json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))


def studio_ld():
    return {"@type": "Organization", "name": STUDIO_NAME, "url": STUDIO_URL}


def publisher_ld():
    return {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL, "parentOrganization": studio_ld(),
            "logo": {"@type": "ImageObject", "url": abs_url("assets/favicon-512.png"), "width": 512, "height": 512}}


def seo_block(ed, items=(), story=""):
    f = seo_fields(ed, items, story)
    art = {"@context": "https://schema.org", "@type": "NewsArticle", "headline": f["headline"],
           "description": f["desc"], "datePublished": f["published"], "dateModified": f["published"],
           "image": [f["image"]], "url": f["url"], "mainEntityOfPage": {"@type": "WebPage", "@id": f["url"]},
           "author": {"@type": "Organization", "name": SITE_NAME, "url": SITE_URL},
           "creator": studio_ld(), "copyrightHolder": studio_ld(), "publisher": publisher_ld(), "articleSection": f["section"], "keywords": ", ".join(f["keywords"]),
           "inLanguage": "en", "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": SITE_URL}}
    tags = [
        '<title>%s</title>' % esc(f["title"]),
        '<meta name="description" content="%s">' % esc(f["desc"]),
        '<meta name="keywords" content="%s">' % esc(", ".join(f["keywords"])),
        '<link rel="canonical" href="%s">' % esc(f["url"]),
        '<meta name="robots" content="index,follow,max-image-preview:large">',
        '<meta property="og:type" content="article">',
        '<meta property="og:site_name" content="%s">' % SITE_NAME,
        '<meta property="og:title" content="%s">' % esc(f["title"]),
        '<meta property="og:description" content="%s">' % esc(f["desc"]),
        '<meta property="og:url" content="%s">' % esc(f["url"]),
        '<meta property="og:image" content="%s">' % esc(f["image"]),
        '<meta property="og:image:alt" content="%s header chart">' % esc(f["section"]),
        '<meta property="og:locale" content="en_US">',
        '<meta property="article:published_time" content="%s">' % f["published"],
        '<meta property="article:section" content="%s">' % esc(f["section"]),
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="%s">' % esc(f["title"]),
        '<meta name="twitter:description" content="%s">' % esc(f["desc"]),
        '<meta name="twitter:image" content="%s">' % esc(f["image"]),
        '<link rel="alternate" type="application/atom+xml" title="%s feed" href="%s">' % (SITE_NAME, abs_url("feed.xml")),
        ld_json(art)]
    return SEO_START + "".join(tags) + SEO_END


def strip_head_seo(doc):
    """Remove the page's own title/description/social/canonical tags so ours are the only ones."""
    doc = re.sub(re.escape(SEO_START) + ".*?" + re.escape(SEO_END) + r"\n?", "", doc, flags=re.S)
    doc = re.sub(r"<title[^>]*>.*?</title>\s*", "", doc, flags=re.S | re.I)
    doc = re.sub(r"<meta\s+(?:name|property)=\"(?:description|keywords|robots|og:[^\"]*|twitter:[^\"]*|article:[^\"]*)\"[^>]*>\s*",
                 "", doc, flags=re.I)
    doc = re.sub(r"<link\s+rel=\"canonical\"[^>]*>\s*", "", doc, flags=re.I)
    return doc


def ensure_lang(doc):
    if re.search(r"<html\b[^>]*\blang=", doc, re.I):
        return doc
    return re.sub(r"<html\b", '<html lang="en"', doc, count=1, flags=re.I)


# ---- a small Markdown renderer for the static report pages (reports use plain, simple Markdown)
def md_inline(t):
    codes = []
    t = re.sub(r"`([^`]+)`", lambda m: codes.append(m.group(1)) or "\x00%d\x00" % (len(codes) - 1), t)
    t = esc(t).replace("&#x27;", "'")
    t = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: '<img src="%s" alt="%s" loading="lazy">' % (m.group(2), m.group(1)), t)

    def link(m):
        url = m.group(2)
        if re.match(r"(?i)\s*(javascript|vbscript|data):", html.unescape(url)):
            return m.group(1)
        ext = ' rel="noopener"' if re.match(r"https?:", url) else ""
        return '<a href="%s"%s>%s</a>' % (url, ext, m.group(1))
    t = re.sub(r"\[([^\]]+)\]\(([^)\s]+(?:\([^)\s]*\)[^)\s]*)*)\)", link, t)
    t = re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: "<strong>%s</strong>" % (m.group(1) or m.group(2)), t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"<em>\1</em>", t)
    t = re.sub(r"(?<![\w_])_(?!\s)(.+?)(?<!\s)_(?!\w)", r"<em>\1</em>", t)
    return re.sub(r"\x00(\d+)\x00", lambda m: "<code>%s</code>" % esc(codes[int(m.group(1))]), t)


def md_to_html(md):
    lines = md.replace("\r\n", "\n").split("\n")
    out, para, i = [], [], 0

    def flush():
        if para:
            out.append("<p>%s</p>" % md_inline(" ".join(x.strip() for x in para)))
            para.clear()
    while i < len(lines):
        l = lines[i]
        if not l.strip():
            flush(); i += 1; continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", l)
        if m:
            flush(); n = len(m.group(1))
            out.append("<h%d>%s</h%d>" % (n, md_inline(m.group(2)), n)); i += 1; continue
        if re.match(r"^\s{0,3}([-*_])(\s*\1){2,}\s*$", l):
            flush(); out.append("<hr>"); i += 1; continue
        if l.lstrip().startswith(">"):
            flush(); q = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                q.append(re.sub(r"^\s*>\s?", "", lines[i])); i += 1
            out.append("<blockquote>%s</blockquote>" % md_to_html("\n".join(q))); continue
        if l.lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", lines[i + 1]):
            flush(); rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")]); i += 1
            head, body = rows[0], rows[2:]
            out.append("<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (
                "".join("<th>%s</th>" % md_inline(c) for c in head),
                "".join("<tr>%s</tr>" % "".join("<td>%s</td>" % md_inline(c) for c in r) for r in body)))
            continue
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", l)
        if m:
            flush(); ordered = m.group(2)[0].isdigit(); items = []
            while i < len(lines):
                mm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", lines[i])
                if mm and len(mm.group(1)) <= len(m.group(1)) + 1:
                    items.append(mm.group(3)); i += 1
                elif lines[i].strip() and (lines[i].startswith((" ", "\t")) or mm):
                    items[-1] += " " + lines[i].strip().lstrip("-*+ ").strip(); i += 1
                else:
                    break
            tag = "ol" if ordered else "ul"
            out.append("<%s>%s</%s>" % (tag, "".join("<li>%s</li>" % md_inline(x) for x in items), tag))
            continue
        para.append(l); i += 1
    flush()
    return "\n".join(out)


REPORT_CSS = """<style>
.rp{max-width:980px;margin:0 auto;padding:18px 14px 40px}
.rp-top{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;margin:0 0 16px}
.rp-top a{color:var(--mut);font:600 13px var(--sans);text-decoration:none}.rp-top a:hover{color:#fff}
.rp-top a.btn{color:var(--ink)}
.rp .reader{margin:0}
</style>"""


def report_page(ed, md, items):
    s = SLOTS[ed["slot"]]
    body = md_to_html(md)
    gh = REPO_BLOB + ed["path"]
    key = "%s/%s" % (ed["date"], ed["slot"])
    return ("""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#09090c">
%s
%s
<link rel="stylesheet" href="../../assets/site.css">
%s
</head>
<body>
<main class="rp">
<nav class="rp-top" aria-label="Daily Design"><a class="btn" href="../../index.html">← Daily Design index</a><a href="../../#report=%s">Open in the index reader</a></nav>
%s
<section class="reader" style="--c:%s" aria-label="Report">
<div class="rd-bar"><div class="rd-kick"><span class="dot"></span>%s · %s · %s <b>Report</b></div><div class="rd-acts">%s<a class="rd-gh" href="%s" rel="noopener">View on GitHub ↗</a></div></div>
<article class="rd-body" data-tts-root>
%s
</article>
<div class="rd-foot"><a class="btn" href="../../index.html">← Back to the Daily Design index</a></div>
</section>
</main>
<footer class="site"><div class="wrap">Daily Design is a public archive of AI design research digests. Links go to the original creators and sources; engagement numbers were read when each edition was compiled and will have changed since.%s</div></footer>
<script src="../../assets/tts.js" defer></script>
</body>
</html>
""") % (seo_block(ed, items, report_story(md)), icon_links("../../"), REPORT_CSS, key,
        sponsor_html("../../", "dd-spon-wrap dd-spon-rp"), s["color"],
        esc(s["time"]), esc(s["name"]), esc(nice_date(ed["date"])), REPORT_TTS, esc(gh), body, credit_html("../../"))


REPORT_TTS = ('<button class="btn rd-tts" id="dd-tts-play" type="button" hidden aria-label="Listen: read this page aloud" aria-pressed="false">'
              '<span class="tts-i" aria-hidden="true">▶</span> <span class="tts-l">Listen</span></button>'
              '<button class="btn rd-tts" id="dd-tts-stop" type="button" hidden aria-label="Stop reading"><span aria-hidden="true">■</span> Stop</button>')


def build_report_pages(recs):
    pages = []
    for r in recs:
        e = r["edition"]
        if e["kind"] != "report":
            continue
        mdp = os.path.join(REPO, e["path"])
        if not os.path.exists(mdp):
            continue
        dest = os.path.join(REPO, public_path(e))
        if write_if_changed(dest, report_page(e, open(mdp, encoding="utf-8").read(), r["items"])):
            log("report page", public_path(e))
        pages.append(public_path(e))
    return pages


SPECIAL_TYPES = ("maintenance", "launch")


def load_special_days(days):
    """Special days from tools/special-days.json -> [{date, type}] for index.json, newest first.
    type 'maintenance' (default): red on the archive calendars, never published; dropped if the date has an edition.
    type 'launch': aqua-green on the calendars; kept either way (a launch day with editions stays clickable).
    Bad entries are skipped."""
    p = os.path.join(REPO, "tools", "special-days.json")
    try:
        raw = json.load(open(p, encoding="utf-8")).get("days", [])
    except FileNotFoundError:
        return []
    out = {}
    for d in raw:
        t = (d.get("type") or "maintenance") if isinstance(d, dict) else "maintenance"
        d = d.get("date") if isinstance(d, dict) else d
        if not (isinstance(d, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) and t in SPECIAL_TYPES):
            continue
        if t == "maintenance" and d in days:
            continue
        out[d] = t
    return [dict(date=d, type=out[d]) for d in sorted(out, reverse=True)]


def build_index_seo(editions):
    """Head tags, JSON-LD and crawlable static links in index.html (between markers)."""
    p = os.path.join(REPO, "index.html")
    doc = open(p, encoding="utf-8").read()
    latest = editions[0] if editions else None
    img = abs_url(latest["header"]) if latest and latest.get("header") else abs_url("assets/favicon-512.png")
    parts = []
    for n, e in enumerate(editions[:30], 1):
        f = seo_fields(e)
        parts.append({"@type": "ListItem", "position": n, "url": f["url"], "name": f["title"].rsplit(" · ", 1)[0]})
    ld = [{"@context": "https://schema.org", "@type": "WebSite", "name": SITE_NAME, "url": SITE_URL,
           "description": SITE_DESC, "inLanguage": "en", "publisher": publisher_ld(), "creator": studio_ld(),
           "potentialAction": {"@type": "SearchAction", "target": SITE_URL + "#q={search_term_string}",
                               "query-input": "required name=search_term_string"}},
          {"@context": "https://schema.org", "@type": "CollectionPage", "name": "Daily Design: the index",
           "url": SITE_URL, "description": SITE_DESC, "inLanguage": "en",
           "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": SITE_URL},
           "dateModified": published_iso(latest) if latest else None,
           "mainEntity": {"@type": "ItemList", "numberOfItems": len(editions), "itemListElement": parts}}]
    title = "Daily Design · AI design research digests, searchable"
    head = SEO_START + "".join([
        '<title>%s</title>' % title,
        '<meta name="description" content="%s">' % esc(SITE_DESC),
        '<link rel="canonical" href="%s">' % SITE_URL,
        '<meta name="robots" content="index,follow,max-image-preview:large">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="%s">' % SITE_NAME,
        '<meta property="og:title" content="%s">' % esc(title),
        '<meta property="og:description" content="%s">' % esc(SITE_DESC),
        '<meta property="og:url" content="%s">' % SITE_URL,
        '<meta property="og:image" content="%s">' % esc(img),
        '<meta property="og:locale" content="en_US">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="twitter:title" content="%s">' % esc(title),
        '<meta name="twitter:description" content="%s">' % esc(SITE_DESC),
        '<meta name="twitter:image" content="%s">' % esc(img),
        '<link rel="alternate" type="application/atom+xml" title="Daily Design feed" href="%s">' % abs_url("feed.xml"),
        "".join(ld_json(x) for x in ld)]) + SEO_END
    doc = strip_head_seo(doc)
    doc = re.sub(r"(<meta name=\"viewport\"[^>]*>)", lambda m: m.group(1) + "\n" + head, doc, count=1)
    # latest day: plain links inside #latest (the app replaces them once it loads)
    day = latest["date"] if latest else ""
    cards = "".join('<a class="static-ed" href="%s"><b>%s · %s</b> %s</a>' % (
        esc(public_path(e)), esc(e["time"]), esc(e["title"]), esc(seo_fields(e)["headline"]))
        for e in editions if e["date"] == day)
    doc = re.sub(re.escape(LATEST_START) + ".*?" + re.escape(LATEST_END), lambda m: LATEST_START + cards + LATEST_END, doc, flags=re.S)
    if LATEST_START not in doc:
        doc = doc.replace('<div class="daygrid big" id="latest">', '<div class="daygrid big" id="latest">' + LATEST_START + cards + LATEST_END, 1)
    lis = "".join('<li><a href="%s">%s</a></li>' % (esc(public_path(e)), esc(seo_fields(e)["title"].rsplit(" · ", 1)[0]))
                  for e in editions[:200])
    static = (STATIC_START + '<noscript><section class="wrap block"><h2>All editions</h2><ul>%s</ul>'
              '<p><a href="feed.xml">Atom feed</a> · <a href="sitemap.xml">Sitemap</a> · <a href="contact.html">Contact</a></p></section></noscript>' + STATIC_END) % lis
    doc = re.sub(re.escape(STATIC_START) + ".*?" + re.escape(STATIC_END), lambda m: static, doc, flags=re.S)
    if STATIC_START not in doc:
        doc = doc.replace('<footer class="site">', static + "\n" + '<footer class="site">', 1)
    doc = put_sponsor(doc, r'<main class="wrap" id="results">')
    # second combo: first thing inside the Recent links section, so it moves with it when app.js reorders the archive
    doc = re.sub(re.escape(SPON2_START) + ".*?" + re.escape(SPON2_END), "", doc, flags=re.S)
    doc = doc.replace('<section class="block" id="items-block">',
                      '<section class="block" id="items-block">' + sponsor_html("", "dd-spon-wrap dd-spon-lk", "links"), 1)
    doc = ensure_credit(doc)
    if write_if_changed(p, doc):
        log("index.html SEO updated")


CONTACT_CSS = """<style>
.ct{max-width:760px;margin:0 auto;padding:18px 16px 50px}
.ct-top{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;margin:0 0 20px}
.ct-top a{color:var(--mut);font:600 13px var(--sans);text-decoration:none}.ct-top a:hover{color:#fff}.ct-top a.btn{color:var(--ink)}
.ct-card{position:relative;overflow:hidden;background:linear-gradient(180deg,#121219,#0d0d12);border:1px solid var(--line2);border-top:3px solid var(--amber);border-radius:20px;padding:30px 26px 28px}
.ct-card:before{content:"";position:absolute;inset:-60% -20% auto -20%;height:300px;pointer-events:none;
background:radial-gradient(40% 60% at 20% 50%,rgba(245,165,36,.16),transparent 70%),radial-gradient(35% 55% at 55% 30%,rgba(34,224,207,.10),transparent 70%),radial-gradient(35% 55% at 90% 40%,rgba(155,107,255,.14),transparent 70%)}
.ct-card>*{position:relative}
.ct .eyebrow{margin:0 0 12px}
.ct h1{font:400 clamp(38px,7vw,64px)/.95 var(--serif);letter-spacing:-.03em;margin:0 0 14px}
.ct h1 em{font-style:italic;background:linear-gradient(90deg,var(--amber),var(--aqua) 35%,var(--violet) 68%,var(--flame));-webkit-background-clip:text;background-clip:text;color:transparent;padding-right:.06em}
.ct .lede{font:300 clamp(17px,2.2vw,20px)/1.5 var(--sans);color:#d5d1c8;margin:0 0 22px;max-width:600px}
.ct-mail{display:flex;flex-wrap:wrap;align-items:center;gap:10px}
.ct-addr{flex:1 1 300px;min-width:0;display:block;padding:14px 16px;border:1px solid var(--line2);border-radius:12px;background:#09090c;color:var(--ink);
font:600 clamp(16px,2.6vw,19px)/1.3 var(--mono);overflow-wrap:anywhere;user-select:all;-webkit-user-select:all;cursor:text}
.ct-btns{display:flex;flex-wrap:wrap;gap:10px}
.ct .btn{display:inline-flex;align-items:center;gap:8px;text-decoration:none;font-size:14px;padding:13px 16px}
.ct .btn.pri{background:var(--amber);border-color:transparent;color:#0b0b0e;font-weight:800}.ct .btn.pri:hover{background:#ffb94a}
.ct-ok{min-height:20px;margin:10px 0 0;font:600 13px var(--sans);color:var(--aqua)}
.ct-sec{margin:28px 0 0;display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.ct-sec div{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:16px}
.ct-sec h2{font:700 11px/1 var(--sans);letter-spacing:.16em;text-transform:uppercase;color:var(--mut);margin:0 0 8px}
.ct-sec p{margin:0;color:#d5d1c8;font-size:15px;line-height:1.5}
.ct-sp{scroll-margin-top:20px;margin:28px 0 0;padding:20px;border:1px dashed var(--line2);border-radius:16px}
.ct-sp h2{font:400 28px/1.1 var(--serif);margin:0 0 8px}.ct-sp p{margin:0 0 14px;color:#d5d1c8}
.ct-rates{margin:6px 0 16px}
.ct-rates-h h3{font:700 11px/1.3 var(--sans);letter-spacing:.16em;text-transform:uppercase;color:var(--amber);margin:0 0 10px}
.ct-rates-h p{margin:-4px 0 10px;font-size:13px;color:var(--mut)}
.ct-rgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.ct-rate{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 15px 12px;display:flex;flex-direction:column}
.ct-rate h3{font:700 15px/1.25 var(--sans);color:var(--ink);margin:0 0 4px}
.ct-rate>p{margin:0 0 10px!important;font-size:13px!important;line-height:1.45;color:var(--mut)!important}
.ct-rate dl{margin:auto 0 0;display:grid;grid-template-rows:auto auto;grid-auto-flow:column;grid-auto-columns:minmax(0,1fr);column-gap:10px;align-items:end;border-top:1px solid var(--line);padding-top:10px}
.ct-rate dl div{display:contents}
.ct-rate dt{font:600 10.5px/1.2 var(--sans);letter-spacing:.1em;text-transform:uppercase;color:var(--mut);margin:0 0 4px}
.ct-rate dd{margin:0;font:700 22px/1 var(--sans);color:var(--ink)}.ct-rate dd small{font:500 12px var(--sans);color:var(--mut);margin-left:2px}
.ct-rate:nth-child(2) dd{color:var(--ink)}
.ct-spec{margin:0 0 16px;border:1px solid var(--line);border-radius:12px;padding:10px 14px;background:#0b0b0f}
.ct-spec summary{cursor:pointer;font:600 14px var(--sans);color:var(--ink)}
.ct-spec ul{margin:10px 0 2px;padding-left:18px;color:#d5d1c8;font-size:14px;line-height:1.5}.ct-spec li{margin:0 0 6px}
@media (max-width:640px){.ct-rgrid{grid-template-columns:1fr}}
@media (max-width:640px){.ct-card{padding:24px 16px 22px;border-radius:16px}.ct-btns{width:100%}.ct-btns .btn{flex:1 1 0;justify-content:center}}
</style>"""

CONTACT_JS = """<script>(function(){var A="%s",ok=document.getElementById("ct-ok"),el=document.getElementById("ct-addr"),b=document.getElementById("ct-copy");
function say(t){ok.textContent=t;clearTimeout(say.t);say.t=setTimeout(function(){ok.textContent=""},2600)}
function sel(){var r=document.createRange();r.selectNodeContents(el);var s=getSelection();s.removeAllRanges();s.addRange(r)}
function legacy(){sel();var d=false;try{d=document.execCommand("copy")}catch(e){}say(d?"Copied":"Selected. Press Ctrl+C or ⌘C to copy.")}
b.hidden=false;b.addEventListener("click",function(){if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(A).then(function(){sel();say("Copied")},legacy)}else legacy()})})();</script>"""


DEFAULT_RATES = {"currency": "USD", "unit": "week", "note": "Intro rates", "packages": []}


def load_rates():
    try:
        r = json.load(open(os.path.join(REPO, SPONSORS_FILE), encoding="utf-8")).get("rates") or {}
    except (OSError, ValueError):
        r = {}
    return dict(DEFAULT_RATES, **r)


def _money(v, cur):
    v = float(v)
    amt = ("%d" % v) if v == int(v) else ("%.2f" % v)
    return ("$" + amt) if cur in ("USD", "CAD") else (amt + " " + cur)


def rates_html():
    """Rate card for the contact page, rendered from sponsors.json "rates". Display-only."""
    r = load_rates()
    pk = [x for x in r.get("packages", []) if x.get("label") and x.get("static") is not None]
    if not pk:
        return ""
    cur, unit = r.get("currency", "USD"), r.get("unit", "week")
    cards = "".join(
        '<div class="ct-rate"><h3>%s</h3><p>%s</p><dl><div><dt>Static image</dt><dd>%s<small>/%s</small></dd></div>%s</dl></div>' % (
            esc(x["label"]), esc(x.get("desc", "")), _money(x["static"], cur), esc(unit),
            ('<div><dt>Animated or video</dt><dd>%s<small>/%s</small></dd></div>' % (_money(x["motion"], cur), esc(unit)))
            if x.get("motion") is not None else "")
        for x in pk)
    return ('<div class="ct-rates"><div class="ct-rates-h"><h3>%s, %s per %s</h3>%s</div><div class="ct-rgrid">%s</div></div>') % (
        esc(r.get("note") or "Rates"), esc(cur), esc(unit),
        ('<p>%s</p>' % esc(r["footnote"])) if r.get("footnote") else "", cards)


BANNER_SPEC_HTML = """<details class="ct-spec"><summary>Banner spec</summary><ul>
<li><b>Static image:</b> 1200 × 300 px (4:1), PNG, JPG or WebP, up to 300 KB.</li>
<li><b>Animated:</b> GIF or animated WebP, 1200 × 300, up to 1.5 MB, loop of 15 seconds or less.</li>
<li><b>Video:</b> MP4 (H.264) or WebM, 1200 × 300 or 2400 × 600, up to 4 MB, 30 seconds or less. It may include audio. It autoplays muted as the page loads and loops endlessly, with no play, pause or seek controls; the only control is a small speaker button next to the Sponsored label that turns that ad's sound on or off, and every page load starts muted. Please also send a static 1200 × 300 poster frame, shown until the video starts.</li>
<li>Clicking the banner opens your link.</li>
<li>Keep logos and text inside the central 1080 × 240 px. Corners are rounded. No fake buttons that imitate site controls, and no rapid flashing (no more than 3 flashes per second).</li>
<li>We add the <b>Sponsored</b> label above every banner.</li></ul></details>"""


def build_contact_page():
    url = abs_url(CONTACT_PATH)
    title = "Contact · %s" % SITE_NAME
    desc = ("Email Daily Design at %s with questions, tips for future editions, corrections or sponsorship." % CONTACT_EMAIL)
    ld = {"@context": "https://schema.org", "@type": "ContactPage", "name": title, "url": url, "description": desc,
          "inLanguage": "en", "isPartOf": {"@type": "WebSite", "name": SITE_NAME, "url": SITE_URL},
          "mainEntity": dict(publisher_ld(), contactPoint={"@type": "ContactPoint", "email": CONTACT_EMAIL,
                                                            "contactType": "editorial and sponsorship", "availableLanguage": "en"})}
    head = SEO_START + "".join([
        '<title>%s</title>' % esc(title),
        '<meta name="description" content="%s">' % esc(desc),
        '<link rel="canonical" href="%s">' % url,
        '<meta name="robots" content="index,follow">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="%s">' % SITE_NAME,
        '<meta property="og:title" content="%s">' % esc(title),
        '<meta property="og:description" content="%s">' % esc(desc),
        '<meta property="og:url" content="%s">' % url,
        '<meta property="og:image" content="%s">' % abs_url("assets/favicon-512.png"),
        '<meta property="og:locale" content="en_US">',
        '<meta name="twitter:card" content="summary">',
        '<meta name="twitter:title" content="%s">' % esc(title),
        '<meta name="twitter:description" content="%s">' % esc(desc),
        '<meta name="twitter:image" content="%s">' % abs_url("assets/favicon-512.png"),
        '<link rel="alternate" type="application/atom+xml" title="Daily Design feed" href="%s">' % abs_url("feed.xml"),
        ld_json(ld)]) + SEO_END
    e = esc(CONTACT_EMAIL)
    doc = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
%s
<meta name="theme-color" content="#09090c">
%s
<link rel="stylesheet" href="assets/site.css">
%s
</head>
<body>
<main class="ct">
<nav class="ct-top" aria-label="Daily Design"><a class="btn" href="index.html">← Daily Design index</a></nav>
<section class="ct-card" aria-labelledby="ct-h">
<div class="eyebrow"><a class="dd-hlink" href="./" data-glow="Daily Design · Contact">Daily Design · Contact</a></div>
<h1 id="ct-h">Say <em>hello</em></h1>
<p class="lede">Got a question, a tip for a future edition, a correction, or want to sponsor Daily Design? Email us. Tap Copy to grab the address, or Email us to open your mail app.</p>
<div class="ct-mail"><span class="ct-addr" id="ct-addr">%s</span>
<div class="ct-btns"><button class="btn" id="ct-copy" type="button" hidden>Copy</button><a class="btn pri" href="%s">Email us</a></div></div>
<p class="ct-ok" id="ct-ok" role="status" aria-live="polite"></p>
<div class="ct-sec">
<div><h2>Tips</h2><p>Seen something made with AI that deserves a spot? Send the link to the post, repo or video.</p></div>
<div><h2>Corrections</h2><p>Spotted a mistake? Include the edition link and what needs fixing.</p></div>
<div><h2>Questions</h2><p>Anything about Daily Design, the editions or the archive.</p></div>
</div>
<div class="ct-sp" id="sponsor"><h2>Sponsor Daily Design</h2>
<p>Two clearly labelled landscape banner spots (1200 × 300). The <b>top spot</b> sits near the top of the index, each report and each edition. The <b>lower spot</b> sits on the index, just above the recent links. Both are kept apart from the editorial picks: sponsors never affect what we pick or how it ranks.</p>
%s
%s
<a class="btn pri" href="%s">Email about sponsoring</a></div>
</section>
</main>
<footer class="site"><div class="wrap">Daily Design is a public archive of AI design research digests. Links go to the original creators and sources.%s</div></footer>
%s
</body>
</html>
""" % (head, icon_links(""), CONTACT_CSS, e, esc(mailto("Daily Design")), rates_html(), BANNER_SPEC_HTML, esc(mailto("Sponsoring Daily Design")),
       credit_html("", contact=False), CONTACT_JS % CONTACT_EMAIL)
    if write_if_changed(os.path.join(REPO, CONTACT_PATH), doc):
        log("contact page", CONTACT_PATH)


def xml_esc(s):
    return html.escape(s or "", quote=True)


def build_sitemap_feed(editions):
    last = max(e["date"] for e in editions)
    urls = [(SITE_URL, last, "daily", "1.0")]
    urls += [(abs_url(CONTACT_PATH), last, "yearly", "0.5")]
    urls += [(abs_url(public_path(e)), e["date"], "monthly", "0.8") for e in editions]
    sm = ['<?xml version="1.0" encoding="UTF-8"?>',
          '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:image="http://www.google.com/schemas/sitemap-image/1.1">']
    by_url = {abs_url(public_path(e)): e for e in editions}
    for u, lm, cf, pr in urls:
        e = by_url.get(u)
        img = ("<image:image><image:loc>%s</image:loc></image:image>" % xml_esc(abs_url(e["header"]))) if e and e.get("header") else ""
        sm.append("<url><loc>%s</loc><lastmod>%s</lastmod><changefreq>%s</changefreq><priority>%s</priority>%s</url>" % (
            xml_esc(u), lm, cf, pr, img))
    sm.append("</urlset>")
    write_if_changed(os.path.join(REPO, "sitemap.xml"), "\n".join(sm) + "\n")
    write_if_changed(os.path.join(REPO, "robots.txt"),
                     "User-agent: *\nAllow: /\n\nSitemap: %s\n" % abs_url("sitemap.xml"))
    entries = []
    for e in editions[:60]:
        f = seo_fields(e)
        entries.append("""<entry><title>%s</title><link rel="alternate" type="text/html" href="%s"/><id>%s</id>
<published>%s</published><updated>%s</updated><summary>%s</summary><category term="%s"/></entry>""" % (
            xml_esc(f["title"].rsplit(" · ", 1)[0]), xml_esc(f["url"]), xml_esc(f["url"]),
            f["published"], f["published"], xml_esc(f["desc"]), xml_esc(f["section"])))
    feed = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<title>Daily Design</title><subtitle>%s</subtitle>
<link rel="self" type="application/atom+xml" href="%s"/><link rel="alternate" type="text/html" href="%s"/>
<id>%s</id><updated>%s</updated><author><name>Daily Design</name></author><author><name>%s</name><uri>%s</uri></author>
<icon>%s</icon>
%s
</feed>
""" % (xml_esc(SITE_DESC), abs_url("feed.xml"), SITE_URL, SITE_URL, published_iso(editions[0]), STUDIO_NAME, STUDIO_URL,
       abs_url("assets/favicon-192.png"), "\n".join(entries))
    write_if_changed(os.path.join(REPO, "feed.xml"), feed)


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


ASSET_REF_RE = re.compile(r'((?:src|href)=")((?:\.\./)*assets/([A-Za-z0-9_-]+\.(?:js|css)))(?:\?v=[0-9a-f]{6,16})?"')


def version_assets():
    """Cache-bust first-party JS/CSS: every src/href to assets/<name>.js|.css in the site's HTML gets ?v=<10-char content hash>,
    so a changed file gets a new URL (Pages caches assets for 10 minutes). Runs over every page each publish, so old pages are covered."""
    import hashlib
    hashes = {}
    def ver(m):
        name = m.group(3)
        if name not in hashes:
            fp = os.path.join(REPO, "assets", name)
            hashes[name] = hashlib.sha256(open(fp, "rb").read()).hexdigest()[:10] if os.path.isfile(fp) else None
        return m.group(0) if not hashes[name] else '%s%s?v=%s"' % (m.group(1), m.group(2), hashes[name])
    pages = [os.path.join(REPO, "index.html"), os.path.join(REPO, CONTACT_PATH)]
    for sub in ("editions", "reports"):
        for root, _, files in os.walk(os.path.join(REPO, sub)):
            pages += [os.path.join(root, f) for f in files if f.endswith(".html")]
    n = 0
    for pg in pages:
        if os.path.isfile(pg):
            doc = open(pg, encoding="utf-8").read()
            n += write_if_changed(pg, ASSET_REF_RE.sub(ver, doc))
    return n


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
    import hashlib
    spon_key = hashlib.sha1((sponsor_html() + sponsor_html(slot="links")).encode("utf-8")).hexdigest()[:12]  # top + lower spot: either changing rebuilds every edition page
    credit_key = hashlib.sha1(credit_html("../../").encode("utf-8")).hexdigest()[:12]  # footer credit changing rebuilds every edition page
    for i, r in enumerate(pages):
        e = r["edition"]
        prev = pages[i - 1]["edition"] if i > 0 else None
        nxt = pages[i + 1]["edition"] if i + 1 < len(pages) else None
        nav = [prev and prev["path"], nxt and nxt["path"], NAV_VERSION, spon_key, credit_key]
        dest = os.path.join(REPO, e["path"])
        doc = open(dest, encoding="utf-8").read()
        if r.get("nav") == nav and NAV_START in doc:
            continue
        if write_if_changed(dest, inject_nav(doc, e, prev, nxt, r["items"])):
            log("nav", e["path"])
        r["nav"] = nav
        write_if_changed(os.path.join(meta_dir, e["date"], e["slot"] + ".json"), jdump(r, pretty=True))

    # 3b. crawlable static pages for the 6 PM / 8 PM reports (plain report styling)
    build_report_pages(recs)

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
    data["special"] = load_special_days(days)
    data["maintenance"] = [x["date"] for x in data["special"] if x["type"] == "maintenance"]  # older app/gate builds
    write_if_changed(os.path.join(REPO, "data", "index.json"), jdump(data))
    # 4b. SEO: index head/static links, sitemap.xml, robots.txt, feed.xml
    build_index_seo(editions)
    build_contact_page()
    build_sitemap_feed(editions)
    nv = version_assets()  # 4c. ?v=<hash> on first-party JS/CSS links, after every page is written
    if nv: log("asset versions updated on %d pages" % nv)
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
    scan = [p for p in changed if p.endswith((".html", ".json", ".js", ".css", ".md", ".txt", ".py", ".xml", ".webmanifest"))]
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
