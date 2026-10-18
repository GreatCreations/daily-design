# Daily Design

**Live site: https://greatcreations.github.io/daily-design/**

A public, searchable archive of daily AI design research digests: how people are using AI across image, video, 3D, code/UI, sound, games and mashups.

There are up to four editions a day:

| Slot | Edition | Format |
|---|---|---|
| 7 AM | **AI Design Daily**: the morning briefing on new tools, models, tutorials and repos | Long scrolling web page |
| Noon | **AI Design in Use**: real-world projects, workflows and honest results | Long scrolling web page |
| 6 PM | **Best of the Day** | Report page (header image + article) |
| 8 PM | **Hottest Right Now** | Report page (header image + article) |

## The index

The [home page](https://greatcreations.github.io/daily-design/) lists every edition and **every individual link** inside them:

- Instant search across edition headlines and summaries, plus every item's title, note, source, medium and tags.
- Tag filters for edition slot, medium, item type and date. You can combine them, and the URL updates so you can share a filtered view (for example `#q=blender&medium=3d`).
- Each result links straight to the original source and to the edition it came from.

Every edition page has a fixed **Back to index** bar, previous/next links and a footer link back to the index.

## Layout

```
index.html              the searchable index (vanilla JS, no build step)
assets/                 site.css, app.js
data/index.json         all editions + items (data/index.js holds the same data so the page also works when opened locally)
editions/<date>/<slot>.html, <slot>-header.png, <slot>-thumb.jpg
tools/publish.py        the publisher (see tools/PUBLISHING.md)
```

Links go to the original creators and sources. Engagement numbers (likes, views, stars) were read when each edition was compiled and will have changed since.
