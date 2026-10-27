"""Members-gate split for Daily Design (DRAFT, branch gate-kv-publish, not live).

Editions dated after FREE_FOREVER_THROUGH (2026-10-31) never go into this public repo. publish.py still builds
them in the working tree exactly as before (so nav, metadata and incremental checks keep working); this module then:

  1. uploads the full content (editions/<d>/*, reports/<d>/*, data/meta/<d>/*) to the gate Worker's KV as
     ed:<path>, plus the full index and item shards as snap:index / snap:items:* (the Worker serves these),
  2. moves those files out of the repo into PRIVATE_ROOT (outside git) and restores them at the start of the next run,
  3. rewrites the public index.json (gated editions header-only), item shards (no gated items), and returns the
     public edition list so index.html / sitemap.xml / feed.xml are rebuilt without gated editions,
  4. refuses to commit if anything gated is still in the tree (leak check), and keeps a local git exclude as a backstop.

Config (environment, never committed or printed):
  DD_GATE=1                    turn the split on (unset = publish exactly as before)
  DD_FREE_FOREVER_THROUGH      default 2026-10-31
  DD_PRIVATE_ROOT              default /workspace/ai-design-daily/gated-site
  CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID, and the token in CF_KV_TOKEN or in the file named by CF_KV_TOKEN_FILE
  (API token scoped to Workers KV Storage: Edit on that one account only).
"""
import base64, hashlib, json, os, shutil, urllib.request, urllib.error

FFT = os.environ.get("DD_FREE_FOREVER_THROUGH", "2026-10-31")
PRIVATE_ROOT = os.environ.get("DD_PRIVATE_ROOT", "/workspace/ai-design-daily/gated-site")
GATED_DIRS = ("editions", "reports", os.path.join("data", "meta"))
HEADER_KEYS = ("date", "slot", "time", "title", "kind", "headline", "teaser", "item_count", "tags")
UA = "daily-design-publish/1 (+gate)"


def enabled():
    return os.environ.get("DD_GATE") == "1"


def gated(date):
    return date > FFT


def _token():
    t = os.environ.get("CF_KV_TOKEN")
    if not t and os.environ.get("CF_KV_TOKEN_FILE"):
        t = open(os.environ["CF_KV_TOKEN_FILE"], encoding="utf-8").read().strip()
    if not t:
        raise SystemExit("gate: CF_KV_TOKEN / CF_KV_TOKEN_FILE missing; nothing committed")
    return t


def _gated_dates(repo):
    out = set()
    for d in GATED_DIRS:
        p = os.path.join(repo, d)
        if os.path.isdir(p):
            out |= {x for x in os.listdir(p) if len(x) == 10 and x[4] == "-" and gated(x)}
    return out


def _files_for(root, date):
    for d in GATED_DIRS:
        base = os.path.join(root, d, date)
        if os.path.isdir(base):
            for r, _, fs in os.walk(base):
                for f in fs:
                    yield os.path.relpath(os.path.join(r, f), root)


def restore(repo, log):
    """Start of run: put last run's gated files back into the working tree (never committed)."""
    if not enabled() or not os.path.isdir(PRIVATE_ROOT):
        return
    n = 0
    for date in _gated_dates(PRIVATE_ROOT):
        for rel in _files_for(PRIVATE_ROOT, date):
            dst = os.path.join(repo, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(os.path.join(PRIVATE_ROOT, rel), dst); n += 1
    _exclude(repo, _gated_dates(PRIVATE_ROOT))
    if n:
        log("gate: restored %d gated files into the working tree" % n)


def _exclude(repo, dates):
    """Local-only .git/info/exclude entries so `git add -A` can never pick up gated dirs."""
    p = os.path.join(repo, ".git", "info", "exclude")
    if not os.path.isdir(os.path.dirname(p)):
        return
    have = open(p, encoding="utf-8").read().splitlines() if os.path.exists(p) else []
    want = ["/%s/%s/" % (d.replace(os.sep, "/"), date) for date in sorted(dates) for d in GATED_DIRS]
    add = [w for w in want if w not in have]
    if add:
        with open(p, "a", encoding="utf-8") as f:
            f.write("\n".join(["# daily-design gate (local only)"] + add) + "\n")


def _kv_bulk(pairs, log):
    acct, ns = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_KV_NAMESPACE_ID")
    if not acct or not ns:
        raise SystemExit("gate: CF_ACCOUNT_ID / CF_KV_NAMESPACE_ID missing; nothing committed")
    url = "https://api.cloudflare.com/client/v4/accounts/%s/storage/kv/namespaces/%s/bulk" % (acct, ns)
    tok = _token()
    batch, size = [], 0
    def send(b):
        req = urllib.request.Request(url, data=json.dumps(b).encode(), method="PUT",
                                     headers={"Authorization": "Bearer " + tok, "Content-Type": "application/json", "User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                res = json.load(r)
        except urllib.error.HTTPError as e:
            raise SystemExit("gate: KV upload failed (HTTP %s); nothing committed" % e.code)
        if not res.get("success") or res.get("result", {}).get("unsuccessful_keys"):
            raise SystemExit("gate: KV upload incomplete; nothing committed")
    for k, v in pairs:
        item = {"key": k, "value": base64.b64encode(v).decode(), "base64": True}
        sz = len(item["value"]) + len(k)
        if batch and (size + sz > 80_000_000 or len(batch) >= 5000):
            send(batch); batch, size = [], 0
        batch.append(item); size += sz
    if batch:
        send(batch)
    log("gate: uploaded %d KV keys" % len(pairs))


def _manifest_path():
    return os.path.join(PRIVATE_ROOT, ".kv-manifest.json")


def split(repo, data, shards, recs, log, dry_run=False):
    """After the index is built and before the safety scan / commit. Returns the public editions list."""
    if not enabled():
        return data["editions"]
    gdates = sorted({r["edition"]["date"] for r in recs if gated(r["edition"]["date"])} | _gated_dates(repo))
    os.makedirs(PRIVATE_ROOT, exist_ok=True)
    man = json.load(open(_manifest_path())) if os.path.exists(_manifest_path()) else {}
    pairs = []
    # 1a. full content files for gated dates (only changed ones, to stay well inside the KV free write quota)
    for date in gdates:
        for rel in _files_for(repo, date):
            b = open(os.path.join(repo, rel), "rb").read()
            h = hashlib.sha256(b).hexdigest()
            key = "ed:" + rel.replace(os.sep, "/")
            if man.get(key) != h:
                pairs.append((key, b)); man[key] = h
    # 1b. full index + item shards for the Worker (members see all; non-members get header-only from the Worker)
    full_idx = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode()
    snap = [("snap:index", full_idx)]
    for month, its in shards.items():
        snap.append(("snap:items:" + month, json.dumps({"month": month, "items": its}, ensure_ascii=False, separators=(",", ":")).encode()))
        by = {}
        for it in its:
            by.setdefault(it["date"], []).append(it)
        for d, arr in by.items():
            snap.append(("snap:items:%s:%s" % (month, d), json.dumps(arr, ensure_ascii=False, separators=(",", ":")).encode()))
        snap.append(("snap:items-days:" + month, json.dumps(sorted(by)).encode()))
    for k, v in snap:
        h = hashlib.sha256(v).hexdigest()
        if man.get(k) != h:
            pairs.append((k, v)); man[k] = h
    if dry_run:
        log("gate (dry run): would upload %d KV keys (%.1f MB)" % (len(pairs), sum(len(v) for _, v in pairs) / 1e6))
    elif pairs:
        _kv_bulk(pairs, log)
    # 2. move gated files out of the tree
    moved = 0
    for date in gdates:
        for rel in list(_files_for(repo, date)):
            dst = os.path.join(PRIVATE_ROOT, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(os.path.join(repo, rel), dst); moved += 1
        for d in GATED_DIRS:
            p = os.path.join(repo, d, date)
            if os.path.isdir(p):
                shutil.rmtree(p)
    _exclude(repo, gdates)
    if not dry_run:
        json.dump(man, open(_manifest_path(), "w"))
    log("gate: moved %d gated files out of the repo (%s)" % (moved, ", ".join(gdates) or "none"))
    # 3. public index.json and shards
    pub = dict(data)
    pub["editions"] = [e if not gated(e["date"]) else dict({k: e[k] for k in HEADER_KEYS if k in e}, locked_after_first_week=True)
                       for e in data["editions"]]
    for e in pub["editions"]:
        if gated(e["date"]):
            e["teaser"] = _teaser(next(x for x in data["editions"] if x["date"] == e["date"] and x["slot"] == e["slot"]).get("summary"))
    items_dir = os.path.join(repo, "data", "items")
    pub_shards = []
    for s in data["shards"]:
        its = [it for it in shards.get(s["month"], []) if not gated(it["date"])]
        p = os.path.join(items_dir, s["month"] + ".json")
        if its:
            with open(p, "w", encoding="utf-8") as f:
                f.write(json.dumps({"month": s["month"], "items": its}, ensure_ascii=False, separators=(",", ":")))
            pub_shards.append(dict(s, items=len(its), editions=sum(1 for e in data["editions"] if e["date"][:7] == s["month"] and not gated(e["date"]))))
        elif os.path.exists(p):
            os.remove(p)
    pub["shards"] = pub_shards
    pub["totals"] = dict(data["totals"], items=sum(s["items"] for s in pub_shards), months=len(pub_shards))
    with open(os.path.join(repo, "data", "index.json"), "w", encoding="utf-8") as f:
        f.write(json.dumps(pub, ensure_ascii=False, separators=(",", ":")))
    return [e for e in data["editions"] if not gated(e["date"])]


def _teaser(t):
    import re
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    m = re.match(r"^(.{40,180}?[.!?])(\s|$)", t)
    return m.group(1) if m else re.sub(r"\s+\S*$", "", t[:150]) + "…"


def leak_check(repo, changed):
    """Hard stop before commit: no gated content paths, no gated items, header-only index entries."""
    bad = []
    for date in _gated_dates(repo):
        bad.append("gated dir still in repo: %s" % date)
    for p in changed:
        rel = os.path.relpath(p, repo).replace(os.sep, "/")
        parts = rel.split("/")
        for i, seg in enumerate(parts[:-1]):
            if len(seg) == 10 and seg[4] == "-" and gated(seg) and "/".join(parts[:i]) in ("editions", "reports", "data/meta"):
                bad.append("gated file: " + rel)
    idx = json.load(open(os.path.join(repo, "data", "index.json"), encoding="utf-8"))
    for e in idx["editions"]:
        if gated(e["date"]):
            extra = set(e) - set(HEADER_KEYS) - {"locked_after_first_week"}
            if extra:
                bad.append("index.json gated entry %s/%s has %s" % (e["date"], e["slot"], sorted(extra)))
    items_dir = os.path.join(repo, "data", "items")
    for f in os.listdir(items_dir) if os.path.isdir(items_dir) else []:
        for it in json.load(open(os.path.join(items_dir, f), encoding="utf-8")).get("items", []):
            if gated(it.get("date", "")):
                bad.append("gated item in %s" % f); break
    return bad
