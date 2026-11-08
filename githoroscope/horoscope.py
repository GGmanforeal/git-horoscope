"""Turns the analysis into a horoscope. Every reading quotes the number it is based on."""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

from .analysis import Analysis

SIGNS = [
    # (name, symbol, (month, day) start, developer trait)
    ("Capricorn", "♑", (12, 22), "disciplined, writes changelogs, secretly enjoys refactoring legacy code"),
    ("Aquarius", "♒", (1, 20), "rewrites everything in a new framework every six months"),
    ("Pisces", "♓", (2, 19), "dreamy, names variables after feelings"),
    ("Aries", "♈", (3, 21), "ships first, writes tests never"),
    ("Taurus", "♉", (4, 20), "stubborn about tabs vs spaces, usually right"),
    ("Gemini", "♊", (5, 21), "keeps two branches that do the same thing"),
    ("Cancer", "♋", (6, 21), "protective of their code, takes code review personally"),
    ("Leo", "♌", (7, 23), "README longer than the code, with badges"),
    ("Virgo", "♍", (8, 23), "100% test coverage, 0% fun at parties"),
    ("Libra", "♎", (9, 23), "can't decide between two libraries, so uses both"),
    ("Scorpio", "♏", (10, 23), "mysterious; comments are rare and cryptic"),
    ("Sagittarius", "♐", (11, 22), "adventurous, deploys on Friday afternoons"),
]


def zodiac(d: date) -> tuple[str, str, str]:
    md = (d.month, d.day)
    sign = SIGNS[0]
    for s in SIGNS[1:]:
        if md >= s[2]:
            sign = s
    if md >= (12, 22):
        sign = SIGNS[0]
    return sign[0], sign[1], sign[3]


@dataclass
class Reading:
    planet: str
    title: str
    text: str
    evidence: str


def _pct(x: float) -> str:
    return f"{round(100 * x)}%"


def weekly_change_probability(revisions: int, first: str, last: str) -> float:
    """Poisson estimate: P(at least one change next week) = 1 - e^(-rate per week)."""
    weeks = max(1.0, (date.fromisoformat(last) - date.fromisoformat(first)).days / 7)
    return 1 - math.exp(-revisions / weeks)


def readings(a: Analysis, repo: str) -> list[Reading]:
    out: list[Reading] = []
    name, symbol, trait = zodiac(date.fromisoformat(a.first))
    out.append(Reading("☀️", f"Sun in {name} {symbol}", f"{repo} was born on {a.first}, which makes it a {name}: {trait}.",
                       f"{a.n_commits} commits by {len(a.authors)} author(s), {a.first} → {a.last}"))

    out.append(Reading("🌙", f"Moon: {a.chronotype}",
                       f"Your lucky hour is {a.lucky_hour:02d}:00 and your lucky day is {a.lucky_day}. "
                       + ("The moon is basically a co-author." if a.night_share >= 0.3 else
                          "Weekends are for coding, apparently." if a.weekend_share >= 0.4 else
                          "The stars approve of your sleep schedule."),
                       f"{_pct(a.night_share)} of commits between 22:00 and 05:00, {_pct(a.weekend_share)} on weekends"))

    if a.hotspots:
        h = a.hotspots[0]
        p = weekly_change_probability(h.revisions, a.first, a.last)
        out.append(Reading("☿", f"Mercury is in retrograde in {h.path}",
                           f"This file attracts chaos. It is your biggest hotspot. Approach it with tests and a cup of tea. "
                           f"The stars give a {_pct(p)} chance it changes again next week.",
                           f"{h.revisions} changes, {h.loc} lines, {h.churn} lines churned, {h.authors} author(s)"))

    night_r, night_n = a.regret["night"]
    if a.night_penalty is not None and a.night_penalty > 1.2:
        out.append(Reading("♂", "Mars warns about the night shift",
                           f"Commits made between midnight and 6 am needed a fix {a.night_penalty}× more often than daytime commits. "
                           "Mars has one piece of advice: sleep.",
                           f"{night_r}/{night_n} night commits were followed by a fix to the same files within 72 h"))
    elif night_n:
        out.append(Reading("♂", "Mars is calm",
                           "Your late-night commits are no worse than your daytime ones. Suspicious, but the stars respect it.",
                           f"{night_r}/{night_n} night commits needed a fix within 72 h"))
    else:
        out.append(Reading("♂", "Mars sees no night commits",
                           "You do not code after midnight. Mars is proud and slightly bored.", "0 commits between 00:00 and 06:00"))

    if a.coupling:
        x, y, n, deg = a.coupling[0]
        out.append(Reading("♀", "Venus found soulmates",
                           f"{x} and {y} are in a relationship: when one changes, the other follows. "
                           "Venus suggests couples therapy (also known as refactoring).",
                           f"changed together {n} times ({_pct(deg)} of the time)"))

    if a.islands:
        isl = a.islands[0]
        out.append(Reading("♄", f"Saturn: bus factor {a.bus_factor}",
                           f"Only {isl.owner} truly understands {isl.path}. If {isl.owner} wins the lottery tomorrow, "
                           "that file becomes an ancient mystery. Saturn recommends pair programming.",
                           f"{isl.owner} wrote {_pct(isl.share)} of its changes · {len(a.islands)} knowledge island(s) in total"))
    else:
        out.append(Reading("♄", f"Saturn: bus factor {a.bus_factor}",
                           "Knowledge is nicely shared. Saturn has nothing to complain about, which annoys Saturn.",
                           "no file is dominated by a single author"))

    worst = ", ".join(f"“{m}”" for m in a.worst_messages[:3]) or "none, impressively"
    out.append(Reading("♃", "Jupiter reads your commit messages",
                       f"Your messages average {a.msg_avg_len:.0f} characters. "
                       + ("Jupiter is moved to tears. Not good tears." if a.msg_panic_share >= 0.15 else "Jupiter finds them mostly readable.")
                       + f" Your darkest moments: {worst}.",
                       f"{_pct(a.msg_panic_share)} vague messages, {_pct(a.msg_fix_share)} are fixes"))

    out.append(Reading("⭐", "Your streaks",
                       f"Longest coding streak: {a.longest_streak} day(s) in a row. Longest silence: {a.longest_break} day(s). We don't talk about it.",
                       (f"biggest commit: “{a.biggest_commit[0]}” ({a.biggest_commit[1]} lines, {a.biggest_commit[2]})" if a.biggest_commit else "")))

    if len(a.authors) >= 2:
        (p1, n1), (p2, n2) = a.authors[:2]
        out.append(Reading("💞", "Compatibility",
                           f"{p1} and {p2} are this repo's power couple. Together they made most of the commits. The stars ship it.",
                           f"{n1} + {n2} of {a.n_commits} commits"))
    return out


def one_liner(a: Analysis, repo: str) -> str:
    name, symbol, _ = zodiac(date.fromisoformat(a.first))
    hs = f" Mercury is in retrograde in {a.hotspots[0].path}." if a.hotspots else ""
    return f"{repo} is a {name} {symbol} {a.chronotype}.{hs}"
