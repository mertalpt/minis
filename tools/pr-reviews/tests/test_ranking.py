from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest

from pr_reviews.ranking import (
    WORKING_DAY,
    ChangedFile,
    PullRequest,
    Request,
    rank,
    select,
    size_score,
    time_score,
    working_time,
)

# 2026-11-23 is a Monday.
MONDAY = datetime(2026, 11, 23, tzinfo=UTC)


def make_pr(number: int = 1, **changes: object) -> PullRequest:
    pr = PullRequest(
        owner="acme",
        repo="app",
        number=number,
        title="Change",
        url=f"https://github.com/acme/app/pull/{number}",
        ready_at=MONDAY,
        additions=10,
        deletions=0,
        files=(),
        approved=False,
        request=Request.TEAM,
    )
    return replace(pr, **changes)  # type: ignore[arg-type]


def rank_at(now: datetime, *prs: PullRequest, limit_days: float = 8) -> list[str]:
    ranked = rank(
        prs, now=now, tz=UTC, limit_days=limit_days, ignore=[], ignore_by_repo={}
    )
    return [r.pr.ref for r in ranked]


def test_working_time_skips_the_weekend() -> None:
    friday_noon = MONDAY + timedelta(days=4, hours=12)
    next_monday_noon = MONDAY + timedelta(days=7, hours=12)
    assert working_time(friday_noon, next_monday_noon, UTC) == timedelta(hours=24)


def test_working_time_from_a_weekend_starts_on_monday() -> None:
    saturday = MONDAY + timedelta(days=5, hours=10)
    assert working_time(saturday, MONDAY + timedelta(days=7, hours=3), UTC) == (
        timedelta(hours=3)
    )


def test_weekends_follow_the_given_time_zone() -> None:
    # Friday 23:00 UTC is already Saturday at UTC+3.
    friday_late = MONDAY + timedelta(days=4, hours=23)
    two_hours_later = friday_late + timedelta(hours=2)
    plus_three = timezone(timedelta(hours=3))
    assert working_time(friday_late, two_hours_later, plus_three) == timedelta()
    assert working_time(friday_late, two_hours_later, UTC) == timedelta(hours=1)


@pytest.mark.parametrize(
    ("lines", "score"),
    [(0, 21), (99, 21), (100, 20), (499, 18), (500, 16), (2099, 8), (2100, 0)],
)
def test_size_score_buckets(lines: int, score: int) -> None:
    assert size_score(lines)[0] == score


@pytest.mark.parametrize(("days", "score"), [(0, 0), (3.5, 3), (7.5, 21)])
def test_time_score_with_the_default_limit(days: float, score: int) -> None:
    assert time_score(days * WORKING_DAY, 8 * WORKING_DAY) == score


@pytest.mark.parametrize(
    ("since_ready", "overdue"),
    # Monday to the next Thursday at midnight is 8 working days.
    [(timedelta(days=10), True), (timedelta(days=10, seconds=-1), False)],
)
def test_overdue_from_the_limit(since_ready: timedelta, overdue: bool) -> None:
    [ranked] = rank(
        [make_pr()],
        now=MONDAY + since_ready,
        tz=UTC,
        limit_days=8,
        ignore=[],
        ignore_by_repo={},
    )
    assert ranked.overdue is overdue


def test_ordering() -> None:
    now = MONDAY + timedelta(weeks=3)
    overdue_old = make_pr(1, ready_at=MONDAY, additions=5000)
    overdue_new = make_pr(2, ready_at=MONDAY + timedelta(days=1))
    # Wednesday noon two weeks earlier: 7.5 working days.
    big_old = make_pr(3, ready_at=now - timedelta(days=19, hours=12), additions=1500)
    small_new = make_pr(4, ready_at=now - timedelta(hours=1))
    tie_old = make_pr(5, ready_at=now - timedelta(hours=3))
    tie_new = make_pr(6, ready_at=now - timedelta(hours=2))
    order = rank_at(now, tie_new, small_new, big_old, overdue_new, tie_old, overdue_old)
    assert order == [
        "acme/app#1",
        "acme/app#2",
        "acme/app#3",  # 8 + 21 beats 21 + 0
        "acme/app#5",
        "acme/app#6",
        "acme/app#4",
    ]


def test_ignored_files_do_not_count_toward_size() -> None:
    pr = make_pr(
        additions=1010,
        deletions=0,
        files=(
            ChangedFile("app.py", 10, 0),
            ChangedFile("web/package-lock.json", 500, 0),
            ChangedFile("gen/api_pb2.py", 500, 0),
        ),
    )
    [ranked] = rank(
        [pr],
        now=MONDAY,
        tz=UTC,
        limit_days=8,
        ignore=["package-lock.json"],
        ignore_by_repo={"ACME/App": ["gen/*"]},
    )
    assert ranked.size == 10


def test_select_filters() -> None:
    prs = [
        make_pr(1, owner="Acme", request=Request.DIRECT),
        make_pr(2, owner="acme", approved=True),
        make_pr(3, owner="other"),
    ]

    def numbers(**kwargs: object) -> list[int]:
        options: dict[str, object] = {
            "include_owners": [],
            "exclude_owners": [],
            "direct_only": False,
            "hide_approved": False,
        }
        options.update(kwargs)
        return [pr.number for pr in select(prs, **options)]  # type: ignore[arg-type]

    assert numbers() == [1, 2, 3]
    assert numbers(include_owners=["ACME"]) == [1, 2]
    assert numbers(exclude_owners=["acme"]) == [3]
    assert numbers(direct_only=True) == [1]
    assert numbers(hide_approved=True) == [1, 3]
