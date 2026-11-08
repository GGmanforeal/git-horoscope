"""A starry, self-contained HTML report (inline CSS + SVG, no JavaScript, no external assets)."""
from __future__ import annotations

import html
from datetime import date

from .analysis import DAYS, Analysis
from .horoscope import one_liner, readings, zodiac


def _e(x: object) -> str:
    return html.escape(str(x))


def _heatmap(a: Analysis) -> str:
    cell, left, top = 22, 48, 22
    peak = max(max(r) for r in a.heatmap) or 1
    parts = [f'<svg viewBox="0 0 {left + 24 * cell + 4} {top + 7 * cell + 4}" class="heat" role="img" aria-label="Commits by weekday and hour">']
    for h in range(0, 24, 3):
        parts.append(f'<text x="{left + h * cell + cell / 2}" y="14" class="ax">{h:02d}</text>')
    for d in range(7):
        parts.append(f'<text x="{left - 8}" y="{top + d * cell + 15}" class="ax" text-anchor="end">{DAYS[d]}</text>')
        for h in range(24):
            v = a.heatmap[d][h]
            op = 0.07 if v == 0 else 0.25 + 0.75 * v / peak
            parts.append(f'<rect x="{left + h * cell}" y="{top + d * cell}" width="{cell - 3}" height="{cell - 3}" rx="4" fill="#ffd36e" opacity="{op:.2f}"><title>{DAYS[d]} {h:02d}:00 — {v} commits</title></rect>')
    parts.append("</svg>")
    return "".join(parts)


def _hotspots(a: Analysis) -> str:
    if not a.hotspots:
        return '<p class="muted">No hotspots yet.</p>'
    peak = a.hotspots[0].score
    rows = []
    for h in a.hotspots[:8]:
        w = 100 * h.score / peak
        rows.append(
            f'<div class="hs"><div class="hs-name" title="{_e(h.path)}">{_e(h.path)}</div>'
            f'<div class="hs-bar"><span style="width:{w:.0f}%"></span></div>'
            f'<div class="hs-num">{h.revisions}× · {h.loc} loc</div></div>'
        )
    return "".join(rows)


def _regret(a: Analysis) -> str:
    rows = []
    labels = {"night": "🌑 00–06", "morning": "🌅 06–12", "afternoon": "☀️ 12–18", "evening": "🌆 18–24"}
    for k, (r, n) in a.regret.items():
        rate = r / n if n else 0
        rows.append(
            f'<div class="hs"><div class="hs-name">{labels[k]}</div><div class="hs-bar red"><span style="width:{100 * rate:.0f}%"></span></div>'
            f'<div class="hs-num">{rate * 100:.0f}% ({r}/{n})</div></div>'
        )
    return "".join(rows)


def render(a: Analysis, repo: str) -> str:
    sign, symbol, _ = zodiac(date.fromisoformat(a.first))
    cards = "".join(
        f'<article class="reading"><div class="planet">{_e(r.planet)}</div><div><h3>{_e(r.title)}</h3><p>{_e(r.text)}</p>'
        f'<p class="evidence">📊 {_e(r.evidence)}</p></div></article>'
        for r in readings(a, repo)
    )
    coupling = "".join(f"<tr><td>{_e(x)}</td><td>{_e(y)}</td><td>{n}</td><td>{d * 100:.0f}%</td></tr>" for x, y, n, d in a.coupling) or '<tr><td colspan="4" class="muted">No couples found.</td></tr>'
    islands = "".join(f"<tr><td>{_e(i.path)}</td><td>{_e(i.owner)}</td><td>{i.share * 100:.0f}%</td><td>{i.revisions}</td></tr>" for i in a.islands[:8]) or '<tr><td colspan="4" class="muted">Knowledge is well shared.</td></tr>'
    authors = "".join(f"<li>{_e(n)} <b>{c}</b></li>" for n, c in a.authors[:8])
    stars = "".join(f'<i style="left:{(i * 37) % 100}%;top:{(i * 53) % 100}%;animation-delay:{(i % 7) * .4}s"></i>' for i in range(60))
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Git Horoscope — {_e(repo)}</title><style>{CSS}</style></head><body><div class="sky">{stars}</div>
<header><div class="sign">{symbol}</div><div><p class="kicker">Git Horoscope for</p><h1>{_e(repo)}</h1>
<p class="sub">{_e(one_liner(a, repo))}</p></div></header>
<main>
<section class="readings">{cards}</section>
<section class="grid">
<div class="card wide"><h2>When the stars align (commits by weekday × hour)</h2>{_heatmap(a)}</div>
<div class="card"><h2>Hotspots</h2><p class="muted">Changes × log(size): files that change often <i>and</i> are big.</p>{_hotspots(a)}</div>
<div class="card"><h2>Regret by time of day</h2><p class="muted">Share of commits followed by a fix to the same files within 72 hours.</p>{_regret(a)}</div>
<div class="card"><h2>Soulmate files</h2><p class="muted">Temporal coupling: files that change in the same commit.</p>
<table><tr><th>File</th><th>File</th><th>Together</th><th>Degree</th></tr>{coupling}</table></div>
<div class="card"><h2>Knowledge islands</h2><p class="muted">One person made ≥ 80% of the changes. Bus factor of the repo: <b>{a.bus_factor}</b>.</p>
<table><tr><th>File</th><th>Keeper</th><th>Share</th><th>Changes</th></tr>{islands}</table></div>
<div class="card"><h2>The cast</h2><ul class="authors">{authors}</ul></div>
</section></main>
<footer>{sign} {symbol} · read from {a.n_commits} commits · made with git-horoscope by Rahimjon Xasanov</footer></body></html>"""


CSS = """
*{box-sizing:border-box}body{margin:0;font-family:'Segoe UI',system-ui,sans-serif;background:#0b0b1f;color:#ecebff;min-height:100vh}
.sky{position:fixed;inset:0;background:radial-gradient(1000px 600px at 80% -10%,#3b2a7a 0%,transparent 60%),radial-gradient(800px 500px at 0% 110%,#123a6b 0%,transparent 60%);z-index:-1;overflow:hidden}
.sky i{position:absolute;width:2px;height:2px;background:#fff;border-radius:50%;opacity:.6;animation:tw 3s infinite}
@keyframes tw{50%{opacity:.1}}
header{display:flex;gap:22px;align-items:center;padding:34px 40px 10px;max-width:1200px;margin:0 auto}
.sign{font-size:72px;width:110px;height:110px;border-radius:50%;display:grid;place-items:center;background:linear-gradient(135deg,#ffd36e,#ff7ab6);color:#2a1050;box-shadow:0 0 50px rgba(255,211,110,.35)}
.kicker{margin:0;text-transform:uppercase;letter-spacing:.2em;font-size:12px;color:#b9b4ff}h1{margin:2px 0;font-size:40px;font-family:Georgia,serif}.sub{margin:0;color:#c9c6ff}
main{max-width:1200px;margin:0 auto;padding:16px 40px 30px}
.readings{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:900px){.readings,.grid{grid-template-columns:1fr!important}}
.reading{display:flex;gap:14px;background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:16px 18px;backdrop-filter:blur(4px)}
.planet{font-size:30px;width:46px;flex:none;text-align:center}.reading h3{margin:0 0 6px;font-size:17px;color:#ffd36e;font-family:Georgia,serif}
.reading p{margin:0;line-height:1.5;font-size:14.5px}.reading .evidence{margin-top:8px;font-family:Consolas,monospace;font-size:12px;color:#a6a2d9}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:18px}.card{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.1);border-radius:16px;padding:16px 18px}
.wide{grid-column:1/-1}h2{margin:0 0 6px;font-size:16px;font-family:Georgia,serif;color:#fff}.muted{color:#a6a2d9;font-size:13px;margin:0 0 10px}
.heat{width:100%}.heat .ax{fill:#a6a2d9;font-size:9px;text-anchor:middle}
.hs{display:grid;grid-template-columns:minmax(0,1.3fr) 1fr 110px;gap:10px;align-items:center;margin:6px 0;font-size:13px}
.hs-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:Consolas,monospace}.hs-bar{background:rgba(255,255,255,.08);border-radius:6px;height:12px;overflow:hidden}
.hs-bar span{display:block;height:100%;background:linear-gradient(90deg,#ffd36e,#ff7ab6)}.hs-bar.red span{background:linear-gradient(90deg,#ff7ab6,#ff4d6d)}.hs-num{color:#c9c6ff;font-size:12px;text-align:right}
table{width:100%;border-collapse:collapse;font-size:12.5px}th,td{text-align:left;padding:5px 6px;border-bottom:1px solid rgba(255,255,255,.08)}th{color:#a6a2d9;font-weight:600}td{font-family:Consolas,monospace}
.authors{list-style:none;padding:0;margin:0;columns:2}.authors li{padding:3px 0}
footer{text-align:center;color:#8f8bc6;font-size:12px;padding:10px 0 26px}
"""
