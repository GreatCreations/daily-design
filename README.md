# Daily Design

**Live site: https://greatcreations.github.io/daily-design/**

A public, searchable archive of daily AI design research digests: how people are using AI across image, video, 3D, code/UI, sound, games and mashups.

There are up to four editions a day:

| Slot | Edition | Format |
|---|---|---|
| 7 AM | **AI Design Daily**: the morning briefing on new tools, models, tutorials and repos | Long scrolling web page (`editions/<date>/morning.html`) |
| Noon | **AI Design in Use**: real-world projects, workflows and honest results | Long scrolling web page (`editions/<date>/noon.html`) |
| 6 PM | **Best of the Day** | Plain Markdown report (`reports/<date>/best.md`) |
| 8 PM | **Hottest Right Now** | Plain Markdown report (`reports/<date>/hottest.md`) |

## The index

The [home page](https://greatcreations.github.io/daily-design/) covers every edition and **every individual link** in them:

- **Latest** at the top always shows the most recent day's four slots, and marks any slot that hasn't been published yet.
- **Search** runs instantly across edition headlines and summaries, plus every item's title, note, source, medium and tags.
- **Filters** cover edition slot, medium and item type, plus a date range (from/to, latest day, last 7 or 30 days, this month). Search, tags and dates all combine, and the URL hash keeps the view so it can be shared (for example `#q=blender&medium=3d&from=2026-10-01`).
- **Archive** groups editions by month, then by day. Each day shows its four slots side by side, with a clear "Not published" state for any that are missing. Each month has a small calendar heatmap of published days that you can click to jump to a day, and there's also a month jump menu and a newest-first/oldest-first toggle.
- **Reports**: clicking a 6 PM or 8 PM report opens it inline in a reader panel on the index (deep link: `#report=<date>/<slot>`), with a secondary "View on GitHub" link.

The 7 AM and noon pages have a fixed **Back to index** bar, previous/next links and a footer link back to the index.

## Layout

```
index.html                         the index (vanilla JS, no build step, no CDNs)
assets/site.css, assets/app.js     styles and app
assets/vendor/marked.min.js        Markdown renderer for the report reader (MIT, see marked.LICENSE.md)
data/index.json                    editions, calendar, facets, totals and the item shard manifest
data/items/<YYYY-MM>.json          every item for that month (loaded on demand)
data/meta/<YYYY-MM-DD>/<slot>.json per-edition record used to rebuild the index
editions/<YYYY-MM-DD>/<slot>.html  7 AM / noon pages, with <slot>-header.png and <slot>-thumb.jpg
reports/<YYYY-MM-DD>/<slot>.md     6 PM / 8 PM reports, with <slot>-header.png and <slot>-thumb.jpg
tools/publish.py                   the publisher (see tools/PUBLISHING.md)
```

## Built to scale

Item data is split into one file per month, so the index stays light as the archive grows. At first load the page fetches only `data/index.json` plus the newest month. A search or filter then pulls in the other months it needs, newest first, with a progress bar, and a date range limits it to the months in that range. Results, edition cards and archive months are all paged, and a month's days are only drawn when it's opened. In a test with 1,419 editions and 95,546 items, `index.json` was about 0.5 MB, each month file was about 5.7 MB uncompressed, and a full-archive search finished in about 1.3 s.

Links go to the original creators and sources. Engagement numbers (likes, views, stars) were read when each edition was compiled and will have changed since.
