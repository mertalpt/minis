"""Karma: weighted reviewed lines over weighted authored lines, free of I/O."""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo

from pr_reviews.ranking import WORKING_DAY, ChangedFile, size, working_time


class WindowError(ValueError):
    """The full-weight period is not shorter than the window."""


@dataclass(frozen=True)
class Work:
    """A pull request the user reviewed or authored, as GitHub reports it."""

    owner: str
    repo: str
    number: int
    url: str
    dated_at: datetime
    additions: int
    deletions: int
    files: tuple[ChangedFile, ...]

    @property
    def ref(self) -> str:
        """The `owner/repo#number` reference."""
        return f"{self.owner}/{self.repo}#{self.number}"


@dataclass(frozen=True)
class Window:
    """How weight falls with age, in working days."""

    full_days: float
    days: float

    def __post_init__(self) -> None:
        """Reject a full-weight period that is not shorter than the window.

        Raises:
            WindowError: The full-weight period is not shorter.
        """
        if not self.full_days < self.days:
            raise WindowError(
                f"the full-weight period ({self.full_days:g} working days) must be "
                f"shorter than the window ({self.days:g} working days)"
            )

    def weight(self, age: timedelta) -> float:
        """Return the weight of work of an age, 0 outside the window."""
        days = age / WORKING_DAY
        if days <= self.full_days:
            return 1.0
        if days >= self.days:
            return 0.0
        return 1 - ((days - self.full_days) / (self.days - self.full_days)) ** 2

    def search_since(self, now: datetime) -> datetime:
        """Return an instant at or before the start of the window.

        Every 7 calendar days hold 5 working days; the extra day covers
        daylight saving shifts.
        """
        return now - timedelta(weeks=math.ceil(self.days / 5), days=1)


@dataclass(frozen=True)
class Counted:
    """Work inside the window, with its lines and weight."""

    work: Work
    lines: int
    age: timedelta
    weight: float

    @property
    def weighted_lines(self) -> float:
        """The lines times the weight."""
        return self.lines * self.weight


@dataclass(frozen=True)
class Side:
    """The counted work on one side of the ratio, newest first."""

    counted: tuple[Counted, ...]

    @property
    def weighted_lines(self) -> float:
        """The sum of the weighted lines."""
        return sum(c.weighted_lines for c in self.counted)


@dataclass(frozen=True)
class Karma:
    """Reviewed work against authored work."""

    reviewed: Side
    authored: Side
    window: Window

    @property
    def value(self) -> float | None:
        """Weighted reviewed lines over weighted authored lines.

        None when there are no weighted authored lines.
        """
        authored = self.authored.weighted_lines
        return self.reviewed.weighted_lines / authored if authored else None


def compute(
    reviewed: Iterable[Work],
    authored: Iterable[Work],
    *,
    now: datetime,
    tz: tzinfo | None,
    window: Window,
    include_owners: Sequence[str],
    exclude_owners: Sequence[str],
    ignore: Sequence[str],
    ignore_by_repo: dict[str, Sequence[str]],
) -> Karma:
    """Weigh reviewed and authored work and return the karma.

    Args:
        reviewed: The pull requests the user reviewed, dated at their first
            submitted review.
        authored: The pull requests the user authored, dated at when they
            became ready for review.
        now: The aware instant ages end at.
        tz: The time zone for weekends, or None for the machine's.
        window: How weight falls with age.
        include_owners: Only count these owners; empty counts every owner.
        exclude_owners: Do not count these owners.
        ignore: Ignore patterns for every repository.
        ignore_by_repo: Further ignore patterns by `owner/repo`.

    Owners and repositories compare without regard to case.

    Returns:
        The karma.
    """
    include = {o.lower() for o in include_owners}
    exclude = {o.lower() for o in exclude_owners}
    by_repo = {
        repo.lower(): list(patterns) for repo, patterns in ignore_by_repo.items()
    }

    def side(works: Iterable[Work]) -> Side:
        counted = []
        for work in works:
            owner = work.owner.lower()
            if (include and owner not in include) or owner in exclude:
                continue
            age = working_time(work.dated_at, now, tz)
            weight = window.weight(age)
            if not weight:
                continue
            patterns = [*ignore, *by_repo.get(f"{owner}/{work.repo.lower()}", [])]
            counted.append(Counted(work, size(work, patterns), age, weight))
        return Side(tuple(sorted(counted, key=lambda c: c.age)))

    return Karma(side(reviewed), side(authored), window)
