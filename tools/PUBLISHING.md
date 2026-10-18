# Publishing new editions

Run one command after an edition has been written:

```
python3 /workspace/daily-design/tools/publish.py
```

Options: `--no-push` rebuilds and runs the safety scan without committing. `--rebuild` reprocesses every source edition even if it hasn't changed. `--src DIR` reads from a different source folder.

## What it does

1. **Finds editions** in the source folder (default `/workspace/ai-design-daily`): files named `YYYY-MM-DD-<slot>.html` / `YYYY-MM-DD-<slot>.md`,
   where slot is `morning`, `noon`, `best` or `hottest`. Header images come from `YYYY-MM-DD-<slot>-header.png` (or .jpg/.webp), or from the
   first image the Markdown links to. An edition is processed only when it's new or its source files changed (tracked by content hash).
2. **7 AM and noon** (`morning`, `noon`) are HTML pages: copied to `editions/<date>/<slot>.html` with `<slot>-header.<ext>` and a small `<slot>-thumb.jpg`.
3. **6 PM and 8 PM** (`best`, `hottest`) stay **plain Markdown reports**: copied to `reports/<date>/<slot>.md`, with the header image next to it and
   embedded at the top as a relative link (`![Best of the Day header](best-header.png)`). They aren't converted to HTML. On the index they appear as
   **Report** cards that open in an inline reader, with a secondary link to the GitHub file view.
4. **Navigation** goes into the HTML editions only: a fixed "Back to index" bar with previous/next links (stepping through HTML editions) and a footer.
   It sits between `<!--dd-nav:start-->`/`<!--dd-nav:end-->` markers (plus style and footer markers), so re-running replaces it instead of duplicating it.
   Only pages whose previous/next neighbours changed are rewritten. Page elements that were sticky at `top:0` are moved below the bar automatically.
5. **Metadata**: each edition gets `data/meta/<date>/<slot>.json` (edition fields + parsed items). The index is always rebuilt from these records,
   so old editions stay indexed even after the source folder is cleaned out.
6. **Index data**: `data/index.json` holds the editions (newest first), the calendar of published days and slots, facets, totals and the shard
   manifest. Items go into monthly shards, `data/items/<YYYY-MM>.json`, which the browser loads on demand. Every edition and item carries an ISO `date` and a `slot`.
7. **Item parsing** reads list items in each edition's `.md`:
   - `- [Title](url), type. Note…` (morning style)
   - `1. **[Title](url)**: note` (try-this style)
   - `1. **Title** · author · Oct 14 · Platform · *Kind* · ♥ 15`, then the note and a `Tools: … · [source](url) · [extra](url)` line (noon style)
   - any other list item that contains a link (the first link is used)

   Medium comes from the nearest heading (image, video, 3D, code/UI, sound, games, mashups). The item's own label is mapped onto tutorial,
   repo/tool, showcase, news, update, buzz, case study, breakdown, workflow or result, and the original label is kept as an extra tag.
   "Stories to read first" (duplicate picks) and "Method & caveats" sections are skipped.
8. **Safety scan**: every new or changed file is checked for local paths, tokens, email addresses and private Slack/Drive links, plus the patterns
   in an optional private denylist kept outside the repo (`<src>/.publish-denylist`, one regex per line). If anything matches, nothing is committed.
9. **Commit and push** to `main` as GreatCreations. The repo's local git credential helper asks `gh auth token -u GreatCreations` for the token,
   so the active gh account is never switched. GitHub Pages redeploys in about a minute.

Re-running with nothing new prints `nothing new to publish`.

## Routine checklist

- 7 AM / noon: write `YYYY-MM-DD-<slot>.html`, `YYYY-MM-DD-<slot>.md` and `YYYY-MM-DD-<slot>-header.png` into the source folder.
- 6 PM / 8 PM: write `YYYY-MM-DD-best.md` / `YYYY-MM-DD-hottest.md` and the matching `-header.png`.
- Run `python3 /workspace/daily-design/tools/publish.py`.
- Pages: `https://greatcreations.github.io/daily-design/editions/<date>/<slot>.html`. Reports: `https://greatcreations.github.io/daily-design/#report=<date>/<slot>`.
