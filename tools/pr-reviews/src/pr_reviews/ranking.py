"""Scoring and ranking of review requests, free of I/O."""

import enum
import fnmatch
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo

SIZE_SCORES: tuple[tuple[int, int], ...] = (
    (100, 21),
    (200, 20),
    (300, 19),
    (500, 18),
    (800, 16),
    (1300, 13),
    (2100, 8),
)
SIZE_SCORE_LARGEST = 0
TIME_SCORES: tuple[int, ...] = (0, 1, 2, 3, 5, 8, 13, 21)
WORKING_DAY = timedelta(hours=24)


class Request(enum.StrEnum):
    """How the user's review was requested."""

    DIRECT = "direct"
    TEAM = "team"


@dataclass(frozen=True)
class ChangedFile:
    """A file a pull request changes."""

    path: str
    additions: int
    deletions: int


@dataclass(frozen=True)
class PullRequest:
    """A pull request requesting the user's review, as GitHub reports it."""

    owner: str
    repo: str
    number: int
    title: str
    url: str
    ready_at: datetime
    additions: int
    deletions: int
    files: tuple[ChangedFile, ...]
    approved: bool
    request: Request

    @property
    def ref(self) -> str:
        """The `owner/repo#number` reference."""
        return f"{self.owner}/{self.repo}#{self.number}"


@dataclass(frozen=True)
class Ranked:
    """A pull request with its scores."""

    pr: PullRequest
    size: int
    size_bucket: str
    size_score: int
    wait: timedelta
    time_score: int
    overdue: bool

    @property
    def priority(self) -> int:
        """The sum of the size score and the time score."""
        return self.size_score + self.time_score


def working_time(start: datetime, end: datetime, tz: tzinfo | None) -> timedelta:
    """Return the time between two instants that falls on weekdays.

    Args:
        start: The aware start instant.
        end: The aware end instant.
        tz: The time zone whose Saturdays and Sundays are excluded, or None
            for the local time zone of the machine.

    Returns:
        The weekday time from start to end, or zero if end is before start.
    """
    total = timedelta()
    day = start.astimezone(tz).date()
    last = end.astimezone(tz).date()
    while day <= last:
        if day.weekday() < 5:
            day_start = max(start, _midnight(day, tz))
            day_end = min(end, _midnight(day + timedelta(days=1), tz))
            if day_end > day_start:
                total += day_end - day_start
        day += timedelta(days=1)
    return total


def _midnight(day: date, tz: tzinfo | None) -> datetime:
    naive = datetime(day.year, day.month, day.day)
    # astimezone() on a naive datetime reads it as the machine's local time,
    # including its daylight saving rules for that date.
    return naive.astimezone() if tz is None else naive.replace(tzinfo=tz)


def is_ignored(path: str, patterns: Iterable[str]) -> bool:
    """Return whether a path matches any ignore pattern.

    A pattern without a slash matches the file name in any directory. A
    pattern with a slash matches the whole path, and its `*` also matches
    across slashes.
    """
    name = path.rsplit("/", 1)[-1]
    return any(
        fnmatch.fnmatchcase(path if "/" in pattern else name, pattern)
        for pattern in patterns
    )


def size(pr: PullRequest, patterns: Sequence[str]) -> int:
    """Return the lines added and deleted outside ignored files."""
    ignored = sum(
        f.additions + f.deletions for f in pr.files if is_ignored(f.path, patterns)
    )
    return pr.additions + pr.deletions - ignored


def size_score(lines: int) -> tuple[int, str]:
    """Return the size score and the label of its bucket."""
    for limit, score in SIZE_SCORES:
        if lines < limit:
            return score, f"<{limit}"
    return SIZE_SCORE_LARGEST, f">={SIZE_SCORES[-1][0]}"


def time_score(wait: timedelta, limit: timedelta) -> int:
    """Return the time score of a wait before the limit, or the top score."""
    step = min(int(wait / (limit / len(TIME_SCORES))), len(TIME_SCORES) - 1)
    return TIME_SCORES[step]


def rank(
    prs: Iterable[PullRequest],
    *,
    now: datetime,
    tz: tzinfo | None,
    limit_days: float,
    ignore: Sequence[str],
    ignore_by_repo: dict[str, Sequence[str]],
) -> list[Ranked]:
    """Score pull requests and return them in queue order.

    Overdue pull requests come first, oldest first; the rest follow by
    priority, highest first, and equal priorities oldest first.

    Args:
        prs: The pull requests to rank.
        now: The aware instant waits end at.
        tz: The time zone for weekends, or None for the machine's.
        limit_days: The deadline in working days.
        ignore: Ignore patterns for every repository.
        ignore_by_repo: Further ignore patterns by `owner/repo`, matched
            without regard to case.

    Returns:
        The ranked pull requests.
    """
    limit = limit_days * WORKING_DAY
    by_repo = {
        repo.lower(): list(patterns) for repo, patterns in ignore_by_repo.items()
    }
    ranked = []
    for pr in prs:
        patterns = [*ignore, *by_repo.get(f"{pr.owner}/{pr.repo}".lower(), [])]
        lines = size(pr, patterns)
        s_score, bucket = size_score(lines)
        wait = working_time(pr.ready_at, now, tz)
        ranked.append(
            Ranked(
                pr=pr,
                size=lines,
                size_bucket=bucket,
                size_score=s_score,
                wait=wait,
                time_score=time_score(wait, limit),
                overdue=wait >= limit,
            )
        )
    return sorted(
        ranked,
        key=lambda r: (
            not r.overdue,
            0 if r.overdue else -r.priority,
            r.pr.ready_at,
            r.pr.ref,
        ),
    )


def select(
    prs: Iterable[PullRequest],
    *,
    include_owners: Sequence[str],
    exclude_owners: Sequence[str],
    direct_only: bool,
    hide_approved: bool,
) -> list[PullRequest]:
    """Return the pull requests that pass the filters.

    Owners compare without regard to case. An empty include list includes
    every owner.
    """
    include = {o.lower() for o in include_owners}
    exclude = {o.lower() for o in exclude_owners}
    return [
        pr
        for pr in prs
        if (not include or pr.owner.lower() in include)
        and pr.owner.lower() not in exclude
        and not (direct_only and pr.request is not Request.DIRECT)
        and not (hide_approved and pr.approved)
    ]
