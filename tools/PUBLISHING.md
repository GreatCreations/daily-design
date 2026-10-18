# Publishing new editions

Run one command after an edition has been written:

```
python3 /workspace/daily-design/tools/publish.py
```

The script:

1. **Finds editions** in the source folder (default `/workspace/ai-design-daily`, override with `--src DIR`). It picks up any file named
   `YYYY-MM-DD-<slot>.html` or `YYYY-MM-DD-<slot>.md`, where slot is `morning`, `noon`, `best` or `hottest`.
   Header images are read from `YYYY-MM-DD-<slot>-header.png` (or .jpg/.webp), or from the first image the Markdown links to.
2. **Copies** them to `editions/<date>/<slot>.html` with `<slot>-header.<ext>` and a small `<slot>-thumb.jpg` for the index cards.
3. **Converts Markdown-only reports** (6 PM `best`, 8 PM `hottest`) into styled pages: header image on top, then headline, lead and article.
   The lead is the first `>` blockquote, or the first paragraph if there isn't one.
4. **Injects navigation** into every edition: a fixed "Back to index" bar with previous/next links, and a footer. The injected block sits between
   `<!--dd-nav:start-->`/`<!--dd-nav:end-->` markers (plus style and footer markers), so re-running replaces it instead of duplicating it. Sticky or fixed
   elements on the page that were pinned to `top:0` get moved below the bar automatically.
5. **Rebuilds `data/index.json`** (and `data/index.js`) by parsing the list items in each edition's `.md` source:
   - `- [Title](url), type. Note…` (morning style)
   - `1. **[Title](url)**: note` (try-this style)
   - `1. **Title** · author · Oct 14 · Platform · *Kind* · ♥ 15` followed by the note and a `Tools: … · [source](url) · [extra](url)` line (noon style)
   - any other list item that contains a link (the first link is used)

   Medium comes from the nearest `##`/`###` heading (image, video, 3D, code/UI, sound, games, mashups). Item type comes from the item's own
   label, mapped onto: tutorial, repo/tool, showcase, news, update, buzz, case study, breakdown, workflow, result. Sections such as
   "stories to read first" (duplicate picks) and "Method & caveats" are skipped. If an edition has only HTML and no `.md`, it is published,
   but its items aren't indexed.
6. **Safety scan**: before anything is committed, every published file is checked for local paths, tokens, email addresses, private
   Slack or Drive links, and the patterns in an optional private denylist kept outside the repo (`<src>/.publish-denylist`, one regex per line).
   If anything matches, nothing is committed and the matches are printed.
7. **Commits and pushes** to `main` as GreatCreations. The git credential helper is set locally in this repo and asks
   `gh auth token -u GreatCreations` for the token, so the active gh account is never switched. GitHub Pages redeploys in about a minute.

Re-running with nothing new prints `nothing new to publish`. Use `--no-push` to rebuild and check locally without committing.

## Routine checklist

- Write the edition's `.md` (always) and the `.html` (7 AM / noon), plus `YYYY-MM-DD-<slot>-header.png`, into the source folder.
- Run `python3 /workspace/daily-design/tools/publish.py`.
- The edition is live at `https://greatcreations.github.io/daily-design/editions/<date>/<slot>.html`.
