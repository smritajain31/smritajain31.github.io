#!/usr/bin/env python3
"""SJ site builder.

Reads data/archive.json (the source of truth) and data/link-status.json
(written by the weekly link checker) and generates:

  * archive/index.html  - the full, categorised archive
  * index.html          - only the blocks between <!-- SJ:...:start/end -->
                          markers are rewritten; everything else on the
                          homepage is left exactly as written.

Usage:  python3 sj/build.py            (build)
        python3 sj/build.py --check    (validate only, exit 1 on problems)
"""
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "archive.json"
LINKS = ROOT / "data" / "link-status.json"
HOME = ROOT / "index.html"
OUT = ROOT / "archive" / "index.html"

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
STATUSES = {"verified", "own-site", "cited"}
REQUIRED = {"id", "cats", "title", "source", "summary", "status", "via"}


def esc(s):
    return html.escape(str(s or ""), quote=True)


def fmt_date(d):
    if not d:
        return ""
    p = d.split("-")
    if len(p) == 1:
        return p[0]
    if len(p) == 2:
        return f"{MONTHS[int(p[1]) - 1]} {p[0]}"
    return f"{MONTHS[int(p[1]) - 1]} {int(p[2])}, {p[0]}"


def fmt_range(e):
    a, b = fmt_date(e.get("date")), fmt_date(e.get("end"))
    return f"{a} – {b}" if a and b else a


def sort_key(e):
    # newest first, undated last
    return e.get("date") or "0000"


def is_upcoming(e, today):
    d = e.get("date") or ""
    return len(d) == 10 and d >= today


def validate(data):
    problems = []
    cats = {c["id"] for c in data["categories"]}
    seen = set()
    for e in data["entries"]:
        missing = REQUIRED - e.keys()
        if missing:
            problems.append(f"{e.get('id')}: missing {sorted(missing)}")
        if e.get("id") in seen:
            problems.append(f"duplicate id {e['id']}")
        seen.add(e.get("id"))
        for c in e.get("cats", []):
            if c not in cats:
                problems.append(f"{e['id']}: unknown category {c}")
        if e.get("status") not in STATUSES:
            problems.append(f"{e['id']}: bad status {e.get('status')}")
        d = e.get("date")
        if d and not re.fullmatch(r"\d{4}(-\d{2}(-\d{2})?)?", d):
            problems.append(f"{e['id']}: bad date {d}")
        u = e.get("url")
        if u and not u.startswith(("http://", "https://")):
            problems.append(f"{e['id']}: bad url {u}")
    return problems


def load_links():
    try:
        return json.loads(LINKS.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def entry_html(e, links, today, show_cats=True, cat_labels=None):
    url = e.get("url")
    title = esc(e["title"])
    t = f'<a href="{esc(url)}" rel="noopener">{title} <span aria-hidden="true">↗</span></a>' if url else title
    badges = []
    if is_upcoming(e, today):
        badges.append('<span class="badge up">Upcoming</span>')
    st = e["status"]
    badges.append({
        "verified": '<span class="badge ok" title="SJ opened this source and confirmed it">Verified</span>',
        "own-site": '<span class="badge own" title="Stated on Smrita’s own sites">Own site</span>',
        "cited": '<span class="badge cite" title="Listed on her CV or Wikipedia; original not yet re-checked">Cited</span>',
    }[st])
    extra = []
    if e.get("cta") and url and is_upcoming(e, today):
        extra.append(f'<a class="cta" href="{esc(url)}" rel="noopener">{esc(e["cta"])} ↗</a>')
    for l in e.get("links", []):
        extra.append(f'<a href="{esc(l["url"])}" rel="noopener">{esc(l["label"])} ↗</a>')
    ls = links.get(url or "", {})
    if ls.get("status") == "dead":
        extra.append(f'<a href="https://web.archive.org/web/2024*/{esc(url)}" rel="noopener">Original moved · archived copy ↗</a>')
    meta = " · ".join(x for x in [esc(e["source"]), esc(e.get("kind")), esc(e.get("time"))] if x)
    also = ""
    if show_cats and cat_labels and len(e["cats"]) > 1:
        others = [cat_labels[c] for c in e["cats"][1:]]
        also = f'<span class="also">Also in {esc(", ".join(others))}</span>'
    search = " ".join([e["title"], e["source"], e.get("kind", ""), e["summary"], fmt_range(e)]).lower()
    return (
        f'<li class="entry" data-cats="{esc(" ".join(e["cats"]))}" data-q="{esc(search)}">'
        f'<div class="when">{esc(fmt_range(e))}</div>'
        f'<div class="what"><h3>{t}</h3><div class="meta">{meta}</div>'
        f'<p>{esc(e["summary"])}</p>'
        + (('<ul class="about">' + "".join(f"<li>{esc(a)}</li>" for a in e["about"]) + "</ul>") if e.get("about") and is_upcoming(e, today) else "")
        + (f'<p class="note-line">{esc(e["note"])}</p>' if e.get("note") and is_upcoming(e, today) else "")
        + f'<div class="foot">{"".join(badges)}{"".join(extra)}{also}</div></div></li>'
    )


ARCHIVE_CSS = """
.ar-hero{padding-top:64px;padding-bottom:28px}.ar-hero p{max-width:760px;font-size:17px}
.stats{display:flex;flex-wrap:wrap;gap:10px;margin:18px 0 6px}.stat{background:var(--pale);border:1px solid #eadce3;border-radius:999px;padding:6px 14px;font-size:13px;font-weight:600;color:#78234f}
.layout{display:grid;grid-template-columns:1fr 280px;gap:40px;align-items:start}
.infobox{border:1px solid #eadce3;background:#fff;font-size:14px;position:sticky;top:20px}.infobox h2{font-size:20px;margin:0;padding:14px 16px;background:var(--pale);border-bottom:1px solid #eadce3}.infobox dl{margin:0;padding:6px 16px 14px}.infobox dt{font-weight:700;margin-top:10px;font-size:12px;text-transform:uppercase;letter-spacing:.08em;color:#9a0c5c}.infobox dd{margin:2px 0 0}.infobox dd a{display:block}
.tools{padding:16px 0 12px;border-bottom:1px solid #eadce3}
.search{width:100%;font:16px Inter,Arial,sans-serif;padding:12px 14px;border:1px solid #dfbdce;border-radius:6px}.search:focus-visible{outline:3px solid #a30b5a;outline-offset:1px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.chip{font:600 13px Inter,Arial,sans-serif;border:1px solid #dfbdce;background:#fff;color:#78234f;border-radius:999px;padding:7px 13px;cursor:pointer}.chip:hover{background:#fff1f7}.chip[aria-pressed=true]{background:var(--pink);border-color:var(--pink);color:#fff}.chip:focus-visible{outline:3px solid #a30b5a;outline-offset:2px}
.cat{padding:44px 0 10px;border-bottom:1px solid #eadce3}.cat h2{font-size:clamp(28px,3.4vw,38px);margin-bottom:10px}
.entries{list-style:none;margin:0;padding:0}.entry{display:grid;grid-template-columns:130px 1fr;gap:20px;padding:18px 0;border-top:1px solid #f0e4ea}
.when{font-size:13px;color:#675a62;font-weight:600;padding-top:3px}.what h3{font-size:19px;margin:0 0 3px}.what h3 a{text-decoration:none;color:var(--ink)}.what h3 a:hover{color:#9b0759;text-decoration:underline}
.meta{font-size:13px;color:#9a0c5c;font-weight:600}.what p{margin:6px 0 8px;font-size:15px}
.foot{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;font-size:13px}
.badge{font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;padding:3px 8px;border-radius:4px}.badge.ok{background:#e9f6ee;color:#1d6b3a}.badge.own{background:#fff1f7;color:#8e004d}.badge.cite{background:#f3f0f2;color:#5d5258}.badge.up{background:var(--pink);color:#fff}
.cta{background:var(--pink);color:#fff!important;text-decoration:none;padding:6px 12px;border-radius:5px;font-weight:600}.cta:hover{background:#b0106c}
.also{color:#766a70}
.upnext{border:1px solid #f2b6d4;background:var(--pale);padding:20px 22px;margin:26px 0 0}.upnext .entries .entry{border-top:0;padding:6px 0}
.about{margin:0 0 8px;padding-left:20px;font-size:14px}.note-line{font-size:13px;color:#675a62;margin:0 0 10px}
.legend{font-size:14px;color:#4d4349}.legend li{margin:6px 0}
.empty{display:none;padding:30px 0;color:#675a62}
@media(max-width:1000px){.layout{grid-template-columns:1fr}.infobox{position:static;order:-1}}
@media(max-width:760px){.entry{grid-template-columns:1fr;gap:4px}.ar-hero{padding-top:40px}}
"""


def render_archive(data, links, base_css, today):
    cats = data["categories"]
    labels = {c["id"]: c["label"] for c in cats}
    entries = data["entries"]
    by_cat = {c["id"]: [] for c in cats}
    for e in entries:
        by_cat[e["cats"][0]].append(e)
    # entries also appear under secondary categories
    for e in entries:
        for c in e["cats"][1:]:
            by_cat[c].append(e)

    sources = {e["source"] for e in entries}
    upcoming = sorted([e for e in entries if is_upcoming(e, today)], key=lambda e: e["date"])

    side = "".join(f'<a href="#{c["id"]}">{esc(c["label"])}</a>' for c in cats if by_cat[c["id"]])
    chips = '<button class="chip" type="button" data-cat="all" aria-pressed="true">All</button>' + "".join(
        f'<button class="chip" type="button" data-cat="{c["id"]}" aria-pressed="false">{esc(c["label"])}</button>'
        for c in cats if by_cat[c["id"]])

    sections = []
    for c in cats:
        items = by_cat[c["id"]]
        if not items:
            continue
        items = sorted(items, key=sort_key, reverse=True)
        items = [e for e in items if is_upcoming(e, today)] + [e for e in items if not is_upcoming(e, today)]
        lis = "".join(entry_html(e, links, today, show_cats=(e["cats"][0] == c["id"]), cat_labels=labels) for e in items)
        sections.append(
            f'<section class="cat" id="{c["id"]}" data-section="{c["id"]}"><div class="eyebrow">{esc(c.get("eyebrow",""))}</div>'
            f'<h2>{esc(c["label"])}</h2><ul class="entries">{lis}</ul></section>')

    up_html = ""
    if upcoming:
        up_html = ('<div class="upnext" id="upcoming"><div class="eyebrow">Upcoming</div><ul class="entries">'
                   + "".join(entry_html(e, links, today, show_cats=False) for e in upcoming) + "</ul></div>")

    s = data["subject"]
    info = (
        f'<aside class="infobox" aria-label="Quick facts"><h2>{esc(s["name"])}</h2><dl>'
        f'<dt>Based in</dt><dd>{esc(s["based_in"])}</dd>'
        f'<dt>Company</dt><dd><a href="https://www.theaquariogroup.com/">{esc(s["company"])}</a></dd>'
        f'<dt>Known for</dt><dd>{esc(" · ".join(s["known_for"]))}</dd>'
        f'<dt>Websites</dt><dd>' + "".join(f'<a href="{esc(w["url"])}">{esc(w["label"])} ↗</a>' for w in s["websites"]) + "</dd>"
        f'<dt>Archive</dt><dd>{len(entries)} entries · {len(sources)} sources<br>Updated {esc(fmt_date(data["updated"]))}</dd>'
        "</dl></aside>")

    same_as = sorted({e["url"] for e in entries if "profiles" in e["cats"] and e.get("url")})
    ld = json.dumps({
        "@context": "https://schema.org", "@type": "Person", "name": s["name"],
        "url": "https://smritajain31.github.io/",
        "worksFor": {"@type": "Organization", "name": "The Aquario Group", "url": "https://www.theaquariogroup.com/"},
        "alumniOf": [{"@type": "CollegeOrUniversity", "name": "Pratt Institute"}],
        "sameAs": same_as,
    }, ensure_ascii=False)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smrita Jain | The archive</title>
<meta name="description" content="An organised, source-linked archive of Smrita Jain's talks, press, writing, books, art, design and AI work, teaching, awards and The Aquario Group.">
<link rel="canonical" href="https://smritajain31.github.io/archive/">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Bodoni+Moda:ital,opsz,wght@0,6..96,500;0,6..96,700;1,6..96,500&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{base_css}{ARCHIVE_CSS}</style>
<script type="application/ld+json">{ld}</script>
</head>
<body>
<aside class="sidebar" aria-label="Archive navigation">
<a class="side-name" href="../">SMRITA JAIN</a>
<img class="side-portrait" src="https://upload.wikimedia.org/wikipedia/commons/c/c3/Smrita-jain.jpg" alt="Smrita Jain" draggable="false" oncontextmenu="return false">
<details class="side-menu" open><summary>Explore the archive <span aria-hidden="true">☰</span></summary>
<nav class="side-links" aria-label="Archive sections"><a href="../">← Home</a><a href="#top">Overview</a>{'<a href="#upcoming">Upcoming</a>' if upcoming else ''}{side}</nav></details>
</aside>
<main id="top">
<div class="wrap">
<div class="ar-hero">
<div class="eyebrow">The archive · kept by SJ</div>
<h1>Everything, in one place.</h1>
<p>Talks, press, writing, books, art, design and AI work, teaching and The Aquario Group, gathered from across the web, checked against the original sources and linked back to where each one lives.</p>
<div class="stats"><span class="stat">{len(entries)} entries</span><span class="stat">{len(sources)} sources</span><span class="stat">{len(by_cat)} categories</span><span class="stat">Updated {esc(fmt_date(data["updated"]))}</span></div>
{up_html}
</div>
<div class="layout">
<div>
<div class="tools">
<label class="eyebrow" for="q">Search the archive</label>
<input id="q" class="search" type="search" placeholder="Try “Pratt”, “AI”, “London” or “2017”" autocomplete="off">
<div class="chips" role="group" aria-label="Filter by category">{chips}</div>
</div>
<p class="empty" id="empty">Nothing matches that yet.</p>
{"".join(sections)}
<section class="cat" id="about-archive">
<div class="eyebrow">How this works</div>
<h2>About this archive</h2>
<p>SJ, Smrita's research agent, searches the web twice a month for anything published by or about her and The Aquario Group, confirms it is really about her, and adds a short factual entry that links to the original. Every link is re-checked weekly; when a page disappears, SJ points to an archived copy.</p>
<ul class="legend">
<li><span class="badge ok">Verified</span> SJ opened the original source and confirmed it.</li>
<li><span class="badge own">Own site</span> Stated on Smrita's own websites.</li>
<li><span class="badge cite">Cited</span> Listed on her CV or Wikipedia; the original has not been re-checked yet.</li>
</ul>
<p>Entry descriptions are short summaries written by SJ. Smrita's own words live on the <a href="../">home page</a>. Spotted something missing or wrong? <a href="mailto:Smrita@SmritaJain.com">Email Smrita</a>.</p>
</section>
</div>
{info}
</div>
<footer class="footer"><p class="note">© Smrita Jain · Made with curiosity and a little pink.</p>
<p class="note">Profile photo: <a href="https://commons.wikimedia.org/wiki/File:Smrita-jain.jpg">Rm.marte21, via Wikimedia Commons</a> · <a href="https://creativecommons.org/licenses/by-sa/4.0/">CC BY-SA 4.0</a> · cropped for display</p></footer>
</div>
</main>
<script>
(function(){{
const q=document.getElementById('q'),chips=[...document.querySelectorAll('.chip')],secs=[...document.querySelectorAll('[data-section]')],empty=document.getElementById('empty');
let cat='all';
function apply(){{
 const t=q.value.trim().toLowerCase();let any=0;
 secs.forEach(s=>{{
  const on=cat==='all'||s.dataset.section===cat;let n=0;
  s.querySelectorAll('.entry').forEach(li=>{{const hit=on&&(!t||li.dataset.q.includes(t));li.hidden=!hit;if(hit)n++;}});
  s.hidden=!n;any+=n;
 }});
 empty.style.display=any?'none':'block';
}}
chips.forEach(c=>c.addEventListener('click',()=>{{cat=c.dataset.cat;chips.forEach(x=>x.setAttribute('aria-pressed',x===c));apply();}}));
q.addEventListener('input',apply);
const menu=document.querySelector('.side-menu'),media=matchMedia('(max-width:760px)');
function adapt(e){{menu.open=!e.matches}}adapt(media);media.addEventListener('change',adapt);
document.querySelectorAll('.side-links a').forEach(a=>a.addEventListener('click',()=>{{if(media.matches)menu.open=false}}));
}})();
</script>
</body>
</html>
"""


def render_home_talks(data, links, today):
    talks = [e for e in data["entries"] if "talks" in e["cats"]]
    up = sorted([e for e in talks if is_upcoming(e, today)], key=lambda e: e["date"])
    past = sorted([e for e in talks if not is_upcoming(e, today) and len(e.get("date") or "") >= 7], key=sort_key, reverse=True)[:6]

    def row(e, upcoming=False):
        url = e.get("url")
        title = esc(e["title"])
        t = f'<a href="{esc(url)}">{title} ↗</a>' if url else title
        when = esc(fmt_range(e) + (f" · {e['time']}" if e.get("time") else ""))
        tag = '<span class="sj-up">Upcoming</span> ' if upcoming else ""
        return f'<div class="row"><strong>{tag}{t}</strong><span>{esc(e["source"])} · {when}</span></div>'

    up_rows = ""  # upcoming items live in the Upcoming section
    return (
        '<section class="section" id="talks">'
        '<div class="eyebrow">On stage, on air, on Zoom</div>'
        '<h2>Talks, shows &amp; workshops <span class="emoji" aria-hidden="true">🎤</span></h2>'
        + (f'<div class="rows sj-upcoming">{up_rows}</div>' if up_rows else "")
        + '<div class="rows">' + "".join(row(e) for e in past) + "</div>"
        '<p><a href="archive/#talks">See every talk and interview in the archive ↗</a></p>'
        "</section>"
    )


WEEKDAYS = "Monday Tuesday Wednesday Thursday Friday Saturday Sunday".split()


def render_home_upcoming(data, today):
    up = sorted([e for e in data["entries"] if is_upcoming(e, today)], key=lambda e: e["date"])
    head = ('<section class="section" id="upcoming"><div class="eyebrow">Save the date</div>'
            '<h2>Upcoming <span class="emoji" aria-hidden="true">📅</span></h2>')
    if not up:
        return head + ('<p>Nothing is scheduled right now. New workshops, talks and exhibitions appear here first.</p>'
                       '<p><a href="archive/#talks">See past talks and workshops ↗</a></p></section>')
    cards = []
    for e in up:
        d = dt.date.fromisoformat(e["date"])
        about = "".join(f"<li>{esc(a)}</li>" for a in e.get("about", []))
        cta = (f'<a class="up-cta" href="{esc(e["url"])}" rel="noopener">{esc(e.get("cta", "Details"))} ↗</a>'
               if e.get("url") else "")
        cards.append(
            '<article class="up-card">'
            f'<div class="up-date" aria-hidden="true"><span>{MONTHS[d.month - 1]}</span><strong>{d.day}</strong><span>{WEEKDAYS[d.weekday()][:3]}</span></div>'
            '<div class="up-body">'
            f'<small>{esc(e.get("kind", ""))} · {esc(e["source"])}</small>'
            f'<h3>{esc(e["title"])}</h3>'
            f'<div class="up-when">{esc(WEEKDAYS[d.weekday()])}, {esc(fmt_date(e["date"]))}{(" · " + esc(e["time"])) if e.get("time") else ""}</div>'
            f'<p>{esc(e["summary"])}</p>'
            + (f'<div class="up-about"><strong>What we’ll cover</strong><ul>{about}</ul></div>' if about else "")
            + (f'<p class="up-note">{esc(e["note"])}</p>' if e.get("note") else "")
            + cta + "</div></article>")
    return head + "".join(cards) + "</section>"


def render_home_art(data):
    ents = data["entries"]
    cards = sorted([e for e in ents if e.get("home_art")], key=lambda e: e["home_art"])
    tiles = ["", " two", " three"]
    card_html = "".join(
        f'<a class="card" href="{esc(e.get("url", "https://www.smritajainart.com/"))}" rel="noopener">'
        f'<div class="art{tiles[i % 3]}">{esc(e["title"])}</div><div class="cardbody">'
        f'<small>{esc((e.get("kind") or "").split(" · ")[0].upper())}</small>'
        f'<p>{esc(e["summary"]) if len(e["summary"]) > 30 else "See the work on smritajainart.com"} ↗</p></div></a>'
        for i, e in enumerate(cards))
    ex = sorted([e for e in ents if "art" in e["cats"] and re.search(r"exhibition|art fair|showcase", (e.get("kind") or ""), re.I)],
                key=sort_key, reverse=True)
    rows = "".join(
        f'<div class="row"><strong>{esc(e["title"])}</strong><span>{esc(e["source"])} · {esc(fmt_date(e.get("date")))}</span></div>'
        for e in ex)
    return (
        '<section class="section" id="art"><div class="eyebrow">Paintings, installations, performance &amp; photography</div>'
        '<h2>Art &amp; exhibitions <span class="emoji" aria-hidden="true">🖼️</span></h2>'
        f'<div class="grid">{card_html}</div>'
        f'<h3 class="art-sub">Exhibitions</h3><div class="rows">{rows}</div>'
        '<div class="links art-links">'
        '<a href="https://www.smritajainart.com/">smritajainart.com ↗</a>'
        '<a href="https://www.smritajainart.com/paintings">Paintings ↗</a>'
        '<a href="https://www.smritajainart.com/installations-art-performance">Installations &amp; performance ↗</a>'
        '<a href="https://www.smritajainart.com/artist-statement">Artist statement ↗</a>'
        '<a href="https://www.smritajainart.com/selected-cv">Selected CV ↗</a>'
        '<a href="archive/#art">All art in the archive ↗</a>'
        "</div></section>")


def replace_block(text, name, new):
    pat = re.compile(rf"(<!-- SJ:{name}:start -->)(.*?)(<!-- SJ:{name}:end -->)", re.S)
    if not pat.search(text):
        raise SystemExit(f"index.html is missing the SJ:{name} markers")
    return pat.sub(lambda m: m.group(1) + new + m.group(3), text)


def main():
    data = json.loads(DATA.read_text())
    problems = validate(data)
    if problems:
        print("Archive data problems:\n  " + "\n  ".join(problems))
        sys.exit(1)
    if "--check" in sys.argv:
        print(f"OK: {len(data['entries'])} entries")
        return
    links = load_links()
    today = dt.date.today().isoformat()
    home = HOME.read_text()
    base_css = re.search(r"<style>(.*?)</style>", home, re.S).group(1)
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(render_archive(data, links, base_css, today))
    home = replace_block(home, "upcoming", render_home_upcoming(data, today))
    home = replace_block(home, "art", render_home_art(data))
    home = replace_block(home, "talks", render_home_talks(data, links, today))
    home = replace_block(home, "count", f'{len(data["entries"])} entries')
    HOME.write_text(home)
    print(f"Built archive/index.html with {len(data['entries'])} entries; homepage blocks refreshed")


if __name__ == "__main__":
    main()
