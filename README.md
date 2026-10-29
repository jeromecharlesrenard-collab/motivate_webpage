# motivate_webpage
Website: https://jeromecharlesrenard-collab.github.io/motivate_webpage/

MOTIVATE - full-screen trading motivation pages (rules, principles, reminders) kept in view
during the trading session.

- `site/index.html` - home page with a box for every page
- `site/01_key_points.html` ... - one HTML file per page
- `site/css/motivate.css`, `site/js/nav.js` - shared look and navigation (menu, arrows, arrow keys)
- `site/builder.html` + `app/` - in-page PAGE BUILDER (create or edit pages), served by a small
  local Python server on 127.0.0.1
- `main.py` - launcher (starts the local server and opens the home page)
- `tests/` - pytest checks

Run: `python -m venv .venv`, `.venv\Scripts\pip install -r requirements.txt`,
then `.venv\Scripts\pythonw.exe main.py`. Without the launcher, open `site/index.html`
(the page builder is then read-only).
