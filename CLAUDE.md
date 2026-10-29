# MOTIVATE Webpage

## Purpose
Full-screen trading motivation pages (rules, principles, reminders) kept in view during the
trading session. Static HTML/CSS/JS served by a small local pythonw server (127.0.0.1 only),
which also powers the in-page PAGE BUILDER (black "A" circle, bottom right of every page).

## Folder Structure
```
motivate_webpage\
  README.md, .gitignore    GitHub: github.com/jeromecharlesrenard-collab/motivate_webpage (public)
  .github\workflows\pages.yml   publishes site\ to https://jeromecharlesrenard-collab.github.io/motivate_webpage/
  MOTIVATE.lnk             shortcut -> .venv\Scripts\pythonw.exe main.py
  main.py                  entry point: logging, config, starts server, opens site\<start_page>
  app\launcher.py          config, EDT logging, error dialogs, open-in-browser / server start
  app\server.py            local HTTP server: serves site\; GET /api/ping, /api/page?n=N;
                           POST /api/preview, /api/create, /api/update, /api/shutdown
  app\github_sync.py       git add/commit/push after every builder CREATE / SAVE (auto_upload)
  app\page_builder.py      builder logic: validate spec, render page, insert + renumber,
                           load existing page (parses original style-x and builder line-N pages), edit, backup
  site\                    THE WEBPAGE (multi-page version)
    index.html             home: title + 4-per-row rounded boxes "N - NAME" (built from nav.js PAGES)
    builder.html           PAGE BUILDER form (not in PAGES); _preview.html = temporary preview
    01_key_points.html ... 12_principles.html   one file per original page
    13_patience.html       developed from page 2 line "BE PATIENT - FOCUSED AND DISCIPLINED"
    14_page_14 .. 16_page_16.html   placeholders (marked <!-- placeholder -->)
    css\motivate.css       shared look (fonts, colors, menu, page indicator, arrows, A button)
    js\nav.js              shared navigation; PAGES list (PAGES-BEGIN/END, one JSON object per
                           line) = single source of truth, rewritten by the page builder
  assets\                  MOTIVATE_ORIGINAL.html (original single-file version, reference only),
                           MOTIVATE.ico, MOTIVATE_info_page.docx (help), archives\ (old versions; *.html not on GitHub)
  assets\archives\saved\   site_backup_*.zip (before every CREATE / SAVE)
  docs\                    MOTIVATE NOTES.md, SESSION_HISTORY.md, sessions\ (raw transcripts)
  logs\app.log             rotating log (1 MB x 5), EDT timestamps
  tests\test_site.py       pytest: page list, links, balanced markup, launcher logic
  config.json              log_level, start_page
```

## Venv & Commands
- Python: C:\Users\Jerome\AppData\Local\Programs\Python\Python314\python.exe
- Venv: `.venv\` (create: `python -m venv .venv`, then `.venv\Scripts\pip install -r requirements.txt`)
- Launch: double-click `MOTIVATE.lnk`, or `.venv\Scripts\pythonw.exe main.py`
  (starts the server on 127.0.0.1:<port>, reuses it if already running; stops after idle_minutes;
  an older server, by server.API_VERSION, is stopped via POST /api/shutdown and replaced; bump
  API_VERSION whenever the API changes)
- View without launcher: open `site\index.html` in a browser (builder is then read-only)
- Test: `.venv\Scripts\python.exe -m pytest` (ask JR before running)

## Dependencies (requirements.txt, pinned)
- tzdata (America/New_York on Windows); pytest (tests); Pillow (icon generation)

## Config (config.json)
- `log_level`: INFO | DEBUG
- `start_page`: file in site\ opened by the launcher (default index.html; invalid -> index.html)
- `port`: local server port (default 8765)
- `idle_minutes`: server stops after this long with no requests (default 120; open pages ping every minute)
- `auto_upload`: true = every builder CREATE / SAVE is committed and pushed to GitHub (OK notice shows the result)

## Conventions
- Each page: `<body data-page="N">`, links `css/motivate.css` and `js/nav.js`; page-specific
  `.style-one`..`.style-seven` rules in its own `<style>` (scoped `.page .style-x`).
- Adding a page: use the PAGE BUILDER (renumbers files, data-page, JRn titles, links between pages,
  and PAGES). Manual: create `NN_name.html` and add one line to `PAGES` in `site\js\nav.js`.
- Editing: builder "Edit Existing Page" mode (or builder.html?edit=N) loads the page into the form;
  SAVE re-renders it in builder format (line-N classes, margin-bottom spacing); number and tab title kept,
  a new name renames the file and updates links. Original sub-section `gap` becomes each line's spacing after.
- Line text keeps <strong> <b> <em> <i> <u> <br> <a href="NN_x.html"> and entities (&nbsp; &bull;);
  everything else is escaped (clean_text / editable_text). Max 20 lines per page.
- Builder units are rem; fonts, font types, and alignments are whitelisted in app\page_builder.py.
- Builder POSTs are accepted only with Host/Origin = 127.0.0.1/localhost:<port> and a JSON body.
- Look & feel: white background, Arial Black / Arial, colors #083a5e navy, #0070c0 blue,
  #ff0000 red, #00b050 green; rem-based fluid font sizes.
- Navigation: hamburger menu ("N - NAME", current page gray band), ◄ ► wrap around, Left/Right arrow keys, Esc closes menu.
- Old links `MOTIVATE.html#N` map to `site\index.html#N`, which redirects to page N.
- American spelling; all times EDT. Launcher runs under pythonw.exe (no console, no print()).
- Website (GitHub Pages) has no A button (https); the builder only works on the local server.
- Log every session in `docs\SESSION_HISTORY.md` (date, request, decisions, files changed).
