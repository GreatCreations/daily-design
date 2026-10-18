# Daily Design

**Live site: https://studios.greatcreations.art/daily-design/**

A public, searchable archive of daily AI design research digests: how people are using AI across image, video, 3D, code/UI, sound, games and mashups.

There are up to four editions a day:

| Slot | Edition | Format |
|---|---|---|
| 7 AM | **AI Design Daily**: the morning briefing on new tools, models, tutorials and repos | Long scrolling web page (`editions/<date>/morning.html`) |
| Noon | **AI Design in Use**: real-world projects, workflows and honest results | Long scrolling web page (`editions/<date>/noon.html`) |
| 6 PM | **Best of the Day** | Plain Markdown report (`reports/<date>/best.md`) |
| 8 PM | **Hottest Right Now** | Plain Markdown report (`reports/<date>/hottest.md`) |

## The index

The [home page](https://studios.greatcreations.art/daily-design/) covers every edition and **every individual link** in them:

- **Next-edition countdown** in the top bar: the next scheduled slot (7 AM, noon, 6 PM, 8 PM Vancouver time, computed with Intl) in its slot colour, the due time in the visitor's own time zone, and a live hh:mm:ss countdown. It shows "arriving now" for 10 minutes after each scheduled time, then rolls on. It's the schedule, not a publish confirmation (`assets/countdown.js`).
- **3D logo**: the DD mark as a CSS-3D extruded tile (no libraries), scrubbed by scroll (`assets/logo3d.js`). Its place on a swirling path from the hero spot to the slot beside the sticky search bar, its turn, scale, light sweep and theme-colour trails are all functions of scroll position, so it freezes when you stop and rewinds when you scroll up. Nothing moves on load. It is a "Back to top" button: below the top it smooth-scrolls up (rewinding the path); at the top it plays a ~1 s spin with a ring burst that ends on the exact resting pose. Lighter trails on phones; with reduced motion, two static logos crossfade, the scroll is instant and the click is a glow pulse.
- **Always opens at the top**: a tiny inline script in the index head (`<!--dd-top-->` markers) turns off browser scroll restoration and resets to the top on load, refresh and back/forward. Only a `#report=` deep link scrolls, to the reader.
- **Latest** at the top always shows the most recent day's four slots, and marks any slot that hasn't been published yet.
- **Search** runs instantly across edition headlines and summaries, plus every item's title, note, source, medium and tags.
- **Filters** cover edition slot, medium and item type, plus a date range (from/to, latest day, last 7 or 30 days, this month). Search, tags and dates all combine, and the URL hash keeps the view so it can be shared (for example `#q=blender&medium=3d&from=2026-10-01`).
- **Archive** groups editions by month, then by day. Each day shows its four slots side by side, with a clear "Not published" state for any that are missing. Each month has a small calendar heatmap of published days that you can click to jump to a day, and there's also a month jump menu and a newest-first/oldest-first toggle.
- **Reports**: clicking a 6 PM or 8 PM report opens it inline in a reader panel on the index (deep link: `#report=<date>/<slot>`), with a secondary "View on GitHub" link.

The 7 AM and noon pages have a fixed **Back to index** bar, previous/next links and a footer link back to the index.

**Listen (read aloud):** every report in the reader and every 7 AM / noon page has a **▶ Listen** button (Pause/Resume and Stop while reading). It uses the browser's built-in speech (Web Speech API), so there is no outside service, key or tracking. It reads the headline and article text in short pieces, skipping navigation, buttons, charts, images and code, and says link text rather than URLs. It prefers a well-known female English voice when the device has one (for example Google UK English Female, Microsoft Aria/Jenny/Sonia Natural, Samantha, Karen, Moira, Zira) and otherwise uses the first English voice. Voices and quality depend on the device and browser; the button is hidden where speech isn't supported.

## Search engines and sharing

Every page carries a unique title and description, a canonical URL (base `https://studios.greatcreations.art/daily-design/`), Open Graph and Twitter card tags with the edition's header image, and NewsArticle structured data (JSON-LD). Because the index opens reports through a URL hash, each 6 PM / 8 PM report also gets a plain, lightweight static page (`reports/<date>/<slot>.html`, same styling as the reader) that search engines can index; canonical links and the sitemap point there. The index has WebSite + CollectionPage structured data and plain links to the latest editions in the HTML. `sitemap.xml`, `robots.txt` and an Atom feed (`feed.xml`) are regenerated on every publish. Note: crawlers only read `robots.txt` at a domain root, so submit `sitemap.xml` in Google Search Console.

Every page ends with a credit: "Daily Design is created and brought to you by Great Creation Studios", linking to https://greatcreationstudios.greatcreations.art. Its small icon is a copy of that site's favicon (`assets/gcs-icon.png`). The Listen button doesn't read it.

## Layout

```
index.html                         the index (vanilla JS, no build step, no CDNs)
assets/site.css, assets/app.js     styles and app
assets/favicon.svg (+ .ico, PNGs)  "DD" site icon; icon.svg is the large-size artwork; site.webmanifest
assets/tts.js                      read-aloud button (browser speech, used by the reader and the edition pages)
assets/vendor/marked.min.js        Markdown renderer for the report reader (MIT, see marked.LICENSE.md)
data/index.json                    editions, calendar, facets, totals and the item shard manifest
data/items/<YYYY-MM>.json          every item for that month (loaded on demand)
data/meta/<YYYY-MM-DD>/<slot>.json per-edition record used to rebuild the index
editions/<YYYY-MM-DD>/<slot>.html  7 AM / noon pages, with <slot>-header.png and <slot>-thumb.jpg
reports/<YYYY-MM-DD>/<slot>.md     6 PM / 8 PM reports, with <slot>-header.png and <slot>-thumb.jpg
reports/<YYYY-MM-DD>/<slot>.html   plain static copy of each report (for search engines and sharing)
sitemap.xml, robots.txt, feed.xml  generated on every publish
tools/publish.py                   the publisher (see tools/PUBLISHING.md)
```

## Built to scale

Item data is split into one file per month, so the index stays light as the archive grows. At first load the page fetches only `data/index.json` plus the newest month. A search or filter then pulls in the other months it needs, newest first, with a progress bar, and a date range limits it to the months in that range. Results, edition cards and archive months are all paged, and a month's days are only drawn when it's opened. In a test with 1,419 editions and 95,546 items, `index.json` was about 0.5 MB, each month file was about 5.7 MB uncompressed, and a full-archive search finished in about 1.3 s.

Links go to the original creators and sources. Engagement numbers (likes, views, stars) were read when each edition was compiled and will have changed since.
