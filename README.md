# smritajain31.github.io

Smrita Jain's personal site and public archive.

- `index.html` — home page (hand-written; only the `<!-- SJ:… -->` blocks are generated)
- `archive/` — the full archive, generated from `data/archive.json`
- `data/archive.json` — every entry: talks, press, writing, books, art, design and AI work, teaching, education, awards, TAG, community and profiles
- `data/link-status.json` — weekly link check results
- `sj/` — SJ, the research and watch agent: playbook (`SJ.md`), search list (`watchlist.json`), builder and link checker

To add or fix an entry by hand: edit `data/archive.json`, run `python3 sj/build.py`, commit.
