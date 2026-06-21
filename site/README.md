# Ballon d'Or — public scrollytelling site

A designed, general-public version of the analysis (the rigorous version is the Quarto report at
`report/ballon-dor.qmd`). Dark-editorial scrollytelling, bespoke D3 charts.

## View it
Just open `site/index.html` in a browser (works from `file://`). The data is inlined in `data.js`, so
no server is needed. D3, scrollama, and the fonts load from CDNs — so an internet connection is needed
for the first view. To host: drop the `site/` folder on any static host (GitHub Pages, Netlify, …).

## Files
- `index.html` — narrative + section structure.
- `styles.css` — dark-editorial design system.
- `app.js` — D3 v7 charts + scrollama scroll-step wiring.
- `data.js` — distilled results (`window.BDOR`), generated from the cached models.

## Regenerate the data
`python run.py report` rebuilds `site/data.js` (and the Quarto figure PNGs) from the cached model
objects — it never refits. Logic lives in `src/bdor/report.py` (`export_site_data`).
