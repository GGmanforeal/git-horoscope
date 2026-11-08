"""Reads a repository's history with a single `git log` call and parses it into Commit objects."""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

RS, US = "\x1e", "\x1f"  # record / unit separators: safe even if commit messages contain anything
FORMAT = f"{RS}%H{US}%an{US}%ae{US}%aI{US}%s"


@dataclass
class FileChange:
    path: str
    added: int
    deleted: int

    @property
    def churn(self) -> int:
        return self.added + self.deleted


@dataclass
class Commit:
    sha: str
    author: str
    email: str
    when: datetime  # author's local time, with its UTC offset
    subject: str
    files: list[FileChange] = field(default_factory=list)

    @property
    def churn(self) -> int:
        return sum(f.churn for f in self.files)


class GitError(RuntimeError):
    pass


def run_git(repo: str | Path, *args: str) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, check=True, encoding="utf-8", errors="replace"
        )
    except FileNotFoundError as e:
        raise GitError("git is not installed or not on PATH") from e
    except subprocess.CalledProcessError as e:
        raise GitError(e.stderr.strip() or "git failed") from e
    return out.stdout


_BRACE = re.compile(r"\{([^{}]*) => ([^{}]*)\}")


def normalise_path(p: str) -> str:
    """Resolves git's rename notation: 'src/{old => new}/a.py' -> 'src/new/a.py', 'a => b' -> 'b'."""
    if "=>" not in p:
        return p
    if "{" in p:
        p = _BRACE.sub(lambda m: m.group(2), p)
        return p.replace("//", "/")
    return p.split(" => ")[-1]


def parse_log(text: str) -> list[Commit]:
    commits: list[Commit] = []
    for record in text.split(RS):
        if not record.strip():
            continue
        header, _, body = record.partition("\n")
        parts = header.split(US)
        if len(parts) < 5:
            continue
        sha, author, email, date, subject = parts[:5]
        c = Commit(sha, author, email, datetime.fromisoformat(date.strip()), subject.strip())
        for line in body.splitlines():
            cols = line.split("\t")
            if len(cols) != 3:
                continue
            a, d, path = cols
            c.files.append(FileChange(normalise_path(path), int(a) if a.isdigit() else 0, int(d) if d.isdigit() else 0))
        commits.append(c)
    commits.sort(key=lambda c: c.when)
    return commits


def read_commits(repo: str | Path, since: str | None = None, author: str | None = None) -> list[Commit]:
    args = ["log", "--no-merges", "--numstat", f"--pretty=format:{FORMAT}", "-M"]
    if since:
        args.append(f"--since={since}")
    if author:
        args.append(f"--author={author}")
    return parse_log(run_git(repo, *args))


def current_files(repo: str | Path) -> dict[str, int]:
    """Lines of code per tracked file at HEAD (binary and huge files are skipped)."""
    root = Path(run_git(repo, "rev-parse", "--show-toplevel").strip())
    out: dict[str, int] = {}
    for rel in run_git(repo, "ls-files").splitlines():
        p = root / rel
        try:
            if p.stat().st_size > 2_000_000:
                continue
            data = p.read_bytes()
        except OSError:
            continue
        if b"\0" in data[:8000]:
            continue
        out[rel] = data.count(b"\n") + (0 if data.endswith(b"\n") or not data else 1)
    return out


def repo_name(repo: str | Path) -> str:
    return Path(run_git(repo, "rev-parse", "--show-toplevel").strip()).name
