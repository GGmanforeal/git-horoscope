"""The actual science. Every horoscope line is backed by one of these numbers.

Ideas borrowed from software-analytics research ("Your Code as a Crime Scene", A. Tornhill):
hotspots = files that change often AND are big; knowledge islands = files only one person
touches; temporal coupling = files that always change together.
"""
from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from itertools import combinations

from .gitlog import Commit

FIX_RE = re.compile(r"\b(fix(e[sd])?|bug|bugfix|hotfix|oops|revert|typo|broken|patch|tuzat\w*|исправ\w*)\b", re.I)
# "Panic" messages say nothing about the change: the whole subject is one of these (or yells).
PANIC_RE = re.compile(
    r"^\s*(wip|final\W*\w{0,6}|asdf\w*|test\d*|temp|tmp|stuff|changes?|updates?|updated|misc|fix(es|ed)?|small fix|"
    r"minor|\.+|idk|please work|pls work|work pls|ok|done|save|commit|\S{1,3})\s*[!.?]*\s*$|!{3,}|\?{3,}",
    re.I,
)
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
BUCKETS = [("night", range(0, 6)), ("morning", range(6, 12)), ("afternoon", range(12, 18)), ("evening", range(18, 24))]


@dataclass
class Hotspot:
    path: str
    revisions: int
    loc: int
    churn: int
    authors: int
    score: float


@dataclass
class Island:
    path: str
    owner: str
    share: float
    revisions: int


@dataclass
class Analysis:
    n_commits: int
    authors: list[tuple[str, int]]
    first: str
    last: str
    heatmap: list[list[int]]  # [weekday][hour]
    chronotype: str
    night_share: float
    weekend_share: float
    lucky_hour: int
    lucky_day: str
    hotspots: list[Hotspot]
    islands: list[Island]
    bus_factor: int
    coupling: list[tuple[str, str, int, float]]
    regret: dict[str, tuple[int, int]]  # bucket -> (regretted, total)
    night_penalty: float | None
    msg_avg_len: float
    msg_panic_share: float
    msg_fix_share: float
    worst_messages: list[str]
    longest_streak: int
    longest_break: int
    biggest_commit: tuple[str, int, str] | None
    extras: dict = field(default_factory=dict)


def _bucket(hour: int) -> str:
    return next(name for name, hours in BUCKETS if hour in hours)


def heatmap(commits: list[Commit]) -> list[list[int]]:
    grid = [[0] * 24 for _ in range(7)]
    for c in commits:
        grid[c.when.weekday()][c.when.hour] += 1
    return grid


def chronotype(commits: list[Commit]) -> tuple[str, float, float]:
    n = len(commits) or 1
    night = sum(1 for c in commits if c.when.hour >= 22 or c.when.hour < 5) / n
    early = sum(1 for c in commits if 5 <= c.when.hour < 9) / n
    weekend = sum(1 for c in commits if c.when.weekday() >= 5) / n
    office = sum(1 for c in commits if c.when.weekday() < 5 and 9 <= c.when.hour < 18) / n
    if night >= 0.3:
        kind = "Night Owl 🦉"
    elif early >= 0.25:
        kind = "Early Bird 🐦"
    elif weekend >= 0.4:
        kind = "Weekend Warrior ⚔️"
    elif office >= 0.6:
        kind = "Nine-to-Fiver 💼"
    else:
        kind = "Chaotic Neutral 🌀"
    return kind, night, weekend


def hotspots(commits: list[Commit], loc: dict[str, int], top: int = 10) -> list[Hotspot]:
    revs: Counter[str] = Counter()
    churn: Counter[str] = Counter()
    who: defaultdict[str, set[str]] = defaultdict(set)
    for c in commits:
        for f in c.files:
            revs[f.path] += 1
            churn[f.path] += f.churn
            who[f.path].add(c.author)
    out = []
    for path, r in revs.items():
        if path not in loc:  # deleted files can't hurt you any more
            continue
        size = loc[path]
        out.append(Hotspot(path, r, size, churn[path], len(who[path]), round(r * math.log2(2 + size), 2)))
    out.sort(key=lambda h: (-h.score, h.path))
    return out[:top]


def knowledge(commits: list[Commit], loc: dict[str, int], threshold: float = 0.8) -> tuple[list[Island], int]:
    """Knowledge islands (one author made ≥80% of the changes) and the repo's bus factor.

    Bus factor = the smallest number of people who together are the main author of more
    than half of the files. If they all left, most of the code would have no expert.
    """
    per_file: defaultdict[str, Counter[str]] = defaultdict(Counter)
    for c in commits:
        for f in c.files:
            if f.path in loc:
                per_file[f.path][c.author] += max(1, f.churn)
    islands = []
    main_author: Counter[str] = Counter()
    for path, ctr in per_file.items():
        total = sum(ctr.values())
        owner, amount = ctr.most_common(1)[0]
        main_author[owner] += 1
        share = amount / total
        revs = sum(1 for c in commits for f in c.files if f.path == path)
        if share >= threshold and len(ctr) >= 1 and revs >= 2:
            islands.append(Island(path, owner, round(share, 2), revs))
    islands.sort(key=lambda i: (-i.revisions, i.path))
    files = len(per_file) or 1
    covered, bus = 0, 0
    for _, n in main_author.most_common():
        covered += n
        bus += 1
        if covered > files / 2:
            break
    return islands, bus


def coupling(commits: list[Commit], min_shared: int = 3, top: int = 8) -> list[tuple[str, str, int, float]]:
    """Files that change in the same commit again and again (degree = shared / min(revs))."""
    pair: Counter[tuple[str, str]] = Counter()
    revs: Counter[str] = Counter()
    for c in commits:
        paths = sorted({f.path for f in c.files})
        if len(paths) > 30:  # giant refactors/formatting commits say nothing about coupling
            continue
        revs.update(paths)
        pair.update(combinations(paths, 2))
    out = []
    for (a, b), n in pair.items():
        if n >= min_shared:
            out.append((a, b, n, round(n / min(revs[a], revs[b]), 2)))
    out.sort(key=lambda x: (-x[2], -x[3], x[0]))
    return out[:top]


def regret(commits: list[Commit], window_hours: int = 72) -> tuple[dict[str, tuple[int, int]], float | None]:
    """How often was a commit followed by a *fix* to the same files within 72 hours, by time of day?"""
    stats = {name: [0, 0] for name, _ in BUCKETS}
    for i, c in enumerate(commits):
        if FIX_RE.search(c.subject) or not c.files:
            continue
        files = {f.path for f in c.files}
        limit = c.when + timedelta(hours=window_hours)
        regretted = False
        for later in commits[i + 1 :]:
            if later.when > limit:
                break
            if FIX_RE.search(later.subject) and files & {f.path for f in later.files}:
                regretted = True
                break
        b = _bucket(c.when.hour)
        stats[b][1] += 1
        stats[b][0] += regretted
    out = {k: (v[0], v[1]) for k, v in stats.items()}
    night_r, night_n = out["night"]
    day_r = sum(out[k][0] for k in ("morning", "afternoon", "evening"))
    day_n = sum(out[k][1] for k in ("morning", "afternoon", "evening"))
    penalty = None
    if night_n >= 3 and day_n >= 3 and day_r > 0:
        penalty = round((night_r / night_n) / (day_r / day_n), 1)
    return out, penalty


def messages(commits: list[Commit]) -> tuple[float, float, float, list[str]]:
    if not commits:
        return 0.0, 0.0, 0.0, []
    subjects = [c.subject for c in commits]
    avg = sum(len(s) for s in subjects) / len(subjects)
    panic = [s for s in subjects if PANIC_RE.search(s)]
    fixes = sum(1 for s in subjects if FIX_RE.search(s))
    worst = sorted(set(panic), key=lambda s: (len(s), s))[:5]
    return round(avg, 1), round(len(panic) / len(subjects), 3), round(fixes / len(subjects), 3), worst


def streaks(commits: list[Commit]) -> tuple[int, int]:
    days = sorted({c.when.date() for c in commits})
    if not days:
        return 0, 0
    best = run = 1
    gap = 0
    for a, b in zip(days, days[1:]):
        d = (b - a).days
        run = run + 1 if d == 1 else 1
        best = max(best, run)
        gap = max(gap, d - 1)
    return best, gap


def analyze(commits: list[Commit], loc: dict[str, int]) -> Analysis:
    if not commits:
        raise ValueError("this repository has no commits to read the stars from")
    grid = heatmap(commits)
    kind, night, weekend = chronotype(commits)
    hours = Counter(c.when.hour for c in commits)
    days = Counter(c.when.weekday() for c in commits)
    islands, bus = knowledge(commits, loc)
    reg, penalty = regret(commits)
    avg, panic, fixes, worst = messages(commits)
    best, gap = streaks(commits)
    big = max(commits, key=lambda c: c.churn)
    return Analysis(
        n_commits=len(commits),
        authors=Counter(c.author for c in commits).most_common(),
        first=commits[0].when.date().isoformat(),
        last=commits[-1].when.date().isoformat(),
        heatmap=grid,
        chronotype=kind,
        night_share=round(night, 3),
        weekend_share=round(weekend, 3),
        lucky_hour=hours.most_common(1)[0][0],
        lucky_day=DAYS[days.most_common(1)[0][0]],
        hotspots=hotspots(commits, loc),
        islands=islands,
        bus_factor=bus,
        coupling=coupling(commits),
        regret=reg,
        night_penalty=penalty,
        msg_avg_len=avg,
        msg_panic_share=panic,
        msg_fix_share=fixes,
        worst_messages=worst,
        longest_streak=best,
        longest_break=gap,
        biggest_commit=(big.subject, big.churn, big.sha[:7]) if big.churn else None,
    )
