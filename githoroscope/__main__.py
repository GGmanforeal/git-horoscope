"""git-horoscope — read your repository's stars.

    python -m githoroscope                     horoscope for the repo in the current folder
    python -m githoroscope path/to/repo        …or any other repo
    python -m githoroscope --demo              build a fake repo with planted patterns and read it
    options: --html FILE  --no-open  --since "6 months ago"  --author NAME  --json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import textwrap
import webbrowser
from dataclasses import asdict
from pathlib import Path

from .analysis import analyze
from .gitlog import GitError, current_files, read_commits, repo_name
from .horoscope import readings
from .report import render


def _color(code: str, s: str, on: bool) -> str:
    return f"\x1b[{code}m{s}\x1b[0m" if on else s


def print_readings(a, repo: str, color: bool) -> None:
    width = 92
    print(_color("1;35", f"\n  ✨ Git Horoscope for {repo} ✨\n", color))
    for r in readings(a, repo):
        print(f"  {r.planet}  " + _color("1;33", r.title, color))
        for line in textwrap.wrap(r.text, width - 6):
            print("      " + line)
        print("      " + _color("2", f"📊 {r.evidence}", color))
        print()


def _read(repo: str, a: argparse.Namespace):
    commits = read_commits(repo, since=a.since, author=a.author)
    return analyze(commits, current_files(repo)), repo_name(repo)


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="githoroscope", description="Real repository analytics, delivered as a horoscope.")
    p.add_argument("repo", nargs="?", default=".")
    p.add_argument("--demo", action="store_true", help="analyse a generated demo repository")
    p.add_argument("--html", type=Path, default=Path("horoscope.html"), help="where to write the HTML report")
    p.add_argument("--no-open", action="store_true", help="don't open the report in a browser")
    p.add_argument("--since", help='only commits after this date, e.g. "6 months ago"')
    p.add_argument("--author", help="only commits by this author")
    p.add_argument("--json", action="store_true", help="print the raw analysis as JSON")
    a = p.parse_args(argv)

    try:
        if a.demo:
            from .demo import create_demo_repo

            # the demo repo only lives while we read it
            with tempfile.TemporaryDirectory(prefix="horoscope-", ignore_cleanup_errors=True) as tmp:
                analysis, name = _read(str(create_demo_repo(Path(tmp) / "shop-backend")), a)
        else:
            analysis, name = _read(a.repo, a)
    except (GitError, ValueError) as e:
        print(f"🔭 The stars are unclear: {e}", file=sys.stderr)
        return 1

    if a.json:
        print(json.dumps(asdict(analysis), ensure_ascii=False, indent=2, default=str))
        return 0
    color = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    print_readings(analysis, name, color)
    a.html.write_text(render(analysis, name), encoding="utf-8")
    print(f"  🔮 Full chart: {a.html.resolve()}")
    if not a.no_open:
        webbrowser.open(a.html.resolve().as_uri())
    return 0


def cli() -> None:
    sys.exit(main())


if __name__ == "__main__":
    cli()
