/* ==========================================================================
   MOTIVATE - shared navigation for every page
   - Hamburger menu + slide-out panel, page number, ◄ ► page toggles
   - Esc closes the menu; Left/Right arrow keys go to the previous/next page
   - Black "A" circle (bottom right) opens the page builder
   Each page declares itself with <body data-page="N"> (index.html = "0").
   The PAGES block below is rewritten by the page builder (app/page_builder.py):
   keep one JSON object per line between the PAGES-BEGIN / PAGES-END markers.
   ========================================================================== */
(function () {
    // PAGES-BEGIN
    const PAGES = [
        {"id": "0", "file": "index.html", "label": "Home", "title": "MOTIVATE HOME"},
        {"id": "1", "file": "01_key_points.html", "label": "Key Points", "title": "MOTIVATE"},
        {"id": "2", "file": "02_marathon.html", "label": "Marathon", "title": "JR2"},
        {"id": "3", "file": "03_hope.html", "label": "Hope", "title": "JR3"},
        {"id": "4", "file": "04_stops.html", "label": "Stops", "title": "JR4"},
        {"id": "5", "file": "05_thinking.html", "label": "Thinking", "title": "JR5"},
        {"id": "6", "file": "06_page_6.html", "label": "Page 6", "title": "JR6"},
        {"id": "7", "file": "07_page_7.html", "label": "Page 7", "title": "JR7"},
        {"id": "8", "file": "08_page_8.html", "label": "Page 8", "title": "JR8"},
        {"id": "9", "file": "09_why.html", "label": "Why", "title": "JR9"},
        {"id": "10", "file": "10_rules.html", "label": "Rules", "title": "JR10"},
        {"id": "11", "file": "11_truths.html", "label": "Truths", "title": "JR11"},
        {"id": "12", "file": "12_principles.html", "label": "Principles", "title": "JR12"},
        {"id": "13", "file": "13_patience.html", "label": "Patience", "title": "JR13"},
        {"id": "14", "file": "14_page_14.html", "label": "Page 14", "title": "JR14"},
        {"id": "15", "file": "15_page_15.html", "label": "Page 15", "title": "JR15"},
        {"id": "16", "file": "16_page_16.html", "label": "Page 16", "title": "JR16"}
    ];
    // PAGES-END
    window.MOTIVATE_PAGES = PAGES;

    const currentId = document.body.getAttribute('data-page') || '0';
    let idx = PAGES.findIndex(function (p) { return p.id === currentId; });
    const known = idx !== -1;           // builder / preview pages are not in PAGES
    if (!known) idx = 0;
    const page = PAGES[idx];

    // Old single-file links (MOTIVATE.html#5) -> index.html#5 -> the matching page file.
    if (page.id === '0' && known) {
        const target = PAGES.find(function (p) { return p.id !== '0' && '#' + p.id === location.hash; });
        if (target) { location.replace(target.file); return; }
    }

    // ---------- Build the shared controls ----------
    const btn = document.createElement('button');
    btn.className = 'menu-btn';
    btn.id = 'menuBtn';
    btn.setAttribute('aria-label', 'Open menu');
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-controls', 'navPanel');
    btn.innerHTML = '<span></span><span></span><span></span>';

    const indicator = document.createElement('div');
    indicator.className = 'page-indicator';
    indicator.id = 'pageIndicator';
    indicator.textContent = (known && page.id !== '0') ? page.id : '';

    const toggles = document.createElement('div');
    toggles.className = 'page-toggle-group';
    toggles.id = 'pageToggleGroup';
    toggles.innerHTML =
        '<button class="page-toggle-btn" id="prevPageBtn" aria-label="Previous page">&#9668;</button>' +
        '<button class="page-toggle-btn" id="nextPageBtn" aria-label="Next page">&#9658;</button>';

    const panel = document.createElement('nav');
    panel.className = 'nav-panel';
    panel.id = 'navPanel';
    PAGES.forEach(function (p) {
        const a = document.createElement('a');
        a.href = p.file;
        a.textContent = (p.id === '0' ? '' : p.id + ' - ') + p.label.toUpperCase();   // "1 - KEY POINTS"
        a.title = a.textContent;
        if (known && p.id === page.id) {
            a.className = 'current';
            a.setAttribute('aria-current', 'page');
        }
        panel.appendChild(a);
    });

    const scrim = document.createElement('div');
    scrim.className = 'nav-scrim';
    scrim.id = 'navScrim';

    const controls = [btn, indicator, toggles, panel, scrim];
    // No A button on the website (https): the builder needs the local MOTIVATE server.
    if (currentId !== 'builder' && location.protocol !== 'https:') {
        const builderBtn = document.createElement('a');
        builderBtn.className = 'builder-btn';
        builderBtn.href = 'builder.html?at=' + (known ? Number(page.id) + 1 : PAGES.length);
        builderBtn.title = 'Page builder - create or edit a page';
        builderBtn.setAttribute('aria-label', 'Open the page builder (create or edit a page)');
        builderBtn.textContent = 'A';
        controls.push(builderBtn);
    }
    controls.forEach(function (el) {
        document.body.insertBefore(el, document.body.firstChild);
    });

    if (known) document.title = page.title;

    // ---------- Behavior ----------
    function setOpen(open) {
        panel.classList.toggle('open', open);
        scrim.classList.toggle('open', open);
        btn.setAttribute('aria-expanded', open);
        btn.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    }

    function goTo(step) {
        location.href = PAGES[(idx + step + PAGES.length) % PAGES.length].file;
    }

    function isTyping(el) {
        return el && (el.isContentEditable || /^(INPUT|SELECT|TEXTAREA)$/.test(el.tagName));
    }

    btn.addEventListener('click', function () {
        setOpen(!panel.classList.contains('open'));
    });
    document.getElementById('prevPageBtn').addEventListener('click', function () { goTo(-1); });
    document.getElementById('nextPageBtn').addEventListener('click', function () { goTo(1); });
    scrim.addEventListener('click', function () { setOpen(false); });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') setOpen(false);
        else if (isTyping(e.target) || e.altKey || e.ctrlKey || e.metaKey) return;
        else if (e.key === 'ArrowLeft') goTo(-1);
        else if (e.key === 'ArrowRight') goTo(1);
    });

    // Keep the local MOTIVATE server alive while a page is open (shortcut launch only).
    if (location.protocol === 'http:') {
        const ping = function () { fetch('/api/ping', { cache: 'no-store' }).catch(function () {}); };
        setInterval(ping, 60000);
    }
})();
