# MOTIVATE WEBPAGE



###### FUNCTION: Trading motivation pages (rules, principles, reminders) shown full screen during the session

###### 

###### Filename: "main.py" (launcher) + "site\index.html" (webpage)

###### Folder: "C:\\Users\\Jerome\\PYTHON\_PROJECTS\\motivate\_webpage"

###### Date Created: 20261028

###### Created by: JR / Claude



### App Description \& Operation:

1. The MOTIVATE shortcut runs main.py with pythonw.exe (no console) and opens site\index.html in the default browser.
2. index.html shows a tile for every page; each page is its own HTML file (01 to 13).
3. Navigation on every page: hamburger menu, ◄ ► arrows (wrap around), Left/Right arrow keys, Esc closes the menu.
4. Page 2 line "BE PATIENT - FOCUSED AND DISCIPLINED" links to page 13 (Patience).
5. config.json: start_page, log_level. Log: logs\app.log (EDT).



#### CLAUDE App Setup Description:

Split the single-file MOTIVATE.html into site\ (shared css\motivate.css + js\nav.js, one HTML per page),
added index.html landing page and 13_patience.html, .venv, requirements.txt, launcher, tests, icon,
shortcut, help docx, CLAUDE.md, and session history.



##### 20261028 Update



1\. Created multi-page version in site\ (original MOTIVATE.html kept unchanged).

2\. New page 13 PATIENCE developed from "BE PATIENT - FOCUSED AND DISCIPLINED".

3\. Added Left/Right arrow-key navigation; old MOTIVATE.html#N links redirect via index.html#N.



##### 20261028 Update 2



1\. Home page boxes: "N - NAME", rounded corners, shorter and wider, black Arial text, 4 per row.

2\. Placeholder pages 14 - 16 (PAGE 14, PAGE 15, PAGE 16).

3\. PAGE BUILDER: black "A" circle (bottom right of every page) opens site\builder.html. Inputs: page number (renumbers the following pages), page name, horizontal/vertical alignment with indents, lines 1 - 20 (text, font, size, type, color, spacing after). PREVIEW / CREATE / RESET / EXIT.

4\. The shortcut now starts a local server (app\server.py, 127.0.0.1:8765) needed by the builder; it stops after 120 idle minutes. Site backup zip before every CREATE in assets\archives\saved.



##### 20261028 Update 3



1\. Page builder: Edit Existing Page mode. Enter the page number, LOAD fills the form (name, alignment, lines 1 - 20 with font, size, type, color, spacing after) from that page, SAVE rewrites it (backup first).

2\. Lines are now dynamic: + adds a line below (same style), x deletes a line, ADD LINE adds at the end (20 max).

3\. Line text keeps bold/italic/line-break tags, links, and &nbsp; spacers, so original pages edit without losing formatting.



4\. Fixed: Edit Existing Page error with an older server still running. The shortcut now replaces an older MOTIVATE server automatically; switching mode no longer asks for confirmation unless an edited page is unsaved.

5\. Side menu: "1 - KEY POINTS" style, Arial 16 bold black caps, tighter spacing; current page has a gray band.



##### Next Update

endfile
