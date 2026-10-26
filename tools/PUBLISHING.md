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
   The bar also carries the **Listen** read-aloud buttons and loads `assets/tts.js`, so every new or rebuilt page gets them. When the nav markup
   changes, bump `NAV_VERSION` in `publish.py` and every existing page is re-injected on the next run. Reports get the same button from the index reader.
   The page head also gets the site icon links (favicon .ico/.svg/.png, apple-touch-icon, manifest) between `<!--dd-icon:start-->`/`<!--dd-icon:end-->`.
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
7b. **SEO** (every run): edition pages get title, description, canonical, Open Graph/Twitter and NewsArticle JSON-LD in their head
   (between `<!--dd-seo:start-->`/`<!--dd-seo:end-->`; the page's own title/description tags are replaced). Each report gets a static
   page `reports/<date>/<slot>.html` rendered from its Markdown in plain report styling (with Listen, favicon and a back link).
   `index.html` gets its SEO block, plain links to the latest day (`<!--dd-latest-->`) and a no-JS list of editions (`<!--dd-static-->`).
   `sitemap.xml`, `robots.txt` and `feed.xml` are rewritten. The canonical base is `SITE_URL` in `publish.py`.
7c. **Credit**: every page gets the Great Creation Studios footer credit between `<!--dd-credit:start-->`/`<!--dd-credit:end-->`
   (inside the edition footer, the report page footer and the index footer).
8. **Safety scan**: every new or changed file is checked for local paths, tokens, email addresses and private Slack/Drive links, plus the patterns
   in an optional private denylist kept outside the repo (`<src>/.publish-denylist`, one regex per line). If anything matches, nothing is committed.
9. **Commit and push** to `main` as GreatCreations. The repo's local git credential helper asks `gh auth token -u GreatCreations` for the token,
   so the active gh account is never switched. GitHub Pages redeploys in about a minute.

Re-running with nothing new prints `nothing new to publish`.

## Routine checklist

- 7 AM / noon: write `YYYY-MM-DD-<slot>.html`, `YYYY-MM-DD-<slot>.md` and `YYYY-MM-DD-<slot>-header.png` into the source folder.
- 6 PM / 8 PM: write `YYYY-MM-DD-best.md` / `YYYY-MM-DD-hottest.md` and the matching `-header.png`.
- Run `python3 /workspace/daily-design/tools/publish.py`.
- Pages: `https://studios.greatcreations.art/daily-design/editions/<date>/<slot>.html`. Reports: `https://studios.greatcreations.art/daily-design/#report=<date>/<slot>` (inline reader) or `.../reports/<date>/<slot>.html` (static page).

## Contact page and sponsor spot

- **Contact**: `contact.html` is generated every run (`build_contact_page`) with the public address in `CONTACT_EMAIL`, a Copy button
  (clipboard API, with a select-the-text fallback) and an "Email us" mailto link. Every footer (index, report pages, edition pages) gets a
  Contact link through the credit block, so new editions pick it up automatically. The page is in `sitemap.xml`.
- **Sponsor spot**: `sponsors.json` at the repo root. The first entry with `"active": true` (and today inside its optional `start`/`end`)
  is the sponsor. Near the top of the index (under search), each report page and each edition (top strip) the publisher renders, between
  `<!--dd-sponsor:start-->`/`<!--dd-sponsor:end-->`:
  1. **The banner** (the actual ad space), a 4:1 landscape slot labelled **Sponsored**. It shows the sponsor's `banner.image` when
     `banner.active` is true and today is inside `banner.start`/`banner.end`; if the sponsor has no live banner, a text card with its
     logo, name and line. With no active sponsor it shows a placeholder template ("Your ad here · 1200 × 300 banner", labelled
     **Ad space**) linking to `contact.html#sponsor`. Sponsor links get `rel="sponsored noopener"` and open in a new tab.
  2. **The invite** below it: a short "Sponsor Daily Design" line and a "Get in touch" link to `contact.html#sponsor`.
  Editing `sponsors.json` and re-running the publisher updates every page. Fields per sponsor: `name`, `line`, `url`, `logo`,
  `active`, `start`, `end`, and `banner` = `{image, alt, url, active, start, end}` (`image` is an https URL or a repo path such as
  `assets/sponsors/acme-1200x300.webp`; `url` defaults to the sponsor `url`; `alt` should say what the ad says).
  The spot is display-only: nothing in it feeds item parsing, ranking or the index data.
- **Banner spec** (what to ask sponsors for):
  - 1200 × 300 px (4:1), PNG, JPG or WebP, 300 KB max. Supply 2400 × 600 for extra sharpness if it stays under 300 KB.
  - It is shown at the width of the content column (up to about 1200 px on the index, 1100 px on editions, about 760 px on report
    pages, about 360 px on phones) and always keeps 4:1, so it is scaled, never cropped differently per device.
  - Safe area: keep logo and text inside the central 1080 × 240 px (60 px clear on every side). Text must stay readable at 360 px wide,
    so use a headline of 48 px or more at full size and no more than about 8 words; avoid small print.
  - Corners are rounded by the site (about 14 px), so keep nothing important in the corners.
  - No fake buttons that imitate site controls, no flashing or animation. The site adds the **Sponsored** label above the banner
    (required disclosure in Canada); do not rely on the image to carry it.
