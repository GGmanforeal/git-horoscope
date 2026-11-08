"""Builds a realistic fake repository (≈160 commits, 3 months, 3 people) in one `git fast-import` call.

Planted on purpose, so the horoscope has something to find:
* `src/payments/checkout.py` is a hotspot (changes constantly and keeps growing);
* `src/api/routes.py` and `src/api/schemas.py` always change together;
* `src/legacy/billing_v1.py` is only ever touched by Dilshod (a knowledge island);
* commits made after midnight are much more likely to need a "fix" afterwards.
"""
from __future__ import annotations

import random
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

TZ = timezone(timedelta(hours=5))  # Tashkent
PEOPLE = [("Nodira Karimova", "nodira@example.com"), ("Dilshod Rakhimov", "dilshod@example.com"), ("Sevara Aliyeva", "sevara@example.com")]
FILES = [
    "src/payments/checkout.py", "src/payments/refunds.py", "src/api/routes.py", "src/api/schemas.py",
    "src/auth/login.py", "src/auth/tokens.py", "src/legacy/billing_v1.py", "src/utils/dates.py",
    "tests/test_checkout.py", "tests/test_auth.py", "README.md", "docs/setup.md",
]
GOOD_MSGS = [
    "Add {thing} to {area}", "Refactor {area} {thing}", "Handle empty {thing} in {area}", "Improve {area} error messages",
    "Speed up {thing} lookup", "Add tests for {area} {thing}", "Document {thing} in {area}", "Validate {thing} before saving",
]
FIX_MSGS = ["Fix {thing} crash in {area}", "fix", "oops, fix typo", "Fix broken {thing}", "hotfix: {area} {thing}", "Revert broken {thing} change"]
PANIC_MSGS = ["wip", "final", "final2", "asdf", "please work", "stuff", "update", "..."]
THINGS = ["promo code", "currency", "cart total", "token expiry", "session", "receipt", "user id", "timezone", "discount", "invoice"]


def _msg(rng: random.Random, templates: list[str], area: str) -> str:
    return rng.choice(templates).format(thing=rng.choice(THINGS), area=area)


def build_commits(seed: int = 42) -> list[dict]:
    rng = random.Random(seed)
    start = datetime(2026, 7, 1, 10, 0, tzinfo=TZ)
    t = start
    commits = []
    for _ in range(150):
        t += timedelta(hours=rng.choice([3, 5, 8, 14, 20, 26, 30]))
        who = rng.choices(range(3), weights=[5, 3, 4])[0]
        hour = rng.choices([rng.randint(9, 18), rng.randint(19, 23), rng.randint(0, 3)], weights=[6, 3, 2])[0]
        when = t.replace(hour=hour, minute=rng.randint(0, 59))
        roll = rng.random()
        if roll < 0.35:
            files = ["src/payments/checkout.py"] + (["tests/test_checkout.py"] if rng.random() < 0.4 else [])
            area = "checkout"
        elif roll < 0.55:
            files = ["src/api/routes.py", "src/api/schemas.py"]
            area = "api"
        elif roll < 0.63:
            files, who, area = ["src/legacy/billing_v1.py"], 1, "billing"
        else:
            files = rng.sample(FILES, rng.randint(1, 3))
            area = files[0].split("/")[-1].split(".")[0]
        night = when.hour < 5
        msg = _msg(rng, GOOD_MSGS, area) if rng.random() > 0.12 else rng.choice(PANIC_MSGS)
        commits.append({"who": who, "when": when, "files": files, "msg": msg})
        # night commits are followed by a fix much more often (that's the joke, and the science)
        if rng.random() < (0.6 if night else 0.12):
            fix_when = when + timedelta(hours=rng.randint(6, 30))
            commits.append({"who": who, "when": fix_when, "files": files[:1], "msg": _msg(rng, FIX_MSGS, area)})
            t = max(t, fix_when)
    commits.sort(key=lambda c: c["when"])
    return commits


def create_demo_repo(path: str | Path, seed: int = 42) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(path)], check=True)
    rng = random.Random(seed + 1)
    content: dict[str, list[str]] = {f: [f"# {f}"] for f in FILES}
    stream: list[bytes] = []
    for i, c in enumerate(build_commits(seed)):
        name, email = PEOPLE[c["who"]]
        ts = int(c["when"].timestamp())
        tz = c["when"].strftime("%z")
        msg = c["msg"].encode()
        stream.append(f"commit refs/heads/main\nmark :{i + 1}\nauthor {name} <{email}> {ts} {tz}\ncommitter {name} <{email}> {ts} {tz}\n".encode())
        stream.append(f"data {len(msg)}\n".encode() + msg + b"\n")
        if i:
            stream.append(f"from :{i}\n".encode())
        for f in c["files"]:
            lines = content[f]
            grow = 12 if f == "src/payments/checkout.py" else 4
            for _ in range(rng.randint(1, grow)):
                lines.insert(rng.randint(1, len(lines)), f"line_{rng.randint(0, 10**6)} = {rng.random():.4f}")
            for _ in range(rng.randint(0, 3)):
                if len(lines) > 3:
                    lines.pop(rng.randint(1, len(lines) - 1))
            data = ("\n".join(lines) + "\n").encode()
            stream.append(f"M 100644 inline {f}\ndata {len(data)}\n".encode() + data + b"\n")
    subprocess.run(["git", "-C", str(path), "fast-import", "--quiet"], input=b"".join(stream), check=True)
    subprocess.run(["git", "-C", str(path), "checkout", "-q", "-f", "main"], check=True)
    return path
